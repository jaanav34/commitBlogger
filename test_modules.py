"""
test_modules.py: Unit tests for the Automated Blog Generator modules.
Uses pytest for testing framework.
"""

import pytest
import os
import json
from unittest.mock import Mock, patch, MagicMock

# Import modules to test
from ingest import Ingester
from transform import Transformer
from publisher import Publisher
from exporter import Exporter
from deployer import Deployer

class TestIngester:
    """Test cases for the Ingester module."""

    def test_load_processed_shas_empty_file(self, tmp_path):
        """Test loading processed SHAs when state file doesn't exist."""
        state_file = tmp_path / "test_state.json"
        ingester = Ingester("fake_github_token", "fake_notion_token", str(state_file))
        assert ingester.processed_shas == set()

    def test_load_processed_shas_existing_file(self, tmp_path):
        """Test loading processed SHAs from an existing state file."""
        state_file = tmp_path / "test_state.json"
        test_shas = ["sha1", "sha2", "sha3"]
        with open(state_file, 'w') as f:
            json.dump(test_shas, f)
        
        ingester = Ingester("fake_github_token", "fake_notion_token", str(state_file))
        assert ingester.processed_shas == set(test_shas)

    def test_save_processed_shas(self, tmp_path):
        """Test saving processed SHAs to state file."""
        state_file = tmp_path / "test_state.json"
        ingester = Ingester("fake_github_token", "fake_notion_token", str(state_file))
        ingester.processed_shas.add("new_sha")
        ingester._save_processed_shas()
        
        with open(state_file, 'r') as f:
            saved_shas = json.load(f)
        assert "new_sha" in saved_shas

    @patch('ingest.Github')
    def test_fetch_github_commits_incremental(self, mock_github, tmp_path):
        """Test fetching GitHub commits in incremental mode."""
        # Mock GitHub API response
        mock_repo = Mock()
        mock_commit = Mock()
        mock_commit.sha = "test_sha"
        mock_commit.commit.message = "Test commit message"
        mock_commit.commit.author.name = "Test Author"
        mock_commit.commit.author.date = Mock()
        mock_commit.commit.author.date.isoformat.return_value = "2023-01-01T00:00:00"
        mock_commit.html_url = "https://github.com/test/repo/commit/test_sha"
        
        mock_full_commit = Mock()
        mock_full_commit.files = []
        mock_repo.get_commit.return_value = mock_full_commit
        mock_repo.get_commits.return_value = [mock_commit]
        
        mock_github_instance = Mock()
        mock_github_instance.get_user.return_value.get_repo.return_value = mock_repo
        mock_github.return_value = mock_github_instance
        
        state_file = tmp_path / "test_state.json"
        ingester = Ingester("fake_github_token", "fake_notion_token", str(state_file))
        
        commits = ingester.fetch_github_commits("test/repo", since_days=7)
        assert len(commits) == 1
        assert commits[0]["sha"] == "test_sha"

class TestTransformer:
    """Test cases for the Transformer module."""

    @patch('transform.genai')
    def test_generate_blog_post(self, mock_genai):
        """Test blog post generation."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Generated blog post content"
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        transformer = Transformer("fake_api_key")
        result = transformer.generate_blog_post("Test commit", [])
        assert result == "Generated blog post content"

    def test_summarize_diff(self):
        """Test diff summarization."""
        transformer = Transformer("fake_api_key")
        files_changed = [
            {
                "filename": "test.py",
                "status": "modified",
                "patch": "+print('hello')\n-print('goodbye')"
            }
        ]
        summary = transformer._summarize_diff(files_changed)
        assert "test.py" in summary
        assert "modified" in summary

class TestPublisher:
    """Test cases for the Publisher module."""

    @patch('publisher.Client')
    def test_publish_post(self, mock_client):
        """Test WordPress post publishing."""
        mock_client_instance = Mock()
        mock_client_instance.call.return_value = "123"  # Mock post ID
        mock_client.return_value = mock_client_instance
        
        publisher = Publisher("http://test.com/xmlrpc.php", "user", "pass")
        post_id = publisher.publish_post("Test Title", "Test Content")
        assert post_id == "123"

class TestExporter:
    """Test cases for the Exporter module."""

    @patch('exporter.requests')
    def test_trigger_simply_static_export(self, mock_requests):
        """Test triggering Simply Static export."""
        mock_response = Mock()
        mock_response.text = "Export triggered"
        mock_requests.get.return_value = mock_response
        
        exporter = Exporter("http://test.com", "http://test.com/export")
        result = exporter.trigger_simply_static_export()
        assert result is True

class TestDeployer:
    """Test cases for the Deployer module."""

    def test_deployer_initialization(self, tmp_path):
        """Test Deployer initialization."""
        deployer = Deployer(str(tmp_path), "https://github.com/test/repo.git")
        assert deployer.local_repo_path == str(tmp_path)
        assert deployer.github_repo_url == "https://github.com/test/repo.git"

    def test_deployer_initialization_invalid_path(self):
        """Test Deployer initialization with invalid path."""
        with pytest.raises(FileNotFoundError):
            Deployer("/nonexistent/path", "https://github.com/test/repo.git")

# Integration test outline
class TestIntegration:
    """Integration tests for the complete pipeline."""

    def test_end_to_end_pipeline_mock(self):
        """
        Mock integration test for the complete pipeline.
        This would test the interaction between all modules.
        """
        # TODO: Implement a comprehensive integration test that:
        # 1. Mocks all external APIs (GitHub, Gemini, WordPress, etc.)
        # 2. Tests the complete flow from ingestion to deployment
        # 3. Verifies that data flows correctly between modules
        # 4. Checks error handling and state management
        pass

if __name__ == "__main__":
    # Run tests with: python -m pytest test_modules.py -v
    pytest.main([__file__, "-v"])


