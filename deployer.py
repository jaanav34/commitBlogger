
"""
Deployer Module: Handles pushing the static HTML files to a GitHub Pages branch.
"""

import os
import subprocess

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

    def _run_git_command(self, command: list) -> tuple[int, str, str]:
        """
        Helper to run a git command in the specified local repository path.

        Args:
            command (list): A list of strings representing the git command and its arguments.

        Returns:
            tuple[int, str, str]: A tuple containing the return code, stdout, and stderr.
        """
        full_command = ["git"] + command
        print(f"Executing command: {" ".join(full_command)} in {self.local_repo_path}")
        process = subprocess.run(
            full_command,
            cwd=self.local_repo_path,
            capture_output=True,
            text=True,
            check=False # Do not raise exception for non-zero exit codes immediately
        )
        if process.returncode != 0:
            print(f"Git command failed with error: {process.stderr}")
        return process.returncode, process.stdout, process.stderr

    def initialize_repo(self) -> bool:
        """
        Initializes a Git repository in the static files directory if it doesn't exist,
        and sets up the remote.

        Returns:
            bool: True if successful, False otherwise.
        """
        # Check if .git directory exists
        if not os.path.exists(os.path.join(self.local_repo_path, ".git")):
            print(f"Initializing new Git repository in {self.local_repo_path}")
            retcode, stdout, stderr = self._run_git_command(["init"])
            if retcode != 0: return False

            print(f"Adding remote origin: {self.github_repo_url}")
            retcode, stdout, stderr = self._run_git_command(["remote", "add", "origin", self.github_repo_url])
            if retcode != 0: return False
        else:
            print(f"Git repository already exists in {self.local_repo_path}")
            # Ensure remote is correct if it already exists
            retcode, stdout, stderr = self._run_git_command(["remote", "set-url", "origin", self.github_repo_url])
            if retcode != 0: print(f"Warning: Could not set remote URL. Error: {stderr}")

        # Ensure we are on the correct branch
        retcode, stdout, stderr = self._run_git_command(["checkout", "-B", self.branch])
        if retcode != 0: 
            print(f"Error checking out/creating branch {self.branch}: {stderr}")
            return False
        
        return True

    def deploy(self, commit_message: str = "Automated blog update") -> bool:
        """
        Adds all files, commits them, and pushes to the GitHub Pages branch.

        Args:
            commit_message (str): The commit message to use.

        Returns:
            bool: True if deployment was successful, False otherwise.
        """
        print(f"Deploying static files from {self.local_repo_path} to {self.github_repo_url}/{self.branch}")

        if not self.initialize_repo():
            print("Failed to initialize/prepare Git repository.")
            return False

        # Add all files
        retcode, stdout, stderr = self._run_git_command(["add", "."])
        if retcode != 0: return False

        # Commit changes
        retcode, stdout, stderr = self._run_git_command(["commit", "-m", commit_message])
        # If no changes to commit, git commit returns non-zero, but it's not an error for us
        if retcode != 0 and "nothing to commit" not in stderr and "nothing to commit" not in stdout:
            print(f"Error committing changes: {stderr}")
            return False
        elif "nothing to commit" in stderr or "nothing to commit" in stdout:
            print("No changes to commit. Skipping push.")
            return True # Consider it successful if nothing to commit

        # Force push to the gh-pages branch
        # TODO: Consider a safer push strategy if history preservation is critical
        # For gh-pages, force push is common to keep the branch clean.
        retcode, stdout, stderr = self._run_git_command(["push", "origin", self.branch, "--force"])
        if retcode != 0: return False

        print("Deployment to GitHub Pages successful.")
        return True

# Example Usage (for testing purposes, will be removed in final main.py)
if __name__ == '__main__':
    # These would typically come from environment variables
    STATIC_EXPORT_PATH = os.getenv("STATIC_EXPORT_PATH", "/tmp/simply-static-export")
    GITHUB_PAGES_REPO_URL = os.getenv("GITHUB_PAGES_REPO_URL", "https://github.com/YOUR_USERNAME/YOUR_REPO.git")

    if not os.path.exists(STATIC_EXPORT_PATH):
        print(f"Creating dummy static export path: {STATIC_EXPORT_PATH}")
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



