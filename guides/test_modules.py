"""
test_modules.py: Unit tests for the Automated Blog Generator modules.
Uses pytest for testing framework.
"""

import pytest
import os
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Import modules to test
from ingest import Ingester
from transform import Transformer
from publisher import Publisher
from exporter import Exporter
from deployer import Deployer

# Mock environment variables for testing
@pytest.fixture(autouse=True)
def mock_env_vars():
    with patch.dict(os.environ, {
        "GITHUB_TOKEN": "test_github_token",
        "NOTION_TOKEN": "test_notion_token",
        "GEMINI_API_KEY": "test_gemini_api_key",
        "WP_XMLRPC_URL": "http://localhost/xmlrpc.php",
        "WP_USERNAME": "test_user",
        "WP_APP_PASSWORD": "test_password",
        "SIMPLY_STATIC_EXPORT_PATH": "/tmp/test_export",
        "SIMPLY_STATIC_TRIGGER_URL": "http://localhost/?simply_static_export=1",
        "GITHUB_PAGES_REPO_URL": "https://github.com/test/pages.git",
    }):
        yield

class TestIngester:
    """Test cases for the Ingester module."""

    @pytest.fixture(autouse=True)
    def setup_ingester(self, tmp_path):
        self.state_file = tmp_path / "processed_state.json"
        self.ingester = Ingester("fake_github_token", "fake_notion_token", str(self.state_file))

    def test_load_processed_shas_empty_file(self):
        """Test loading processed SHAs when state file doesn't exist."""
        assert self.ingester.processed_shas == set()

    def test_load_processed_shas_existing_file(self):
        """Test loading processed SHAs from an existing state file."""
        test_shas = ["sha1", "sha2", "sha3"]
        with open(self.state_file, 'w') as f:
            json.dump(test_shas, f)
        
        ingester_reloaded = Ingester("fake_github_token", "fake_notion_token", str(self.state_file))
        assert ingester_reloaded.processed_shas == set(test_shas)

    def test_save_processed_shas(self):
        """
        Test saving processed SHAs to state file.
        """
        self.ingester.processed_shas.add("new_sha")
        self.ingester._save_processed_shas()
        
        with open(self.state_file, 'r') as f:
            saved_shas = json.load(f)
        assert "new_sha" in saved_shas

    @patch('ingest.Github')
    def test_fetch_github_commits_incremental(self, mock_github):
        """Test fetching GitHub commits in incremental mode."""
        mock_repo = Mock()
        mock_commit = Mock()
        mock_commit.sha = "test_sha_inc"
        mock_commit.commit.message = "Test commit message incremental"
        mock_commit.commit.author.name = "Test Author"
        mock_commit.commit.author.date = datetime.now() - timedelta(days=1)
        mock_commit.html_url = "https://github.com/test/repo/commit/test_sha_inc"
        
        mock_full_commit = Mock()
        mock_full_commit.files = []
        mock_repo.get_commit.return_value = mock_full_commit
        mock_repo.get_commits.return_value = [mock_commit]
        
        mock_github_instance = Mock()
        mock_github_instance.get_user.return_value.get_repo.return_value = mock_repo
        mock_github.return_value = mock_github_instance
        
        commits = self.ingester.fetch_github_commits("test/repo", since_days=7)
        assert len(commits) == 1
        assert commits[0]["sha"] == "test_sha_inc"
        assert "test_sha_inc" in self.ingester.processed_shas

    @patch('ingest.Github')
    def test_fetch_github_commits_batch(self, mock_github):
        """Test fetching GitHub commits in batch mode."""
        mock_repo = Mock()
        mock_commit1 = Mock()
        mock_commit1.sha = "test_sha_batch1"
        mock_commit1.commit.message = "Batch commit 1"
        mock_commit1.commit.author.name = "Test Author"
        mock_commit1.commit.author.date = datetime.now() - timedelta(days=10)
        mock_commit1.html_url = "https://github.com/test/repo/commit/test_sha_batch1"

        mock_commit2 = Mock()
        mock_commit2.sha = "test_sha_batch2"
        mock_commit2.commit.message = "Batch commit 2"
        mock_commit2.commit.author.name = "Test Author"
        mock_commit2.commit.author.date = datetime.now() - timedelta(days=20)
        mock_commit2.html_url = "https://github.com/test/repo/commit/test_sha_batch2"
        
        mock_full_commit = Mock()
        mock_full_commit.files = []
        mock_repo.get_commit.return_value = mock_full_commit
        mock_repo.get_commits.return_value = [mock_commit1, mock_commit2]
        
        mock_github_instance = Mock()
        mock_github_instance.get_user.return_value.get_repo.return_value = mock_repo
        mock_github.return_value = mock_github_instance
        
        commits = self.ingester.fetch_github_commits("test/repo", batch_mode=True)
        assert len(commits) == 2
        assert "test_sha_batch1" in self.ingester.processed_shas
        assert "test_sha_batch2" in self.ingester.processed_shas

    @patch('ingest.Client')
    def test_fetch_notion_notes(self, mock_notion_client):
        """Test fetching Notion notes."""
        mock_notion_instance = Mock()
        mock_notion_client.return_value = mock_notion_instance
        
        mock_notion_instance.databases.query.return_value = {
            "results": [
                {
                    "id": "note_id_1",
                    "last_edited_time": "2023-01-01T10:00:00Z",
                    "properties": {"title": {"title": [{"plain_text": "Test Note 1"}]}},
                    "url": "http://notion.so/note_id_1"
                }
            ],
            "has_more": False,
            "next_cursor": None
        }
        mock_notion_instance.blocks.children.list.return_value = {
            "results": [
                {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Content of note 1."}]}}
            ]
        }

        notes = self.ingester.fetch_notion_notes("test_db_id")
        assert len(notes) == 1
        assert notes[0]["title"] == "Test Note 1"
        assert notes[0]["content"] == "Content of note 1.\n"

class TestTransformer:
    """Test cases for the Transformer module."""

    @pytest.fixture(autouse=True)
    def setup_transformer(self):
        self.transformer = Transformer("fake_api_key")

    @patch('transform.genai')
    def test_generate_blog_post(self, mock_genai):
        """Test blog post generation."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Generated blog post content"
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        result = self.transformer.generate_blog_post("Test commit", [])
        assert result == "Generated blog post content"

    def test_summarize_diff_small(self):
        """Test diff summarization for small diffs."""
        files_changed = [
            {
                "filename": "test.py",
                "status": "modified",
                "patch": "+print('hello')\n-print('goodbye')"
            }
        ]
        summary = self.transformer._summarize_diff(files_changed)
        assert "test.py" in summary
        assert "modified" in summary
        assert "+print('hello')" in summary

    @patch('transform.Transformer._call_gemini')
    def test_summarize_diff_large(self, mock_call_gemini):
        """Test diff summarization for large diffs using Gemini."""
        mock_call_gemini.return_value = "Gemini summarized diff"
        large_patch = "a" * 2000 # Simulate a large patch
        files_changed = [
            {
                "filename": "large_file.py",
                "status": "added",
                "patch": large_patch
            }
        ]
        summary = self.transformer._summarize_diff(files_changed)
        assert "large_file.py" in summary
        assert "Gemini summarized diff" in summary
        mock_call_gemini.assert_called_once()

    @patch('transform.genai')
    def test_generate_linkedin_summary(self, mock_genai):
        """Test LinkedIn summary generation."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Generated LinkedIn summary"
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        result = self.transformer.generate_linkedin_summary("Test commit", [])
        assert result == "Generated LinkedIn summary"

    @patch('transform.genai')
    def test_generate_click_worthy_title(self, mock_genai):
        """Test click-worthy title generation."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Title 1\nTitle 2\nTitle 3"
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        result = self.transformer.generate_click_worthy_title("Test commit", "Blog content")
        assert result == "Title 1"

class TestPublisher:
    """Test cases for the Publisher module."""

    @pytest.fixture(autouse=True)
    def setup_publisher(self):
        with patch('publisher.Client') as mock_client_class:
            self.mock_client_instance = Mock()
            mock_client_class.return_value = self.mock_client_instance
            self.publisher = Publisher("http://test.com/xmlrpc.php", "user", "pass")

    def test_publish_post(self):
        """Test WordPress post publishing."""
        self.mock_client_instance.call.return_value = "123"  # Mock post ID
        post_id = self.publisher.publish_post("Test Title", "Test Content")
        assert post_id == "123"
        self.mock_client_instance.call.assert_called_once()

    def test_update_post(self):
        """Test WordPress post updating."""
        self.mock_client_instance.call.return_value = True
        result = self.publisher.update_post("123", title="Updated Title")
        assert result is True
        self.mock_client_instance.call.assert_called_once()

    def test_upload_media(self, tmp_path):
        """Test media upload to WordPress."""
        dummy_file = tmp_path / "test_image.png"
        dummy_file.write_text("dummy image data")

        self.mock_client_instance.call.return_value = {"url": "http://test.com/image.png"}
        image_url = self.publisher.upload_media(str(dummy_file))
        assert image_url == "http://test.com/image.png"
        self.mock_client_instance.call.assert_called_once()

    def test_guess_mime_type(self):
        """Test MIME type guessing."""
        assert self.publisher._guess_mime_type("image.png") == "image/png"
        assert self.publisher._guess_mime_type("document.pdf") == "application/pdf"
        assert self.publisher._guess_mime_type("unknown.xyz") == "application/octet-stream"

class TestExporter:
    """Test cases for the Exporter module."""

    @pytest.fixture(autouse=True)
    def setup_exporter(self, tmp_path):
        self.export_path = tmp_path / "simply-static-export"
        self.exporter = Exporter(
            wordpress_url="http://test.com",
            simply_static_export_trigger_url="http://test.com/export",
            export_path=str(self.export_path)
        )
        self.export_path.mkdir(exist_ok=True)

    @patch('exporter.requests.get')
    def test_trigger_simply_static_export(self, mock_get):
        """Test triggering Simply Static export."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = "Export triggered"
        mock_get.return_value = mock_response
        
        result = self.exporter.trigger_simply_static_export()
        assert result is True
        mock_get.assert_called_once_with(self.exporter.simply_static_export_trigger_url, timeout=60)

    @patch('exporter.time.sleep')
    def test_wait_for_export_completion(self, mock_sleep):
        """Test waiting for export completion."""
        # Simulate files appearing in the directory
        def simulate_files_appear(*args, **kwargs):
            if not hasattr(simulate_files_appear, 'counter'):
                simulate_files_appear.counter = 0
            if simulate_files_appear.counter < 2:
                (self.export_path / f"file_{simulate_files_appear.counter}.html").write_text("content")
                simulate_files_appear.counter += 1
            os.utime(self.export_path, None) # Update modification time

        mock_sleep.side_effect = simulate_files_appear

        result = self.exporter.wait_for_export_completion(timeout=10, check_interval=1)
        assert result is True

class TestDeployer:
    """Test cases for the Deployer module."""

    @pytest.fixture(autouse=True)
    def setup_deployer(self, tmp_path):
        self.local_repo_path = tmp_path / "test_repo"
        self.local_repo_path.mkdir()
        self.deployer = Deployer(str(self.local_repo_path), "https://github.com/test/repo.git")

    def test_deployer_initialization(self):
        """Test Deployer initialization."""
        assert self.deployer.local_repo_path == str(self.local_repo_path)
        assert self.deployer.github_repo_url == "https://github.com/test/repo.git"

    def test_deployer_initialization_invalid_path(self):
        """Test Deployer initialization with invalid path."""
        with pytest.raises(FileNotFoundError):
            Deployer("/nonexistent/path", "https://github.com/test/repo.git")

    @patch('deployer.subprocess.run')
    def test_initialize_repo_new(self, mock_subprocess_run):
        """Test initializing a new Git repository."""
        mock_subprocess_run.return_value = Mock(returncode=0, stdout="", stderr="")
        result = self.deployer.initialize_repo()
        assert result is True
        assert mock_subprocess_run.call_count == 3 # init, remote add, checkout

    @patch('deployer.subprocess.run')
    def test_deploy_no_changes(self, mock_subprocess_run):
        """Test deploy when there are no changes to commit."""
        # Mock git status --porcelain to return empty string (no changes)
        mock_subprocess_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""), # for initialize_repo
            Mock(returncode=0, stdout="", stderr=""), # for git add .
            Mock(returncode=0, stdout="", stderr="")  # for git status --porcelain
        ]
        result = self.deployer.deploy()
        assert result is True
        # Should not call git commit or git push
        assert mock_subprocess_run.call_count == 3 # initialize_repo calls + git add + git status

    @patch('deployer.subprocess.run')
    def test_deploy_with_changes(self, mock_subprocess_run):
        """Test deploy when there are changes to commit."""
        # Mock git status --porcelain to return changes
        mock_subprocess_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""), # for initialize_repo
            Mock(returncode=0, stdout="", stderr=""), # for git add .
            Mock(returncode=0, stdout="M some_file.txt", stderr=""), # for git status --porcelain
            Mock(returncode=0, stdout="", stderr=""), # for git commit
            Mock(returncode=0, stdout="", stderr="")  # for git push
        ]
        result = self.deployer.deploy()
        assert result is True
        assert mock_subprocess_run.call_count == 5 # initialize_repo calls + git add + git status + git commit + git push

