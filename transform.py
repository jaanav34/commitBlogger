
"""
Transformation Module: Handles preprocessing of diffs and messages, and interacts with the Gemini API
to generate blog posts, LinkedIn summaries, and click-worthy titles.
"""

import os
import google.generativeai as genai

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
        self.model = genai.GenerativeModel("gemini-pro") # Or gemini-1.5-pro if available and desired

    def _summarize_diff(self, files_changed: list) -> str:
        """
        Summarizes the code changes from the diffs.

        Args:
            files_changed (list): A list of dictionaries, each representing a changed file
                                  from GitHub commit data, including 'patch' content.

        Returns:
            str: A concise summary of the changes.
        """
        diff_summary = []
        for file in files_changed:
            filename = file.get("filename", "Unknown File")
            status = file.get("status", "")
            patch = file.get("patch", "")

            summary_line = f"File: {filename} ({status})\n"
            if patch:
                # Simple heuristic to get a few lines from the patch for summary
                lines = patch.split("\n")
                relevant_lines = [line for line in lines if line.startswith(("+", "-", " ")) and not line.startswith(("+++", "---"))]
                summary_line += "\n".join(relevant_lines[:5]) + ("..." if len(relevant_lines) > 5 else "")
            diff_summary.append(summary_line)
        
        # TODO: For very large diffs, consider using Gemini to summarize the diff itself
        # This would require another API call or a more sophisticated local parsing.
        return "\n\n".join(diff_summary) if diff_summary else "No significant code changes detected."

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
        
        prompt = f"""You are a technical blogger and a software engineer.
Based on the following information, write a detailed and engaging Markdown-formatted blog post.

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

Your blog post should:
1.  Explain what was implemented, changed, or fixed in a clear and concise manner.
2.  Discuss why these changes are important, their impact, or how they fit into a larger project context.
3.  Maintain technical clarity and readability, suitable for a developer audience.
4.  Be approximately 300-500 words, structured with headings and bullet points where appropriate.
5.  Include a brief introduction and conclusion.
"""
        print("Generating blog post with Gemini...")
        try:
            response = self.model.generate_content(prompt)
            # TODO: Add error handling for content filtering or empty responses
            return response.text
        except Exception as e:
            print(f"Error generating blog post: {e}")
            return ""

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
        print("Generating LinkedIn summary with Gemini...")
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Error generating LinkedIn summary: {e}")
            return ""

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
        print("Generating click-worthy titles with Gemini...")
        try:
            response = self.model.generate_content(prompt)
            # Return the first title or a selection mechanism later
            titles = [t.strip() for t in response.text.split("\n") if t.strip()]
            return titles[0] if titles else "Default Blog Post Title"
        except Exception as e:
            print(f"Error generating titles: {e}")
            return "Default Blog Post Title"

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



