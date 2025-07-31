
"""
Ingestion Module: Handles fetching data from GitHub and Notion, and managing processed state.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from github import Github, RateLimitExceededException, UnknownObjectException, GithubException
from notion_client import Client
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, before_log, after_log

# Configure logging for this module
logger = logging.getLogger(__name__)

class Ingester:
    """
    Manages data ingestion from GitHub and Notion, and tracks processed items.
    """

    def __init__(self, github_token: str, notion_token: str, state_file: str = 'processed_state.json'):
        """
        Initializes the Ingester with API tokens and state file path.

        Args:
            github_token (str): GitHub personal access token.
            notion_token (str): Notion integration token (optional).
            state_file (str): Path to the JSON file storing processed item SHAs/IDs.
        """
        self.github_client = Github(github_token)
        self.notion_client = Client(auth=notion_token) if notion_token else None
        self.state_file = state_file
        self.processed_shas = self._load_processed_shas()

    def _load_processed_shas(self) -> set:
        """
        Loads the set of already processed SHAs from the state file.

        Returns:
            set: A set of processed SHAs.
        """
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return set(json.load(f))
            except json.JSONDecodeError:
                logger.warning(f"Corrupted state file {self.state_file}. Starting with empty state.")
                return set()
        return set()

    def _save_processed_shas(self):
        """
        Saves the current set of processed SHAs to the state file.
        """
        try:
            with open(self.state_file, 'w') as f:
                json.dump(list(self.processed_shas), f, indent=4)
        except IOError as e:
            logger.error(f"Failed to save processed SHAs to {self.state_file}: {e}")

    def _get_notion_page_title(self, page: dict) -> str:
        """
        Extracts the title from a Notion page object by finding the 'title' property type.
        This is a robust way to get the title regardless of its property name.

        Args:
            page (dict): The Notion page object.

        Returns:
            str: The concatenated title text or "Untitled".
        """
        properties = page.get("properties", {})
        for prop_value in properties.values():
            if prop_value.get("type") == "title":
                title_parts = [part.get("plain_text", "") for part in prop_value.get("title", [])]
                return "".join(title_parts)
        return "Untitled"

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10),
           stop=stop_after_attempt(5),
           retry=retry_if_exception_type((RateLimitExceededException, GithubException)),
           before_sleep=before_log(logger, logging.INFO),
           after=after_log(logger, logging.WARNING))
    def _get_github_repo(self, repo_name: str):
        """
        Helper to get GitHub repository with retry logic.
        """
        return self.github_client.get_repo(repo_name)

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10),
           stop=stop_after_attempt(5),
           retry=retry_if_exception_type((RateLimitExceededException, GithubException)),
           before_sleep=before_log(logger, logging.INFO),
           after=after_log(logger, logging.WARNING))
    def _get_github_commit(self, repo, sha: str):
        """
        Helper to get a specific GitHub commit with retry logic.
        """
        return repo.get_commit(sha)

    def fetch_github_commits(self, repo_name: str, since_days: int = 0, batch_mode: bool = False) -> list:
        """
        Fetches commits from a GitHub repository.

        Args:
            repo_name (str): The full name of the GitHub repository (e.g., 'owner/repo').
            since_days (int): Number of days to look back for new commits. If 0, fetches all.
            batch_mode (bool): If True, fetches all historical commits regardless of `since_days`
                               and does not filter by processed SHAs. Used for initial setup.

        Returns:
            list: A list of dictionaries, each representing a commit with relevant details.
        """
        logger.info(f"Fetching GitHub commits for {repo_name}...")
        commits_data = []
        try:
            repo = self._get_github_repo(repo_name)
            
            if batch_mode:
                # Implement pagination for large number of commits in batch mode
                # Iterate through all commits, handling pagination automatically
                commits = repo.get_commits()
            else:
                since_date = datetime.now() - timedelta(days=since_days)
                commits = repo.get_commits(since=since_date)

            for commit in commits:
                if not batch_mode and commit.sha in self.processed_shas:
                    logger.info(f"Skipping already processed commit: {commit.sha[:8]}")
                    continue # Skip already processed commits in incremental mode

                try:
                    # Fetch full commit details to get file changes (diffs)
                    full_commit = self._get_github_commit(repo, commit.sha)
                    files_changed = []
                    for file in full_commit.files:
                        files_changed.append({
                            'filename': file.filename,
                            'status': file.status,
                            'additions': file.additions,
                            'deletions': file.deletions,
                            'changes': file.changes,
                            'raw_url': file.raw_url, # URL to fetch raw content for diff if needed
                            'patch': file.patch # The actual diff content
                        })

                    commits_data.append({
                        'sha': commit.sha,
                        'message': commit.commit.message,
                        'author': commit.commit.author.name,
                        'date': commit.commit.author.date.isoformat(),
                        'url': commit.html_url,
                        'files': files_changed
                    })
                    self.processed_shas.add(commit.sha)
                except UnknownObjectException:
                    logger.warning(f"Commit {commit.sha} not found or accessible. Skipping.")
                except GithubException as e:
                    logger.error(f"GitHub API error processing commit {commit.sha}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error processing commit {commit.sha}: {e}", exc_info=True)

            self._save_processed_shas()
            logger.info(f"Fetched {len(commits_data)} new/unprocessed commits.")
            return commits_data
        except GithubException as e:
            logger.critical(f"Failed to fetch GitHub repository {repo_name} due to API error: {e}")
            return []
        except Exception as e:
            logger.critical(f"An unexpected error occurred during GitHub ingestion: {e}", exc_info=True)
            return []

    def fetch_notion_notes(self, database_id: str, since_date: Optional[datetime]) -> list:
        """
        Fetches notes (pages) from a Notion database.

        Args:
            database_id (str): The ID of the Notion database.
            since_date (Optional[datetime]): Only fetch notes created/updated after this date.

        Returns:
            list: A list of dictionaries, each representing a Notion page with relevant details.
        """
        if not self.notion_client:
            logger.warning("Notion client not initialized. Skipping Notion ingestion.")
            return []

        logger.info(f"Fetching Notion notes from database {database_id}...")
        notes_data = []
        try:
            filter_obj = None
            if since_date:
                filter_obj = {
                    "timestamp": "last_edited_time",
                    "last_edited_time": {
                        "on_or_after": since_date.isoformat()
                    }
                }


            # Notion API integration to fetch notes with pagination and filtering
            has_more = True
            start_cursor = None
            while has_more:
                response = self.notion_client.databases.query(
                    database_id=database_id,
                    filter=filter_obj,
                    start_cursor=start_cursor
                )
                for page in response["results"]: # type: ignore
                    page_id = page["id"]
                    # Extract title
                    title = self._get_notion_page_title(page)
                    
                    # Fetch block content
                    content_blocks = self.notion_client.blocks.children.list(block_id=page_id)
                    page_content = ""
                    for block in content_blocks["results"]: # type: ignore
                        if "type" in block and block["type"] == "paragraph" and "rich_text" in block["paragraph"]:
                            for text_obj in block["paragraph"]["rich_text"]:
                                if "plain_text" in text_obj:
                                    page_content += text_obj["plain_text"] + "\n"
                        # TODO: Handle other block types (headings, lists, code blocks) as needed

                    notes_data.append({
                        'id': page_id,
                        'title': title,
                        'content': page_content,
                        'last_edited_time': page["last_edited_time"],
                        'url': page["url"]
                    })
                has_more = response["has_more"] # type: ignore
                start_cursor = response["next_cursor"] # type: ignore

            logger.info(f"Fetched {len(notes_data)} Notion notes.")
            return notes_data
        except Exception as e:
            logger.error(f"Error fetching Notion notes from database {database_id}: {e}", exc_info=True)
            return []

    def get_processed_shas(self) -> set:
        """
        Returns the set of SHAs that have been processed.
        """
        return self.processed_shas

# Example Usage (for testing purposes, will be removed in final main.py)
if __name__ == '__main__':
    # These would typically come from environment variables
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    NOTION_TOKEN = os.getenv('NOTION_TOKEN')
    GITHUB_REPO = os.getenv('GITHUB_REPO', 'your_github_username/your_repo_name')
    NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID', 'your_notion_database_id')

    if not GITHUB_TOKEN:
        print("Please set GITHUB_TOKEN environment variable.")
    else:
        ingester = Ingester(github_token=GITHUB_TOKEN, notion_token=NOTION_TOKEN) # type: ignore

        # Example: Fetch commits from the last 7 days (incremental mode)
        # new_commits = ingester.fetch_github_commits(GITHUB_REPO, since_days=7)
        # print(f"Found {len(new_commits)} new commits.")

        # Example: Fetch all historical commits (batch mode)
        # historical_commits = ingester.fetch_github_commits(GITHUB_REPO, batch_mode=True)
        # print(f"Found {len(historical_commits)} historical commits.")

        # Example: Fetch Notion notes
        # if NOTION_TOKEN and NOTION_DATABASE_ID != 'your_notion_database_id':
        #     notion_notes = ingester.fetch_notion_notes(NOTION_DATABASE_ID, since_date=datetime.now() - timedelta(days=30))
        #     print(f"Found {len(notion_notes)} Notion notes.")
        # else:
        #     print("Notion token or database ID not set. Skipping Notion example.")

        print("Processed SHAs:", ingester.get_processed_shas())
