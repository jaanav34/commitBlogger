
"""
Transformation Module: Handles preprocessing of diffs and messages, and interacts with the Gemini API
to generate blog posts, LinkedIn summaries, and click-worthy titles.
"""
import asyncio
import time
import os
import google.generativeai as genai
import logging
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, before_log, after_log

# Configure logging for this module
logger = logging.getLogger(__name__)

class AsyncTokenRateLimiter:
    """
    Manages API call rates for both TPM and RPM with a unified delay mechanism.
    This is an ASYNCHRONOUS version.
    """
    def __init__(self, capacity: int, refill_rate_per_minute: int, rpm_limit: int):
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.refill_rate_per_second = float(refill_rate_per_minute) / 60.0
        self.last_refill_time = time.monotonic()
        self._lock = asyncio.Lock()
        self._rpm_delay = 60.0 / rpm_limit if rpm_limit > 0 else 0

    def _refill(self):
        """Refills the token bucket based on the time elapsed since the last refill."""
        now = time.monotonic()
        elapsed = now - self.last_refill_time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate_per_second)
        self.last_refill_time = now

    async def consume(self, tokens_to_consume: int, model_name: str):
        """
        Asynchronously checks if a call can proceed based on token budget. If not, it waits.
        This version checks the budget BEFORE the call is made to prevent 429 errors.
        """
        async with self._lock:
            if tokens_to_consume > self.capacity:
                logger.warning(f"Call to '{model_name}' requests {tokens_to_consume} tokens, which exceeds the bucket capacity of {self.capacity}.")
            
            self._refill()

            if tokens_to_consume > self.tokens:
                required_tokens = tokens_to_consume - self.tokens
                wait_time = required_tokens / self.refill_rate_per_second
                logger.info(f"TPM Limit for {model_name}: Pausing for {wait_time:.2f}s to refill tokens.")
                await asyncio.sleep(wait_time)
                self._refill()

            self.tokens -= tokens_to_consume

    async def enforce_rpm_delay(self):
        """Asynchronously enforces the mandatory delay between requests."""
        if self._rpm_delay > 0:
            await asyncio.sleep(self._rpm_delay)

