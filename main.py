
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
import asyncio
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
    # Central config loading
    config = {
        "github_token": os.getenv("GITHUB_TOKEN"),
        "github_repo": os.getenv("GITHUB_REPO"),
        "gemini_api_key": os.getenv("GEMINI_API_KEY"),
        "notion_token": os.getenv("NOTION_TOKEN"),
        "notion_database_id": os.getenv("NOTION_DATABASE_ID"),
        "wp_url": os.getenv("WP_URL"),
        "wp_xmlrpc_url": os.getenv("WP_XMLRPC_URL"),
        "wp_username": os.getenv("WP_USERNAME"),
        "wp_app_password": os.getenv("WP_APP_PASSWORD"),
        "simply_static_export_path": os.getenv("SIMPLY_STATIC_EXPORT_PATH"),
        "simply_static_trigger_url": os.getenv("SIMPLY_STATIC_TRIGGER_URL"),
        "github_pages_repo_url": os.getenv("GITHUB_PAGES_REPO_URL"),
        # Model configurations with defaults
        'model_configs': {
            'blog': {
                'name': os.getenv("GEMINI_BLOG_MODEL", "gemini-2.5-flash"),
                'rpm': int(os.getenv("GEMINI_BLOG_RPM", "10")),
                'tpm': int(os.getenv("GEMINI_BLOG_TPM", "250000"))
            },
            'summary': {
                'name': os.getenv("GEMINI_SUMMARY_MODEL", "gemini-2.5-flash-lite"),
                'rpm': int(os.getenv("GEMINI_SUMMARY_RPM", "15")),
                'tpm': int(os.getenv("GEMINI_SUMMARY_TPM", "250000"))
            },
            'linkedin': {
                'name': os.getenv("GEMINI_LINKEDIN_MODEL", "gemini-2.5-flash"),
                'rpm': int(os.getenv("GEMINI_LINKEDIN_RPM", "10")),
                'tpm': int(os.getenv("GEMINI_LINKEDIN_TPM", "250000"))
            },
            'title': {
                'name': os.getenv("GEMINI_TITLE_MODEL", "gemma-3-27b-it"),
                'rpm': int(os.getenv("GEMINI_TITLE_RPM", "30")),
                'tpm': int(os.getenv("GEMINI_TITLE_TPM", "15000"))
            }
        }
    }

    required_vars = [
        "github_token", "github_repo", "gemini_api_key", "wp_xmlrpc_url",
        "wp_username", "wp_app_password", "simply_static_export_path",
        "github_pages_repo_url"
    ]

    for var in required_vars:
        if not config.get(var):
            logger.error(f"Missing required environment variable: {var.upper()}")
            exit(1)
    
    return config


@retry(wait=wait_exponential(multiplier=1, min=4, max=10),
       stop=stop_after_attempt(3),
       before_sleep=before_log(logger, logging.INFO),
       after=after_log(logger, logging.WARNING))
