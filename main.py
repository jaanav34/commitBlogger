
"""
main.py: Orchestrates the Automated Blog Generator pipeline.
This script handles the overall flow, including argument parsing for batch/incremental modes,
and integrates the ingestion, transformation, publishing, exporting, and deployment modules.
"""

import argparse
import os
import logging
from datetime import datetime, timedelta

# Import modules
from ingest import Ingester
from transform import Transformer
from publisher import Publisher
from exporter import Exporter
from deployer import Deployer

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def load_env_variables():
    """
    Loads environment variables. In a real scenario, you might use python-dotenv here.
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
            logging.error(f"Missing required environment variable: {var}")
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

def run_pipeline(mode: str, since_days: int = 7):
    """
    Runs the automated blog generation pipeline.

    Args:
        mode (str): 'batch' to process all historical commits, 'incremental' for new commits.
        since_days (int): Number of days to look back for incremental mode.
    """
    logging.info(f"Starting Automated Blog Generator pipeline in {mode} mode...")

    config = load_env_variables()

    # Initialize modules
    ingester = Ingester(
        github_token=config["github_token"],
        notion_token=config["notion_token"],
        state_file="processed_state.json"
    )
    transformer = Transformer(gemini_api_key=config["gemini_api_key"])
    publisher = Publisher(
        xmlrpc_url=config["wp_xmlrpc_url"],
        username=config["wp_username"],
        app_password=config["wp_app_password"]
    )
    exporter = Exporter(
        wordpress_url=config["wp_url"],
        simply_static_export_trigger_url=config["simply_static_trigger_url"],
        export_path=config["simply_static_export_path"]
    )
    deployer = Deployer(
        local_repo_path=config["simply_static_export_path"],
        github_repo_url=config["github_pages_repo_url"]
    )

    # --- Ingestion Phase ---
    logging.info("Ingestion Phase: Fetching data...")
    commits_to_process = []
    if mode == "batch":
        commits_to_process = ingester.fetch_github_commits(config["github_repo"], batch_mode=True)
    elif mode == "incremental":
        commits_to_process = ingester.fetch_github_commits(config["github_repo"], since_days=since_days)
    else:
        logging.error(f"Invalid mode: {mode}. Use 'batch' or 'incremental'.")
        return

    # TODO: Add Notion ingestion here once implemented in ingest.py
    # notion_notes = ingester.fetch_notion_notes(config["notion_database_id"])

    if not commits_to_process:
        logging.info("No new commits to process. Exiting pipeline.")
        return

    # --- Transformation & Publishing Phase ---
    logging.info(f"Transformation & Publishing Phase: Processing {len(commits_to_process)} commits...")
    for commit_data in commits_to_process:
        try:
            logging.info(f"Processing commit: {commit_data["sha"][:8]} - {commit_data["message"].splitlines()[0]}")
            
            # Generate content
            blog_post_content = transformer.generate_blog_post(
                commit_data["message"],
                commit_data["files"],
                # notion_content # TODO: Pass relevant notion content here
            )
            linkedin_summary = transformer.generate_linkedin_summary(
                commit_data["message"],
                commit_data["files"],
                # notion_content # TODO: Pass relevant notion content here
            )
            blog_post_title = transformer.generate_click_worthy_title(
                commit_data["message"],
                blog_post_content
            )

            if not blog_post_content or not blog_post_title:
                logging.warning(f"Skipping commit {commit_data["sha"][:8]} due to empty generated content or title.")
                continue

            # Publish to WordPress
            post_id = publisher.publish_post(
                title=blog_post_title,
                content_md=blog_post_content,
                tags=["automated", "github", "gemini"], # Example tags
                categories=["Development"] # Example category
            )

            if post_id:
                logging.info(f"Successfully published blog post for commit {commit_data["sha"][:8]}. Post ID: {post_id}")
                # TODO: Optionally save LinkedIn summary to a file or database for later manual posting
            else:
                logging.error(f"Failed to publish blog post for commit {commit_data["sha"][:8]}.")

        except Exception as e:
            logging.error(f"Error processing commit {commit_data["sha"][:8]}: {e}", exc_info=True)
            # TODO: Implement retry logic here for individual commit processing failures

    # --- Export & Deployment Phase ---
    logging.info("Export & Deployment Phase: Generating static site and deploying...")
    try:
        if exporter.trigger_simply_static_export():
            if exporter.wait_for_export_completion():
                logging.info("Simply Static export completed. Proceeding to deployment.")
                if deployer.deploy(commit_message="Automated blog update from pipeline"): # Use a generic commit message for deployment
                    logging.info("Static site successfully deployed to GitHub Pages.")
                else:
                    logging.error("Failed to deploy static site to GitHub Pages.")
            else:
                logging.error("Simply Static export did not complete in time.")
        else:
            logging.error("Failed to trigger Simply Static export.")
    except Exception as e:
        logging.error(f"Error during export or deployment phase: {e}", exc_info=True)

    logging.info("Automated Blog Generator pipeline finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Blog Generator Pipeline.")
    parser.add_argument(
        "--mode", 
        type=str, 
        choices=["batch", "incremental"], 
        default="incremental",
        help="Operation mode: 'batch' for historical commits, 'incremental' for new commits."
    )
    parser.add_argument(
        "--since_days", 
        type=int, 
        default=7, 
        help="Number of days to look back for commits in incremental mode. Default is 7."
    )
    args = parser.parse_args()

    run_pipeline(args.mode, args.since_days)



