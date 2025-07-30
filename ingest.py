
"""
Ingestion Module: Handles fetching data from GitHub and Notion, and managing processed state.
"""

import os
import json
from datetime import datetime, timedelta
from github import Github
from notion_client import Client

class Ingester:
    """
    Manages data ingestion from GitHub and Notion, and tracks processed items.
    """

    def __init__(self, github_token: str, notion_token: str, state_file: str = 'processed_state.json'):
        """
        Initializes the Ingester with API tokens and state file path.

        Args:
            github_token (str): GitHub personal access token.
            notion_token (str): Notion integration token.
            state_file (str): Path to the JSON file storing processed item SHAs/IDs.
        """
        self.github_client = Github(github_token)
        self.notion_client = Client(auth=notion_token)
        self.state_file = state_file
        self.processed_shas = self._load_processed_shas()

    def _load_processed_shas(self) -> set:
        """
        Loads the set of already processed SHAs from the state file.

        Returns:
            set: A set of processed SHAs.
        """
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return set(json.load(f))
        return set()

    def _save_processed_shas(self):
        """
        Saves the current set of processed SHAs to the state file.
        """
        with open(self.state_file, 'w') as f:
            json.dump(list(self.processed_shas), f)

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
        print(f"Fetching GitHub commits for {repo_name}...")
        repo = self.github_client.get_user().get_repo(repo_name)
        commits_data = []
        
        if batch_mode:
            # TODO: Implement pagination for large number of commits in batch mode
            commits = repo.get_commits()
        else:
            since_date = datetime.now() - timedelta(days=since_days)
            commits = repo.get_commits(since=since_date)

        for commit in commits:
            if not batch_mode and commit.sha in self.processed_shas:
                continue # Skip already processed commits in incremental mode

            try:
                # Fetch full commit details to get file changes (diffs)
                full_commit = repo.get_commit(commit.sha)
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
            except Exception as e:
                print(f"Error processing commit {commit.sha}: {e}")
                # TODO: Implement robust error handling and retry mechanism

        self._save_processed_shas()
        print(f"Fetched {len(commits_data)} new/unprocessed commits.")
        return commits_data

    def fetch_notion_notes(self, database_id: str, since_date: datetime = None) -> list:
        """
        Fetches notes (pages) from a Notion database.

        Args:
            database_id (str): The ID of the Notion database.
            since_date (datetime, optional): Only fetch notes created/updated after this date.

        Returns:
            list: A list of dictionaries, each representing a Notion page with relevant details.
        """
        print(f"Fetching Notion notes from database {database_id}...")
        notes_data = []
        # TODO: Implement Notion API integration to fetch notes.
        # Need to handle pagination and filtering by date/status.
        # Example: results = self.notion_client.databases.query(database_id=database_id)
        # Extract title, content (from blocks), last edited time, etc.
        print("Notion ingestion not yet implemented. Skipping.")
        return notes_data

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

    if not GITHUB_TOKEN or not NOTION_TOKEN:
        print("Please set GITHUB_TOKEN and NOTION_TOKEN environment variables.")
    else:
        ingester = Ingester(github_token=GITHUB_TOKEN, notion_token=NOTION_TOKEN)

        # Example: Fetch commits from the last 7 days (incremental mode)
        # new_commits = ingester.fetch_github_commits(GITHUB_REPO, since_days=7)
        # print(f"Found {len(new_commits)} new commits.")

        # Example: Fetch all historical commits (batch mode)
        # historical_commits = ingester.fetch_github_commits(GITHUB_REPO, batch_mode=True)
        # print(f"Found {len(historical_commits)} historical commits.")

        # Example: Fetch Notion notes (database ID needs to be provided)
        # notion_db_id = "YOUR_NOTION_DATABASE_ID"
        # notion_notes = ingester.fetch_notion_notes(notion_db_id)
        # print(f"Found {len(notion_notes)} Notion notes.")

        print("Processed SHAs:", ingester.get_processed_shas())