async def process_single_commit(commit_data: dict, transformer: Transformer, publisher: Publisher, linkedin_summary_dir: str):
    """
    Processes a single commit: generates content and publishes to WordPress.
    """
    logger.info(f"Processing commit: {commit_data['sha'][:8]} - {commit_data['message'].splitlines()[0]}")
    
    # TODO: Integrate Notion content here if relevant to the commit
    notion_content = "" # Placeholder for now
    linkedin_summary = None
    # Generate content
    blog_post_content = await transformer.generate_blog_post(
        commit_data['message'],
        commit_data["files"],
        notion_content
    )
    #linkedin_summary = await transformer.generate_linkedin_summary(
    #    commit_data['message'],
    #    commit_data["files"],
    #    notion_content
    #)
    blog_post_title = await transformer.generate_click_worthy_title(
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

async def run_pipeline(mode: str, since_days: int = 7):
    """
    Runs the automated blog generation pipeline.

    Args:
        mode (str): 'batch' to process all historical commits, 'incremental' for new commits.
        since_days (int): Number of days to look back for incremental mode.
    """
    logger.info(f"Starting Automated Blog Generator pipeline in {mode} mode...")

    config = load_env_variables()

    if mode == 'export':
        logger.info("Running in export-only mode.")
        # Instantiate only necessary modules for export and deployment
        exporter = Exporter(
            wordpress_url=config["wp_url"], # type: ignore
            simply_static_export_trigger_url=config["simply_static_trigger_url"], # type: ignore
            export_path=config["simply_static_export_path"] # type: ignore
        )
        deployer = Deployer(
            local_repo_path=config["simply_static_export_path"], # type: ignore
            github_repo_url=config["github_pages_repo_url"] # type: ignore
        )

        logger.info("Triggering static site export and deployment...")
        try:
            trigger_url = config.get("simply_static_trigger_url")
            if trigger_url:
                # Remote-trigger flow (when URL is provided)
                if exporter.trigger_simply_static_export():
                    if exporter.wait_for_export_completion():
                        logger.info("Simply Static export completed via trigger URL. Proceeding to deployment.")
                    else:
                        logger.error("Simply Static export did not complete in time.")
                        return
                else:
                    logger.error("Failed to trigger Simply Static export via URL.")
                    return
            else:
                # No trigger URL: assume static-export folder is already populated
                logger.info("No Simply Static trigger URL provided; using pre-exported files at: "
                            f"{config['simply_static_export_path']}")

            # Deploy whatever is in the export folder
            if deployer.deploy(commit_message="Automated blog update from pipeline"):
                logger.info("Static site successfully deployed to GitHub Pages.")
            else:
                logger.error("Failed to deploy static site to GitHub Pages.")
        except Exception as e:
            logger.error(f"Error during export or deployment phase: {e}", exc_info=True)
        
        logger.info("Export-only mode finished.")
        return # Exit the pipeline early

    # Initialize modules
    ingester = Ingester(
        github_token=config["github_token"], # type: ignore
        notion_token=config["notion_token"], # type: ignore
        state_file="processed_state.json"
    )
    transformer = Transformer(
        gemini_api_key=config["gemini_api_key"], # type: ignore
        model_configs=config["model_configs"] # type: ignore
    )
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

    logger.info(f"Transformation & Publishing Phase: Processing {len(commits_to_process)} commits...")
    posts_were_published = False
    linkedin_summary_output_dir = "linkedin_summaries"
    blog_cache_dir = "generated_blogs"
    os.makedirs(blog_cache_dir, exist_ok=True)
    
    aggregated_context = ""

    # 3. Iterate through every commit sequentially.
    for commit_data in commits_to_process:
        short_sha = commit_data['sha'][:7]
        commit_message_subject = commit_data['message'].splitlines()[0]
        blog_cache_path = os.path.join(blog_cache_dir, f"blog_{short_sha}.md")

        # A. Check ignore list
        if "ignore" in commit_message_subject.lower():
            logger.info(f"Skipping commit {short_sha} because 'ignore' was found in the commit message.")
            continue

        # B. Check cache
        if os.path.exists(blog_cache_path):
            logger.info(f"Found cached blog post for commit {short_sha}. Loading from cache.")
            with open(blog_cache_path, "r", encoding="utf-8") as f:
                blog_post_content = f.read()
            # Add to context and continue to next commit
            aggregated_context += f"\n\n--- Blog Post for Commit {short_sha} ---\n{blog_post_content}"
            continue

        # C. Process the commit (if not ignored or cached)
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
            # Generate content asynchronously
            blog_post_content = await transformer.generate_blog_post(
                commit_message=commit_data['message'],
                files_changed=commit_data["files"],
                notion_content=notion_content,
                aggregated_context=aggregated_context
            )
            
            if not blog_post_content:
                logger.warning(f"Skipping commit {short_sha} due to empty generated blog content.")
                continue

            # These can run concurrently after the main blog post is done
            title_task = transformer.generate_click_worthy_title(
                commit_message=commit_data['message'],
                blog_post_content=blog_post_content
            )
            linkedin_task = transformer.generate_linkedin_summary(
                commit_message=commit_data['message'],
                files_changed=commit_data["files"],
                notion_content=notion_content
            )
            
            blog_post_title, linkedin_summary = await asyncio.gather(title_task, linkedin_task)

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
                
                # Cache the successful post
                with open(blog_cache_path, "w", encoding="utf-8") as f:
                    f.write(blog_post_content)
                logger.info(f"Blog post for {short_sha} cached successfully.")

                # Add to context for the next iteration
                aggregated_context += f"\n\n--- Blog Post for Commit {short_sha} ---\n{blog_post_content}"

                # Mark commit as processed only after successful publication and caching
                ingester.mark_as_processed(commit_data['sha'])

                # Save LinkedIn summary
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
            trigger_url = config.get("simply_static_trigger_url")
            if trigger_url:
                # Remote-trigger flow (when URL is provided)
                if exporter.trigger_simply_static_export():
                    if exporter.wait_for_export_completion():
                        logger.info("Simply Static export completed via trigger URL. Proceeding to deployment.")
                    else:
                        logger.error("Simply Static export did not complete in time.")
                        return
                else:
                    logger.error("Failed to trigger Simply Static export via URL.")
                    return
            else:
                # No trigger URL: assume static-export folder is already populated
                logger.info("No Simply Static trigger URL provided; using pre-exported files at: "
                            f"{config['simply_static_export_path']}")

            # Deploy whatever is in the export folder
            if deployer.deploy(commit_message="Automated blog update from pipeline"):
                logger.info("Static site successfully deployed to GitHub Pages.")
            else:
                logger.error("Failed to deploy static site to GitHub Pages.")
        except Exception as e:
            logger.error(f"Error during export or deployment phase: {e}", exc_info=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Blog Generator Pipeline.")
    parser.add_argument(
        "--mode", 
        type=str, 
        choices=["batch", "incremental", "export"], 
        default="incremental",
        help="Operation mode: 'batch' for historical, 'incremental' for new, 'export' to only run the static site export and deployment."
    )
    parser.add_argument(
        "--since_days", 
        type=int, 
        default=7, 
        help="Number of days to look back for commits/notes in incremental mode. Default is 7."
    )
    args = parser.parse_args()

    asyncio.run(run_pipeline(args.mode, args.since_days))