# Integration test outline
class TestIntegration:
    """Integration tests for the complete pipeline."""

    @patch('ingest.Ingester')
    @patch('transform.Transformer')
    @patch('publisher.Publisher')
    @patch('exporter.Exporter')
    @patch('deployer.Deployer')
    @patch('main.load_env_variables')
    def test_end_to_end_pipeline_mock(self,
                                       mock_load_env_variables,
                                       mock_deployer_class,
                                       mock_exporter_class,
                                       mock_publisher_class,
                                       mock_transformer_class,
                                       mock_ingester_class):
        """
        Comprehensive integration test for the complete pipeline with mocked external APIs.
        This tests the flow and interactions between modules.
        """
        # Mock environment variables
        mock_load_env_variables.return_value = {
            "github_token": "mock_gh_token",
            "github_repo": "mock_user/mock_repo",
            "gemini_api_key": "mock_gemini_key",
            "notion_token": "mock_notion_token",
            "notion_database_id": "mock_notion_db_id",
            "wp_url": "http://mock-wp.local",
            "wp_xmlrpc_url": "http://mock-wp.local/xmlrpc.php",
            "wp_username": "mock_wp_user",
            "wp_app_password": "mock_wp_pass",
            "simply_static_export_path": "/tmp/mock_export",
            "simply_static_trigger_url": "http://mock-wp.local/?simply_static_export=1",
            "github_pages_repo_url": "https://github.com/mock/pages.git",
        }

        # Mock Ingester behavior
        mock_ingester_instance = mock_ingester_class.return_value
        mock_ingester_instance.fetch_github_commits.return_value = [
            {
                'sha': 'mock_sha_1',
                'message': 'feat: Add new feature',
                'author': 'Mock Author',
                'date': '2023-01-01T00:00:00',
                'url': 'http://mock.com/commit/1',
                'files': []
            }
        ]
        mock_ingester_instance.fetch_notion_notes.return_value = []

        # Mock Transformer behavior
        mock_transformer_instance = mock_transformer_class.return_value
        mock_transformer_instance.generate_blog_post.return_value = "Mock blog post content"
        mock_transformer_instance.generate_linkedin_summary.return_value = "Mock LinkedIn summary"
        mock_transformer_instance.generate_click_worthy_title.return_value = "Mock Blog Title"

        # Mock Publisher behavior
        mock_publisher_instance = mock_publisher_class.return_value
        mock_publisher_instance.publish_post.return_value = "mock_post_id"

        # Mock Exporter behavior
        mock_exporter_instance = mock_exporter_class.return_value
        mock_exporter_instance.trigger_simply_static_export.return_value = True
        mock_exporter_instance.wait_for_export_completion.return_value = True

        # Mock Deployer behavior
        mock_deployer_instance = mock_deployer_class.return_value
        mock_deployer_instance.deploy.return_value = True

        # Run the main pipeline function
        from main import run_pipeline
        run_pipeline(mode="incremental", since_days=1)

        # Assertions to verify interactions and data flow
        mock_load_env_variables.assert_called_once()
        mock_ingester_class.assert_called_once_with(
            github_token="mock_gh_token",
            notion_token="mock_notion_token",
            state_file="processed_state.json"
        )
        mock_ingester_instance.fetch_github_commits.assert_called_once_with("mock_user/mock_repo", since_days=1)
        mock_ingester_instance.fetch_notion_notes.assert_called_once() # Called with since_date

        mock_transformer_class.assert_called_once_with(gemini_api_key="mock_gemini_key")
        mock_transformer_instance.generate_blog_post.assert_called_once()
        mock_transformer_instance.generate_linkedin_summary.assert_called_once()
        mock_transformer_instance.generate_click_worthy_title.assert_called_once()

        mock_publisher_class.assert_called_once_with(
            xmlrpc_url="http://mock-wp.local/xmlrpc.php",
            username="mock_wp_user",
            app_password="mock_wp_pass"
        )
        mock_publisher_instance.publish_post.assert_called_once_with(
            title="Mock Blog Title",
            content_md="Mock blog post content",
            tags=["automated", "github", "gemini"],
            categories=["Development"]
        )

        mock_exporter_class.assert_called_once_with(
            wordpress_url="http://mock-wp.local",
            simply_static_export_trigger_url="http://mock-wp.local/?simply_static_export=1",
            export_path="/tmp/mock_export"
        )
        mock_exporter_instance.trigger_simply_static_export.assert_called_once()
        mock_exporter_instance.wait_for_export_completion.assert_called_once()

        mock_deployer_class.assert_called_once_with(
            local_repo_path="/tmp/mock_export",
            github_repo_url="https://github.com/mock/pages.git"
        )
        mock_deployer_instance.deploy.assert_called_once_with(commit_message="Automated blog update from pipeline")

        # Verify LinkedIn summary file creation (if applicable)
        # This would require inspecting the file system or mocking os.makedirs/open
        # For now, we'll assume the main.py logic handles this correctly based on the mock

if __name__ == "__main__":
    # Run tests with: python -m pytest test_modules.py -v
    pytest.main([__file__, "-v"])


