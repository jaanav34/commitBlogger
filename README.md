# CommitBlogger: Automated AI-Powered Blog Post Generator

CommitBlogger is a sophisticated, AI-powered pipeline that transforms your git commits into engaging, high-quality blog posts. It automates the entire content creation workflow, from ingesting technical data to publishing polished articles, allowing you to focus on coding while your blog writes itself.

-----

## Overview

This project is designed for developers, students, and tech enthusiasts who want to maintain an active blog without the time-consuming process of manual content creation. By leveraging the power of Large Language Models (LLMs), CommitBlogger intelligently analyzes your code changes, git commit messages, and supplementary notes from Notion to generate well-structured, insightful, and ready-to-publish blog posts.

The pipeline is designed to be a "fire-and-forget" system. Once configured, it can be scheduled to run automatically, ensuring a consistent stream of content for your audience.

-----

## Key Features

  * **Automated Content Generation**: Utilizes the Gemini API to create detailed blog posts, concise LinkedIn summaries, and SEO-friendly titles from your git commits.
  * **Context-Aware Narratives**: Integrates with Notion to pull in high-level context, ensuring that the generated content tells a compelling story beyond just the technical details.
  * **Intelligent Content Pipeline**: Fetches commits, generates content, and publishes to WordPress in a seamless, automated workflow.
  * **Static Site Generation**: Integrates with the Simply Static WordPress plugin to export your blog as a fast, secure, and easily deployable static website.
  * **Automated Deployment**: Pushes the generated static site to GitHub Pages, making your content instantly available to the world.
  * **Idempotent & Resilient**: Built with robust error handling, retry mechanisms, and state management to prevent duplicate posts and gracefully handle API or network failures.
  * **Flexible Operating Modes**:
      * **Incremental Mode**: Processes only new commits since the last run, perfect for daily scheduling.
      * **Batch Mode**: Ingests your entire git history to generate a comprehensive blog from past work.
      * **Repost Mode**: Republishes cached blog posts, ideal for migrating content or recovering from errors.

-----

## Getting Started

### Prerequisites

  * Python 3.8+
  * Git installed and configured in your system's PATH.
  * A GitHub account with a personal access token.
  * A self-hosted WordPress instance (e.g., using LocalWP).
  * The "Simply Static" plugin installed and activated on your WordPress site.
  * A Google AI Studio (Gemini) API key.
  * (Optional) A Notion account with an integration token and a database for supplementary notes.

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/your-username/CommitBlogger.git
    cd CommitBlogger
    ```

2.  **Install the required dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

-----

## Configuration

The application is configured using environment variables. Create a `.env` file in the root of the project and populate it with the following:

```env
# GitHub Configuration
GITHUB_TOKEN="your_github_personal_access_token"
GITHUB_REPO="your_github_username/your_repo_name"
GITHUB_REPO_NAME="Your Project Name" # e.g., "AI Teleprompter"

# Google AI Studio (Gemini) Configuration
GEMINI_API_KEY="your_gemini_api_key"

# (Optional) Notion Configuration
NOTION_TOKEN="your_notion_integration_token"
NOTION_DATABASE_ID="your_notion_database_id"

# WordPress Configuration
WP_URL="http://your-local-site.local"
WP_XMLRPC_URL="http://your-local-site.local/xmlrpc.php"
WP_USERNAME="your_wordpress_username"
WP_APP_PASSWORD="your_wordpress_application_password"

# Simply Static & Deployment Configuration
SIMPLY_STATIC_EXPORT_PATH="/path/to/your/local/static/export/folder"
GITHUB_PAGES_REPO_URL="https://github.com/your_github_username/your_pages_repo.git"
# (Optional) If you can trigger Simply Static via a URL
SIMPLY_STATIC_TRIGGER_URL="http://your-local-site.local/?simply_static_export=1"
```

For detailed instructions on obtaining these credentials, please refer to the [Configuration and State Management Guide](https://www.google.com/search?q=guides/Configuration%2520and%2520State%2520Management%2520Guide.md).

-----

## Usage

The pipeline is controlled via the `main.py` script and can be run in several modes:

### Incremental Mode (Default)

This is the standard mode for daily operation. It fetches and processes only the new commits since the last run.

```bash
python main.py --mode incremental --since_days 7
```

### Batch Mode

Use this mode for the initial setup to process your entire commit history.

```bash
python main.py --mode batch
```

### Repost Mode

This mode is useful for republishing all previously generated (and cached) blog posts to WordPress. This is helpful for testing or disaster recovery.

```bash
python main.py --mode repost
```

### Scheduling

For automated execution, you can set up a cron job (Linux/macOS) or a Task Scheduler job (Windows). Refer to the [Scheduling and Error Handling Strategies](https://www.google.com/search?q=guides/Scheduling%2520and%2520Error%2520Handling%2520Strategies.md) guide for detailed instructions.

-----

## Architecture Overview

CommitBlogger follows a modular, five-stage pipeline:

1.  **Ingestion**: Fetches commit data from GitHub and supplementary notes from Notion.
2.  **Transformation**: Uses the Gemini API to generate blog content, titles, and summaries.
3.  **Publishing**: Posts the generated content to a local WordPress instance.
4.  **Export**: Triggers the Simply Static plugin to generate a static HTML version of the site.
5.  **Deployment**: Pushes the static files to a specified GitHub Pages repository.

For a detailed breakdown of the architecture, please see the [Architecture Diagram](https://www.google.com/search?q=guides/Architecture%2520Diagram_%2520Automated%2520Blog%2520Generator%2520Pipeline.md).

-----

## Troubleshooting

  * **UnicodeEncodeError on Windows**: This is a common issue related to file encodings. The script is configured to use UTF-8, which should resolve most problems.
  * **WordPress Markdown Issues**: The pipeline now automatically converts Markdown to HTML before publishing to ensure proper rendering.
  * **AI Content Quality**: The quality of the generated blog posts is highly dependent on the quality of your commit messages and Notion notes. Clear, descriptive messages and detailed notes will produce the best results.

-----

## Future Work

  * Integration with other knowledge sources (e.g., local files, web URLs).
  * Advanced customization options for blog post templates and styles.
  * A more sophisticated UI for managing the content generation process.
