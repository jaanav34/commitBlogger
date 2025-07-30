# Configuration and State Management Guide

This guide details the necessary configuration for the Automated Blog Generator, including environment variables, API scopes, and the strategy for managing state.

## 1. Configuration Guide

### Environment Variables

To securely manage credentials and settings, the application uses environment variables. You can set these directly in your shell or use a `.env` file with a library like `python-dotenv`.

Create a `.env` file in the root of your project with the following variables:

```
# GitHub Configuration
GITHUB_TOKEN="your_github_personal_access_token"
GITHUB_REPO="your_github_username/your_repo_name" # The repository to monitor for commits

# Google AI Studio (Gemini) Configuration
GEMINI_API_KEY="your_gemini_api_key"

# Notion Configuration (Optional)
NOTION_TOKEN="your_notion_integration_token"
NOTION_DATABASE_ID="your_notion_database_id" # The database to pull notes from

# WordPress Configuration
WP_URL="http://your-local-site.local" # Your LocalWP site URL
WP_XMLRPC_URL="http://your-local-site.local/xmlrpc.php" # The XML-RPC endpoint
WP_USERNAME="your_wordpress_username"
WP_APP_PASSWORD="your_wordpress_application_password"

# Simply Static & Deployment Configuration
SIMPLY_STATIC_EXPORT_PATH="/path/to/your/local/static/export/folder" # The folder where Simply Static exports files
GITHUB_PAGES_REPO_URL="https://github.com/your_github_username/your_pages_repo.git" # The repo for GitHub Pages
```

### Required API Scopes and Permissions

#### GitHub Personal Access Token

When creating your GitHub Personal Access Token, you need to grant the following scopes:

*   **`repo`**: Full control of private repositories. This is necessary to read commits, diffs, and to push to the `gh-pages` branch.

#### Google AI Studio (Gemini API)

Your Gemini API key from Google AI Studio does not require specific scopes, but ensure it is enabled and has sufficient quota for your expected usage.

#### WordPress Application Password

To allow the Python script to publish posts, you need to use Application Passwords. You can enable this by installing a plugin like "Application Passwords" or by using the built-in feature in recent WordPress versions.

1.  Go to your WordPress Admin Dashboard.
2.  Navigate to **Users > Your Profile**.
3.  Scroll down to the **Application Passwords** section.
4.  Enter a name for the new application password (e.g., `blog_generator`) and click **Add New Application Password**.
5.  Copy the generated password and store it securely in your `.env` file as `WP_APP_PASSWORD`.

## 2. State Management Strategy

To support both batch processing of historical commits and incremental processing of new commits, the application needs to keep track of which commits have already been processed.

### State File

The state is managed using a simple JSON file named `processed_state.json` located in the project's root directory. This file stores a list of the SHA hashes of all commits that have been successfully processed and turned into blog posts.

**Example `processed_state.json`:**

```json
[
  "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
  "f0e9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4a3b2a1",
  "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"
]
```

### How it Works

1.  **Initialization**: The `ingest.py` module loads the SHAs from `processed_state.json` into a Python `set` for efficient lookups.
2.  **Incremental Mode**: When fetching new commits, the script filters out any commit whose SHA is already present in the `processed_shas` set.
3.  **Batch Mode**: In batch mode, this check is skipped, allowing all historical commits to be processed.
4.  **Updating State**: After a commit is successfully processed (i.e., a blog post is generated and published), its SHA is added to the `processed_shas` set, and the `processed_state.json` file is updated.

This approach is simple, robust, and avoids the need for a more complex database system for this use case.


