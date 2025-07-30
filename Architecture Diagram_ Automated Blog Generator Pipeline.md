# Architecture Diagram: Automated Blog Generator Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────────────┐  │
│  │ GitHub API  │    │ Notion API  │    │ Local State File (processed.json)  │  │
│  │ (PyGithub)  │    │ (notion-    │    │ - Tracks processed commit SHAs     │  │
│  │ - Commits   │    │  client)    │    │ - Prevents duplicate processing     │  │
│  │ - Diffs     │    │ - Notes     │    │ - Supports incremental mode        │  │
│  │ - Messages  │    │ - Pages     │    │                                     │  │
│  └─────────────┘    └─────────────┘    └─────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        INGESTION MODULE (ingest.py)                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│  • fetch_github_commits(repo, since_date, batch_mode)                          │
│  • fetch_notion_notes(database_id, since_date)                                 │
│  • filter_processed_commits(commits, state_file)                               │
│  • save_raw_data(data, cache_dir)                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      TRANSFORMATION MODULE (transform.py)                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  • preprocess_commit_diff(commit_data)                                         │
│  • generate_gemini_prompts(commit_message, diff_summary, note_content)         │
│  • call_gemini_api(prompt, content_type)                                       │
│  • parse_gemini_response(response, format)                                     │
│  • generate_blog_post(commit_data) → Markdown                                  │
│  • generate_linkedin_summary(commit_data) → Short text                         │
│  • generate_catchy_title(commit_data) → SEO-optimized title                    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       PUBLISHER MODULE (publisher.py)                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│  • connect_wordpress(endpoint, username, app_password)                         │
│  • create_wordpress_post(title, content, tags, categories)                     │
│  • upload_media_to_wordpress(image_path)                                       │
│  • schedule_post(post_data, publish_date)                                      │
│  • verify_post_published(post_id)                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        EXPORTER MODULE (exporter.py)                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│  • trigger_simply_static_export(wordpress_url, export_path)                    │
│  • wait_for_export_completion(export_job_id)                                   │
│  • verify_static_files(export_directory)                                       │
│  • optimize_static_assets(export_directory)                                    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        DEPLOYER MODULE (deployer.py)                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│  • initialize_git_repo(static_files_path)                                      │
│  • commit_static_files(commit_message)                                         │
│  • push_to_github_pages(repo_url, branch="gh-pages")                           │
│  • verify_deployment(pages_url)                                                │
│  • cleanup_temp_files(temp_directories)                                        │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FINAL OUTPUT                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────────┐  │
│  │ WordPress Blog  │    │ GitHub Pages    │    │ LinkedIn Content Ready     │  │
│  │ (localhost)     │    │ Static Site     │    │ for Manual Posting         │  │
│  │ - Rich content  │    │ - Fast loading  │    │ - Optimized summaries      │  │
│  │ - SEO optimized │    │ - Global CDN    │    │ - Engagement focused       │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATION LAYER                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  main.py - Master orchestrator with:                                           │
│  • Batch mode: Process all historical commits                                  │
│  • Incremental mode: Process only new commits since last run                   │
│  • Error handling and retry logic                                              │
│  • Logging and progress tracking                                               │
│  • Configuration management                                                     │
│                                                                                 │
│  Scheduling:                                                                    │
│  • Cron job (Linux/Mac): Daily incremental runs                                │
│  • Task Scheduler (Windows): Daily incremental runs                            │
│  • Manual execution: Batch processing or immediate publishing                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                            EXTERNAL SERVICES                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  • Google AI Studio (Gemini API) - Content generation                          │
│  • GitHub API - Repository access and Pages deployment                         │
│  • Notion API - Note and page ingestion                                        │
│  • WordPress XML-RPC/REST API - Content publishing                             │
│  • Simply Static Plugin - Static site generation                               │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Summary

1. **Ingestion**: Fetch commits from GitHub and notes from Notion, filter against processed state
2. **Transformation**: Use Gemini to convert technical content into blog posts, LinkedIn summaries, and titles
3. **Publishing**: Post content to local WordPress instance via XML-RPC/REST API
4. **Export**: Trigger Simply Static to generate static HTML files
5. **Deployment**: Push static files to GitHub Pages for public hosting
6. **State Management**: Update processed commits list to enable incremental processing

