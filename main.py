
"""
main.py: Orchestrates the Automated Blog Generator pipeline.
This script handles the overall flow, including argument parsing for batch/incremental modes,
and integrates the ingestion, transformation, publishing, exporting, and deployment modules.
"""

import argparse
import os
import logging
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv # For loading environment variables from .env file
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, before_log, after_log

# Import modules
from ingest import Ingester
from transform import Transformer
from publisher import Publisher
from exporter import Exporter
from deployer import Deployer

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_env_variables():
    """
    Loads and validates environment variables.
    """
    # GitHub
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo = os.getenv("GITHUB_REPO")

    # Gemini
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    # Notion (Optional)
    notion_token = os.getenv("NOTION_TOKEN")
    notion_database_id = os.getenv("NOTION_DATABASE_ID")

    # WordPress
    wp_url = os.getenv("WP_URL")
    wp_xmlrpc_url = os.getenv("WP_XMLRPC_URL")
    wp_username = os.getenv("WP_USERNAME")
    wp_app_password = os.getenv("WP_APP_PASSWORD")

    # Simply Static & Deployment
    simply_static_export_path = os.getenv("SIMPLY_STATIC_EXPORT_PATH")
    simply_static_trigger_url = os.getenv("SIMPLY_STATIC_TRIGGER_URL")
    github_pages_repo_url = os.getenv("GITHUB_PAGES_REPO_URL")

    required_vars = {
        "GITHUB_TOKEN": github_token,
        "GITHUB_REPO": github_repo,
        "GEMINI_API_KEY": gemini_api_key,
        "WP_XMLRPC_URL": wp_xmlrpc_url,
        "WP_USERNAME": wp_username,
        "WP_APP_PASSWORD": wp_app_password,
        "SIMPLY_STATIC_EXPORT_PATH": simply_static_export_path,
        "GITHUB_PAGES_REPO_URL": github_pages_repo_url,
    }

    for var, value in required_vars.items():
        if not value:
            logger.error(f"Missing required environment variable: {var}")
            exit(1)

    return {
        "github_token": github_token,
        "github_repo": github_repo,
        "gemini_api_key": gemini_api_key,
        "notion_token": notion_token,
        "notion_database_id": notion_database_id,
        "wp_url": wp_url,
        "wp_xmlrpc_url": wp_xmlrpc_url,
        "wp_username": wp_username,
        "wp_app_password": wp_app_password,
        "simply_static_export_path": simply_static_export_path,
        "simply_static_trigger_url": simply_static_trigger_url,
        "github_pages_repo_url": github_pages_repo_url,
    }

@retry(wait=wait_exponential(multiplier=1, min=4, max=10),
       stop=stop_after_attempt(3),
       before_sleep=before_log(logger, logging.INFO),
       after=after_log(logger, logging.WARNING))
def process_single_commit(commit_data: dict, transformer: Transformer, publisher: Publisher, linkedin_summary_dir: str):
    """
    Processes a single commit: generates content and publishes to WordPress.
    """
    logger.info(f"Processing commit: {commit_data['sha'][:8]} - {commit_data['message'].splitlines()[0]}")
    
    # TODO: Integrate Notion content here if relevant to the commit
    notion_content = "" # Placeholder for now
    linkedin_summary = None
    # Generate content
    blog_post_content = transformer.generate_blog_post(
        commit_data['message'],
        commit_data["files"],
        notion_content
    )
    #linkedin_summary = transformer.generate_linkedin_summary(
    #    commit_data['message'],
    #    commit_data["files"],
    #    notion_content
    #)
    blog_post_title = transformer.generate_click_worthy_title(
        commit_data['message'],
        blog_post_content
    )

    if not blog_post_content or not blog_post_title:
        logger.warning(f"Skipping commit {commit_data['sha'][:8]} due to empty generated content or title.")
        return

    # Publish to WordPress
    post_id = publisher.publish_post(
        title=blog_post_title,
        content_md=blog_post_content,
        tags=["automated", "github", "gemini"], # Example tags
        categories=["Development"] # Example category
    )

    if post_id:
        logger.info(f"Successfully published blog post for commit {commit_data['sha'][:8]}. Post ID: {post_id}")
        # Save LinkedIn summary to a file
        if linkedin_summary is not None:
            summary_filename = os.path.join(linkedin_summary_dir, f"linkedin_summary_{commit_data['sha'][:8]}.md")
            os.makedirs(linkedin_summary_dir, exist_ok=True)
            with open(summary_filename, "w", encoding="utf-8") as f:
                f.write(f"# LinkedIn Summary for Commit {commit_data['sha'][:8]}\n\n")
                f.write(linkedin_summary)
            logger.info(f"LinkedIn summary saved to {summary_filename}")
    else:
        logger.error(f"Failed to publish blog post for commit {commit_data['sha'][:8]}.")

