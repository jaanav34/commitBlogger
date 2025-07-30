
"""
Deployer Module: Handles pushing the static HTML files to a GitHub Pages branch.
"""

import os
import subprocess
import logging
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, before_log, after_log, before_sleep_log

# Configure logging for this module
logger = logging.getLogger(__name__)

class Deployer:
    """
    Manages the deployment of static files to GitHub Pages via Git commands.
    Assumes the target repository is already set up for GitHub Pages (e.g., gh-pages branch).
    """

    def __init__(self, local_repo_path: str, github_repo_url: str, branch: str = "gh-pages"):
        """
        Initializes the Deployer.

        Args:
            local_repo_path (str): The local path to the directory containing the static files
                                   (this will be treated as a Git repository).
            github_repo_url (str): The URL of the GitHub repository (e.g., https://github.com/YOUR_USERNAME/YOUR_REPO.git).
            branch (str): The branch to push to for GitHub Pages. Defaults to "gh-pages".
        """
        self.local_repo_path = local_repo_path
        self.github_repo_url = github_repo_url
        self.branch = branch

        if not os.path.exists(self.local_repo_path):
            raise FileNotFoundError(f"Local repository path does not exist: {self.local_repo_path}")

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10),
           stop=stop_after_attempt(3),
           retry=retry_if_exception_type(subprocess.CalledProcessError),
           before_sleep=before_sleep_log(logger, logging.INFO),
           after=after_log(logger, logging.WARNING))
    def _run_git_command(self, command: list) -> tuple[int, str, str]:
        """
        Helper to run a git command in the specified local repository path.
        Raises subprocess.CalledProcessError on non-zero exit codes.

        Args:
            command (list): A list of strings representing the git command and its arguments.

        Returns:
            tuple[int, str, str]: A tuple containing the return code, stdout, and stderr.
        """
        full_command = ["git"] + command
        logger.info(f"Executing command: {' '.join(full_command)} in {self.local_repo_path}")
        try:
            process = subprocess.run(
                full_command,
                cwd=self.local_repo_path,
                capture_output=True,
                text=True,
                check=True # Raise CalledProcessError for non-zero exit codes
            )
            return process.returncode, process.stdout, process.stderr
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed with error: {e.stderr}")
            raise # Re-raise to trigger retry
        except FileNotFoundError:
            logger.critical("Git command not found. Please ensure Git is installed and in your PATH.")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during git command execution: {e}", exc_info=True)
            raise

    def initialize_repo(self) -> bool:
        """
        Initializes a Git repository in the static files directory if it doesn't exist,
        and sets up the remote.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Check if .git directory exists
            if not os.path.exists(os.path.join(self.local_repo_path, ".git")):
                logger.info(f"Initializing new Git repository in {self.local_repo_path}")
                self._run_git_command(["init"])

                logger.info(f"Adding remote origin: {self.github_repo_url}")
                self._run_git_command(["remote", "add", "origin", self.github_repo_url])
            else:
                logger.info(f"Git repository already exists in {self.local_repo_path}")
                # Ensure remote is correct if it already exists
                try:
                    self._run_git_command(["remote", "set-url", "origin", self.github_repo_url])
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Could not set remote URL. Error: {e.stderr}")

            # Ensure we are on the correct branch
            # -B creates the branch if it doesn't exist, or resets it if it does
            self._run_git_command(["checkout", "-B", self.branch])
            
            return True
        except Exception as e:
            logger.error(f"Failed to initialize/prepare Git repository: {e}", exc_info=True)
            return False

    def deploy(self, commit_message: str = "Automated blog update") -> bool:
        """
        Adds all files, commits them, and pushes to the GitHub Pages branch.

        Args:
            commit_message (str): The commit message to use.

        Returns:
            bool: True if deployment was successful, False otherwise.
        """
        logger.info(f"Deploying static files from {self.local_repo_path} to {self.github_repo_url}/{self.branch}")

        if not self.initialize_repo():
            logger.error("Failed to initialize/prepare Git repository. Aborting deployment.")
            return False

        try:
            # Add all files
            self._run_git_command(["add", "."])

            # Commit changes
            # Check if there are any changes to commit before attempting to commit
            status_code, status_stdout, status_stderr = self._run_git_command(["status", "--porcelain"])
            if not status_stdout.strip():
                logger.info("No changes to commit. Skipping push.")
                return True # Consider it successful if nothing to commit

            self._run_git_command(["commit", "-m", commit_message])

            # Force push to the gh-pages branch
            # For gh-pages, force push is common to keep the branch clean and simple.
            # If history preservation were critical, a different strategy (e.g., fetch, rebase, push) would be needed.
            self._run_git_command(["push", "origin", self.branch, "--force"])

            logger.info("Deployment to GitHub Pages successful.")
            return True
        except subprocess.CalledProcessError:
            logger.error("Git command failed during deployment. Check logs for details.")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during deployment: {e}", exc_info=True)
            return False

# Example Usage (for testing purposes, will be removed in final main.py)
if __name__ == '__main__':
    # These would typically come from environment variables
    STATIC_EXPORT_PATH = os.getenv("SIMPLY_STATIC_EXPORT_PATH", "/tmp/simply-static-export")
    GITHUB_PAGES_REPO_URL = os.getenv("GITHUB_PAGES_REPO_URL", "https://github.com/YOUR_USERNAME/YOUR_REPO.git")

    # Create a dummy static export path for testing
    if not os.path.exists(STATIC_EXPORT_PATH):
        logger.info(f"Creating dummy static export path: {STATIC_EXPORT_PATH}")
        os.makedirs(STATIC_EXPORT_PATH, exist_ok=True)
        with open(os.path.join(STATIC_EXPORT_PATH, "index.html"), "w") as f:
            f.write("<h1>Hello from Automated Blog!</h1>")
        with open(os.path.join(STATIC_EXPORT_PATH, "style.css"), "w") as f:
            f.write("body { font-family: sans-serif; }")

    deployer = Deployer(
        local_repo_path=STATIC_EXPORT_PATH,
        github_repo_url=GITHUB_PAGES_REPO_URL
    )

    # Example: Deploy the static files
    # if deployer.deploy():
    #     print("Deployment script ran successfully.")
    # else:
    #     print("Deployment script failed.")
