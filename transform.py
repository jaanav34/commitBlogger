
"""
Transformation Module: Handles preprocessing of diffs and messages, and interacts with the Gemini API
to generate blog posts, LinkedIn summaries, and click-worthy titles.
"""

import os
import google.generativeai as genai
import logging
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, before_log, after_log

# Configure logging for this module
logger = logging.getLogger(__name__)

class Transformer:
    """
    Manages the transformation of raw commit/note data into publishable content
    using the Gemini API.
    """

    def __init__(self, gemini_api_key: str):
        """
        Initializes the Transformer with the Gemini API key.

        Args:
            gemini_api_key (str): Your Google AI Studio Gemini API key.
        """
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash") # Or gemini-1.5-pro if available and desired

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10),
           stop=stop_after_attempt(3),
           retry=retry_if_exception_type(genai.types.BlockedPromptException),
           before_sleep=before_log(logger, logging.INFO),
           after=after_log(logger, logging.WARNING))
    def _call_gemini(self, prompt: str) -> str:
        """
        Helper function to call Gemini API with retry logic and error handling.
        """
        response = None  # Initialize response to handle cases where assignment fails
        try:
            # response = "called 2.5 flash with prompt: \n" + prompt
            logging.info(f"Calling Gemini API with prompt: {prompt[:100]}...")  # Log first 100 chars for brevity
            response = self.model.generate_content(prompt)
            # The .text accessor is the safest way to get the content.
            # It raises a ValueError if the response is blocked or has no text.
            return response.text
        except ValueError:
            # This can happen if the response is blocked for safety reasons.
            # Log the feedback for debugging, checking if response exists first.
            if response:
                logger.warning(f"Gemini returned no content. It may have been blocked. Prompt feedback: {response.prompt_feedback}")
            else:
                logger.warning("Gemini call failed with ValueError before a response object was created.")
            return ""
        except genai.types.BlockedPromptException as e:
            logger.warning(f"Gemini prompt blocked: {e}. Adjusting prompt or skipping.")
            return ""
        except genai.types.StopCandidateException as e:
            logger.warning(f"Gemini generation stopped prematurely: {e}. Partial content might be returned.")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error during Gemini API call: {e}", exc_info=True)
            return ""

    def _summarize_diff(self, files_changed: list) -> str:
        """
        Summarizes the code changes from the diffs. Uses Gemini for large diffs.

        Args:
            files_changed (list): A list of dictionaries, each representing a changed file
                                  from GitHub commit data, including 'patch' content.

        Returns:
            str: A concise summary of the changes.
        """
        diff_texts = []
        for file in files_changed:
            filename = file.get("filename", "Unknown File")
            status = file.get("status", "")
            patch = file.get("patch", "")

            if patch:
                # If patch is too long, ask Gemini to summarize it
                if len(patch) > 1000: # Arbitrary threshold for large diffs
                    logger.info(f"Summarizing large diff for {filename} using Gemini.")
                    summary_prompt = f"Summarize the following code diff for file {filename} ({status}):\n```\n{patch}\n```\nProvide a concise summary focusing on the key changes and their purpose. If it is an initial commit, explain instead what the overall repository does, ignoring most of the peripheral details.\n"
                    diff_summary_text = self._call_gemini(summary_prompt)
                    diff_texts.append(f"File: {filename} ({status})\nSummary: {diff_summary_text}")
                else:
                    # Simple heuristic to get a few lines from the patch for summary
                    lines = patch.split("\n")
                    relevant_lines = [line for line in lines if line.startswith(("+", "-", " ")) and not line.startswith(("++3", "---"))]
                    diff_texts.append(f"File: {filename} ({status})\n" + "\n".join(relevant_lines[:10]) + ("..." if len(relevant_lines) > 10 else ""))
            else:
                diff_texts.append(f"File: {filename} ({status}) - No patch content available.")
        
        return "\n\n".join(diff_texts) if diff_texts else "No significant code changes detected."

    def generate_blog_post(self, commit_message: str, files_changed: list, notion_content: str = "") -> str:
        """
        Generates a Markdown-formatted blog post based on commit message, diff, and Notion content.

        Args:
            commit_message (str): The main commit message.
            files_changed (list): List of changed files with diff patches.
            notion_content (str): Optional, relevant content from Notion notes.

        Returns:
            str: The generated blog post in Markdown format.
        """
        diff_summary = self._summarize_diff(files_changed)
        
        prompt = f"""You are an expert technical storyteller and a senior software engineer writing as me, Jaanav Shah, a Computer Engineering student at Purdue University's engineering blog. Your goal is to turn technical updates into engaging narratives.

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

            Start with the narrative from the Notion note.
            Integrate the technical details from the commit message and code summary to illustrate the points made in the narrative.
            Explain the impact and importance of this update.
            The final post should be well-structured with a clear introduction, body, and conclusion. Use headings and lists to improve readability.
            Crucially, the tone should be that of a human expert explaining a project, not an AI summarizing a commit. The Notion note is the human's voice; amplify it.

"""
        logger.info("Generating blog post with Gemini...")
        return self._call_gemini(prompt)

    def generate_linkedin_summary(self, commit_message: str, files_changed: list, notion_content: str = "") -> str:
        """
        Generates a concise LinkedIn-friendly summary of the changes.

        Args:
            commit_message (str): The main commit message.
            files_changed (list): List of changed files with diff patches.
            notion_content (str): Optional, relevant content from Notion notes.

        Returns:
            str: A short, professional summary suitable for LinkedIn.
        """
        diff_summary = self._summarize_diff(files_changed)

        prompt = f"""You are a professional content creator for LinkedIn.
Based on the following technical update, craft a concise (100-150 words) and impactful summary for a LinkedIn post.
Focus on the value and impact of the changes, suitable for a professional network.

**Commit Message:**
```
{commit_message}
```

**Code Changes Summary:**
```
{diff_summary}
```

**Additional Context (from Notion notes, if any):**
```
{notion_content}
```

Include relevant keywords and a call to action if appropriate (e.g., "Learn more in my latest blog post").
"""
        logger.info("Generating LinkedIn summary with Gemini...")
        return self._call_gemini(prompt)

    def generate_click_worthy_title(self, commit_message: str, blog_post_content: str) -> str:
        """
        Generates a click-worthy and SEO-friendly title for the blog post.

        Args:
            commit_message (str): The main commit message.
            blog_post_content (str): The generated blog post content.

        Returns:
            str: A compelling title.
        """
        prompt = f"""You are an expert in SEO and content marketing.
Based on the following commit message and blog post content, generate 3-5 highly click-worthy and SEO-friendly titles.
Prioritize titles that are engaging, informative, and include relevant keywords.

**Commit Message:**
```
{commit_message}
```

**Blog Post Content (for context):**
```
{blog_post_content}
```

Provide only the titles, one per line, without any additional text or numbering.
"""
        logger.info("Generating click-worthy titles with Gemini...")
        response_text = self._call_gemini(prompt)
        titles = [t.strip() for t in response_text.split("\n") if t.strip()]
        return titles[0] if titles else "Default Blog Post Title"

# Example Usage (for testing purposes, will be removed in final main.py)
if __name__ == '__main__':
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    if not GEMINI_API_KEY:
        print("Please set the GEMINI_API_KEY environment variable.")
    else:
        transformer = Transformer(gemini_api_key=GEMINI_API_KEY)

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
        blog_post = transformer.generate_blog_post(sample_commit_message, sample_files_changed, sample_notion_content)
        print("\n--- Generated Blog Post ---\n", blog_post)

        # Generate LinkedIn summary
        linkedin_summary = transformer.generate_linkedin_summary(sample_commit_message, sample_files_changed, sample_notion_content)
        print("\n--- Generated LinkedIn Summary ---\n", linkedin_summary)

        # Generate click-worthy title
        title = transformer.generate_click_worthy_title(sample_commit_message, blog_post)
        print("\n--- Generated Title ---\n", title)