def run_pipeline(mode: str, since_days: int = 7):
    """
    Runs the automated blog generation pipeline.

    Args:
        mode (str): 'batch' to process all historical commits, 'incremental' for new commits.
        since_days (int): Number of days to look back for incremental mode.
    """
    logger.info(f"Starting Automated Blog Generator pipeline in {mode} mode...")

    config = load_env_variables()

    # Initialize modules
    ingester = Ingester(
        github_token=config["github_token"], # type: ignore
        notion_token=config["notion_token"], # type: ignore
        state_file="processed_state.json"
    )
    transformer = Transformer(gemini_api_key=config["gemini_api_key"]) # type: ignore
    publisher = Publisher(
        xmlrpc_url=config["wp_xmlrpc_url"], # type: ignore
        username=config["wp_username"], # type: ignore
        app_password=config["wp_app_password"] # type: ignore
    )
    exporter = Exporter(
        wordpress_url=config["wp_url"], # type: ignore
        simply_static_export_trigger_url=config["simply_static_trigger_url"], # type: ignore
        export_path=config["simply_static_export_path"] # type: ignore
    )
    deployer = Deployer(
        local_repo_path=config["simply_static_export_path"], # type: ignore
        github_repo_url=config["github_pages_repo_url"] # type: ignore
    )

    # --- Ingestion Phase ---
    logger.info("Ingestion Phase: Fetching data...")

    # 1. Fetch all recent/unprocessed commits from GitHub. This is our primary source.
    commits_to_process = []
    if mode == "batch":
        commits_to_process = ingester.fetch_github_commits(config["github_repo"], batch_mode=True) # type: ignore
    else: # incremental
        commits_to_process = ingester.fetch_github_commits(config["github_repo"], since_days=since_days) # type: ignore

    # 2. Fetch recent Notion notes to be used as optional enhancements.
    notion_notes_by_sha = {}
    if config["notion_token"] and config["notion_database_id"]:
        notion_since_date = datetime.now() - timedelta(days=since_days) if mode == "incremental" else None
        notion_notes_by_sha = ingester.fetch_notion_notes(config["notion_database_id"], since_date=notion_since_date) # type: ignore

    if not commits_to_process:
        logger.info("No new commits to process. Exiting pipeline.")
        return

    # --- Transformation & Publishing Phase ---
    logger.info(f"Transformation & Publishing Phase: Processing {len(commits_to_process)} commits...")
    posts_were_published = False
    linkedin_summary_output_dir = "linkedin_summaries"

    # 3. Iterate through every commit.
    for commit_data in commits_to_process:
        short_sha = commit_data['sha'][:7]
        
        # Check for a matching Notion note. This is the enhancement.
        matching_note = notion_notes_by_sha.get(short_sha)
        notion_content = ""
        notion_title_for_log = ""
        if matching_note:
            notion_content = matching_note['content']
            notion_title_for_log = matching_note['title']
            logger.info(f"Processing commit {short_sha} - Found matching Notion note: '{notion_title_for_log}'")
        else:
            logger.info(f"Processing commit {short_sha} - No matching Notion note found.")

        try:
            # Generate content using commit data and any available Notion content.
            blog_post_content = transformer.generate_blog_post(
                commit_message=commit_data['message'],
                files_changed=commit_data["files"],
                notion_content=notion_content
            )
            linkedin_summary = transformer.generate_linkedin_summary(
                commit_message=commit_data['message'],
                files_changed=commit_data["files"],
                notion_content=notion_content
            )
            blog_post_title = transformer.generate_click_worthy_title(
                commit_message=commit_data['message'],
                blog_post_content=blog_post_content
            )

            if not blog_post_content or not blog_post_title:
                logger.warning(f"Skipping commit {short_sha} due to empty generated content or title.")
                continue

            # Publish to WordPress
            post_id = publisher.publish_post(
                title=blog_post_title,
                content_md=blog_post_content,
                tags=["automated", "github", "gemini"],
                categories=["Development"]
            )

            if post_id:
                posts_were_published = True
                logger.info(f"Successfully published post for commit {short_sha}. Post ID: {post_id}")
                # Mark commit as processed only after successful publication
                ingester.mark_as_processed(commit_data['sha'])

                # Save LinkedIn summary to a file
                if linkedin_summary:
                    summary_filename = os.path.join(linkedin_summary_output_dir, f"linkedin_summary_{short_sha}.md")
                    os.makedirs(linkedin_summary_output_dir, exist_ok=True)
                    with open(summary_filename, "w", encoding="utf-8") as f:
                        f.write(f"# LinkedIn Summary for Commit {short_sha}\n\n")
                        if notion_title_for_log:
                            f.write(f"Based on Notion Note: \"{notion_title_for_log}\"\n\n")
                        f.write(linkedin_summary)
                    logger.info(f"LinkedIn summary saved to {summary_filename}")
            else:
                logger.error(f"Failed to publish post for commit {short_sha}.")

        except Exception as e:
            logger.error(f"Failed to process commit {short_sha} due to an unexpected error: {e}", exc_info=True)

    # --- Export & Deployment Phase ---
    if posts_were_published:
        logger.info("Export & Deployment Phase: Generating static site and deploying...")
        try:
            if exporter.trigger_simply_static_export():
                if exporter.wait_for_export_completion():
                    logger.info("Simply Static export completed. Proceeding to deployment.")
                    if deployer.deploy(commit_message="Automated blog update from pipeline"):
                        logger.info("Static site successfully deployed to GitHub Pages.")
                    else:
                        logger.error("Failed to deploy static site to GitHub Pages.")
                else:
                    logger.error("Simply Static export did not complete in time.")
            else:
                logger.error("Failed to trigger Simply Static export.")
        except Exception as e:
            logger.error(f"Error during export or deployment phase: {e}", exc_info=True)
    else:
        logger.info("No new posts were published. Skipping export and deployment.")

    logger.info("Automated Blog Generator pipeline finished.")
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Blog Generator Pipeline.")
    parser.add_argument(
        "--mode", 
        type=str, 
        choices=["batch", "incremental"], 
        default="incremental",
        help="Operation mode: \'batch\' for historical commits, \'incremental\' for new commits."
    )
    parser.add_argument(
        "--since_days", 
        type=int, 
        default=7, 
        help="Number of days to look back for commits/notes in incremental mode. Default is 7."
    )
    args = parser.parse_args()

    run_pipeline(args.mode, args.since_days)