class Transformer:
    """
    Manages the transformation of raw commit/note data into publishable content
    using the Gemini API.
    """

    def __init__(self, gemini_api_key: str, model_configs: dict):
        """
        Initializes the Transformer with API keys and model configurations.

        Args:
            gemini_api_key (str): Your Google AI Studio Gemini API key.
            model_configs (dict): A dictionary containing model names and their rate limits.
        """
        genai.configure(api_key=gemini_api_key)
        self.models = {
            'blog': genai.GenerativeModel(model_configs['blog']['name']),
            'summary': genai.GenerativeModel(model_configs['summary']['name']),
            'linkedin': genai.GenerativeModel(model_configs['linkedin']['name']),
            'title': genai.GenerativeModel(model_configs['title']['name'])
        }
        
        self.rate_limiters = {}
        unique_model_names = {cfg['name'] for cfg in model_configs.values()}
        
        for model_name in unique_model_names:
            # Find the config for this unique model name
            # This assumes model names in the config dict are consistent
            config = next((cfg for cfg in model_configs.values() if cfg['name'] == model_name), None)
            if config:
                self.rate_limiters[model_name] = AsyncTokenRateLimiter(
                    capacity=config['tpm'],
                    refill_rate_per_minute=config['tpm'],
                    rpm_limit=config['rpm']
                )
                logger.info(f"Initialized rate limiter for {model_name}: {config['rpm']} RPM, {config['tpm']} TPM")


    @retry(wait=wait_exponential(multiplier=1, min=4, max=10),
           stop=stop_after_attempt(3),
           retry=retry_if_exception_type(genai.types.BlockedPromptException),
           before_sleep=before_log(logger, logging.INFO),
           after=after_log(logger, logging.WARNING))
    
    async def _call_gemini_async(self, model_key: str, prompt: str) -> str:
        """
        Helper function to call Gemini API asynchronously with per-model rate limiting.
        """
        model = self.models[model_key]
        model_name = model.model_name

        # 1. Pre-flight token counting and rate limiting
        if model_name in self.rate_limiters:
            limiter = self.rate_limiters[model_name]
            try:
                # Count tokens before the main call
                prompt_tokens = await model.count_tokens_async(prompt)
                # Consume tokens from the bucket (may wait)
                await limiter.consume(prompt_tokens.total_tokens, model_name)
                # Enforce a fixed delay for RPM
                await limiter.enforce_rpm_delay()
            except Exception as e:
                logger.error(f"Error during token counting or rate limiting for {model_name}: {e}")
                # Fail safe, proceed with call but log warning
        
        # 2. Make the actual API call
        response = None
        try:
            logger.info(f"Calling Gemini ({model_name}) with prompt: {prompt[:100]}...")
            response = await model.generate_content_async(prompt)
            return response.text
        except ValueError:
            if response:
                logger.warning(f"Gemini returned no content. It may have been blocked. Prompt feedback: {response.prompt_feedback}")
            else:
                logger.warning("Gemini call failed with ValueError before a response object was created.")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error during Gemini API call to {model_name}: {e}", exc_info=True)
            return ""


    async def _summarize_single_file_async(self, file: dict) -> str:
        """Asynchronously summarizes the diff for a single file."""
        filename = file.get("filename", "Unknown File")
        status = file.get("status", "")
        patch = file.get("patch", "")

        if not patch:
            return f"File: {filename} ({status}) - No patch content available."

        if len(patch) > 1000:  # Arbitrary threshold for large diffs
            logger.info(f"Summarizing large diff for {filename} using Gemini.")
            summary_prompt = f"Summarize the following code diff for file {filename} ({status}):\n```\n{patch}\n```\nProvide a concise summary focusing on the key changes and their purpose."
            diff_summary_text = await self._call_gemini_async('summary', summary_prompt)
            return f"File: {filename} ({status})\nSummary: {diff_summary_text}"
        else:
            lines = patch.split("\n")
            relevant_lines = [line for line in lines if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
            summary = "\n".join(relevant_lines[:10]) + ("..." if len(relevant_lines) > 10 else "")
            return f"File: {filename} ({status})\n{summary}"

    async def _summarize_diff_async(self, files_changed: list) -> str:
        """
        Summarizes code changes from diffs, running large diff summaries concurrently.
        """
        if not files_changed:
            return "No significant code changes detected."
        
        tasks = [self._summarize_single_file_async(file) for file in files_changed]
        summaries = await asyncio.gather(*tasks)
        
        return "\n\n".join(summaries)


    async def generate_blog_post(self, commit_message: str, files_changed: list, notion_content: str = "", aggregated_context: str = "") -> str:
        """
        Generates a Markdown-formatted blog post based on commit message, diff, previous posts and Notion content.

        Args:
            commit_message (str): The main commit message.
            files_changed (list): List of changed files with diff patches.
            notion_content (str): Optional, relevant content from Notion notes.

        Returns:
            str: The generated blog post in Markdown format.
        """
        diff_summary = await self._summarize_diff_async(files_changed)
        context_prompt_part = ""
        if aggregated_context:
            context_prompt_part = f"""
            **Previous Blog Posts (for context and to avoid repetition):**
            ---
            {aggregated_context}
            ---
            """
            
        prompt = f"""You are an expert technical storyteller and a senior software engineer writing as me, Jaanav Shah, a Computer Engineering student at Purdue University's engineering blog. Your goal is to turn technical updates into engaging narratives.

            Previous Blog Posts (already made by you, automatically updating):
            {context_prompt_part}

            Core Narrative & High-Level Context (from my Notion Note):
            This is the main story. Use this as the foundation for the blog post. It explains the "why" and the "what".
            Notion Note Content:
            {notion_content if notion_content.strip() else "No high-level context was provided. You must infer the purpose from the commit message and code changes below."}
            
            Technical Implementation Details (from the Git Commit):
            Use these details as technical evidence to support the core narrative. Weave them into the story to show how the goal was accomplished. Do not just list the changes.

            Commit Message (this is super undetailed, do not write this in the blog content):
            {commit_message}

            Code Changes Summary:
            {diff_summary}
            
            Your Task:
            Write a detailed, engaging, and polished blog post in Markdown format.
            1.  Read the previous blog posts to understand the project's progression.
            Start with the narrative from the Notion note (unless not provided)
            Integrate the technical details from the commit message and code summary to illustrate the points made in the narrative.
            Explain the impact and importance of this update.
            4.  **Crucially, make the new post a distinct, valuable addition. Do not repeat content from the context.**
            The final post should be well-structured with a clear introduction, body, and conclusion. Use headings and lists to improve readability.
            Crucially, the tone should be that of a human expert explaining a project, not an AI summarizing a commit. The Notion note is the human's voice; amplify it.

"""
        logger.info("Generating blog post with Gemini...")
        return await self._call_gemini_async('blog', prompt)


    async def generate_linkedin_summary(self, commit_message: str, files_changed: list, notion_content: str = "") -> str:
        """
        Generates a concise LinkedIn-friendly summary of the changes.
        """
        diff_summary = await self._summarize_diff_async(files_changed)

        prompt = f"""You are a professional content creator for LinkedIn.
    Based on the following technical update, craft a concise (100-150 words) and impactful summary for a LinkedIn post.
    Focus on the value and impact of the changes, suitable for a professional network.

    **Commit Message:**
    {commit_message}

    **Code Changes Summary:**
    {diff_summary}

    **Additional Context (from Notion notes, if any):**
    {notion_content}

    Include relevant keywords and a call to action if appropriate (e.g., "Learn more in my latest blog post").
    """
        logger.info("Generating LinkedIn summary with Gemini...")
        return await self._call_gemini_async('linkedin', prompt)

    async def generate_click_worthy_title(self, commit_message: str, blog_post_content: str) -> str:
        """
        Generates a click-worthy and SEO-friendly title for the blog post.
        """
        prompt = f"""You are an expert in SEO and content marketing.
    Based on the following commit message and blog post content, generate 3-5 highly click-worthy and SEO-friendly titles.
    Prioritize titles that are engaging, informative, and include relevant keywords.

    **Commit Message:**
    {commit_message}

    Generated code
    **Blog Post Content (for context):**
    {blog_post_content}

    Provide only the titles, one per line, without any additional text or numbering.
    """
        logger.info("Generating click-worthy titles with Gemini...")
        response_text = await self._call_gemini_async('title', prompt)
        titles = [t.strip() for t in response_text.split("\n") if t.strip()]
        return titles[0] if titles else "Default Blog Post Title"


    
# Example Usage (for testing purposes, will be removed in final main.py)
if __name__ == '__main__':
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    if not GEMINI_API_KEY:
        print("Please set the GEMINI_API_KEY environment variable.")
    else:
        async def main():
            transformer = Transformer(gemini_api_key=GEMINI_API_KEY) # type: ignore

            sample_commit_message = "feat: Add user authentication with OAuth2"
            sample_files_changed = [
                {
                    "filename": "auth.py",
                    "status": "added",
                    "patch": """--- /dev/null\n+++ b/auth.py\n@@ -0,0 +1,20 @@\n+import oauthlib\n+from flask import Flask, redirect, url_for, session, request\n+# ... (more code)\n+def login():\n+    # OAuth2 flow\n+    pass\n+"""
                },
                {
                    "filename": "app.py",
                    "status": "modified",
                    "patch": """--- a/app.py\n+++ b/app.py\n@@ -10,6 +10,7 @@\n from . import db\n from .auth import login_required, login\n \n+app.register_blueprint(auth.bp)\n @app.route("/hello")\n def hello():\n     return "Hello, World!"\n"""
                }
            ]
            sample_notion_content = "Design notes: OAuth2 integration for user login. Use Google as provider."

            # Generate blog post
            blog_post = await transformer.generate_blog_post(sample_commit_message, sample_files_changed, sample_notion_content)
            print("\n--- Generated Blog Post ---\n", blog_post)

            # Generate LinkedIn summary
            linkedin_summary = await transformer.generate_linkedin_summary(sample_commit_message, sample_files_changed, sample_notion_content)
            print("\n--- Generated LinkedIn Summary ---\n", linkedin_summary)

            # Generate click-worthy title
            title = await transformer.generate_click_worthy_title(sample_commit_message, blog_post)
            print("\n--- Generated Title ---\n", title)

        asyncio.run(main())
