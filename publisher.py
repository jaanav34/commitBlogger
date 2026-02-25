
"""
Publisher Module: Handles publishing content to a locally hosted WordPress instance
via XML-RPC or REST API.
"""

import os
import logging
import mimetypes
import socket
import markdown
from typing import Optional
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost, EditPost
from wordpress_xmlrpc.methods.media import UploadFile
from wordpress_xmlrpc.methods.taxonomies import GetTerms, NewTerm
from wordpress_xmlrpc.compat import xmlrpc_client
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, before_log, after_log

# Configure logging for this module
logger = logging.getLogger(__name__)

class Publisher:
    """
    Manages connection and content publishing to WordPress.
    """

    def __init__(self, xmlrpc_url: str, username: str, app_password: str):
        """
        Initializes the Publisher with WordPress credentials.

        Args:
            xmlrpc_url (str): The XML-RPC endpoint of your WordPress site (e.g., http://localhost/wordpress/xmlrpc.php).
            username (str): Your WordPress username.
            app_password (str): Your WordPress application password.
        """
        try:
            self.client = Client(xmlrpc_url, username, app_password)
            logger.info(f"Successfully connected to WordPress XML-RPC at {xmlrpc_url}")
        except socket.gaierror as e:
            logger.critical(f"DNS lookup failed for WordPress URL '{xmlrpc_url}'. [Errno {e.errno}] {e.strerror}")
            logger.critical("Please ensure the WordPress site is running and the WP_XMLRPC_URL in your .env file is a resolvable hostname (e.g., 'http://localhost:10010/xmlrpc.php' or a valid public domain).")
            # Re-raising the original exception to stop the application.
            raise
        except Exception as e:
            logger.critical(f"Failed to connect to WordPress at {xmlrpc_url}: {e}", exc_info=True)
            raise

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10),
           stop=stop_after_attempt(5),
           retry=retry_if_exception_type(xmlrpc_client.Fault),
           before_sleep=before_log(logger, logging.INFO), # type: ignore
           after=after_log(logger, logging.WARNING))
    def publish_post(self, title: str, content_html: str, tags: Optional[list] = None, categories: Optional[list] = None, status: str = 'publish') -> Optional[str]:
        """
        Publishes a new post to WordPress.

        Args:
            title (str): The title of the blog post.
            content_html (str): The content of the blog post in HTML format.
            ...
        """
        post = WordPressPost()
        post.title = title  # type: ignore
        post.content = content_html  # type: ignore
        post.post_status = status  # type: ignore


        terms_names_dict = {}
        if tags:
            terms_names_dict['post_tag'] = tags
        if categories:
            terms_names_dict['category'] = categories

        if terms_names_dict:
            post.terms_names = terms_names_dict  # type: ignore
        logger.info(f"Attempting to publish post: {title}")
        try:
            post_id: str = self.client.call(NewPost(post))  # type: ignore
            logger.info(f"Successfully published post with ID: {post_id}")
            return post_id
        except xmlrpc_client.Fault as e:
            logger.error(f"WordPress XML-RPC error publishing post: {e}")
            raise # Re-raise to trigger retry
        except Exception as e:
            logger.error(f"Unexpected error publishing post: {e}", exc_info=True)
            return None

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10),
           stop=stop_after_attempt(5),
           retry=retry_if_exception_type(xmlrpc_client.Fault),
           before_sleep=before_log(logger, logging.INFO), # type: ignore
           after=after_log(logger, logging.WARNING))
    def update_post(self, post_id: str, title: Optional[str] = None, content_md: Optional[str] = None, tags: Optional[list] = None, categories: Optional[list] = None, status: Optional[str] = None) -> bool:
        """
        Updates an existing post in WordPress.

        Args:
            post_id (str): The ID of the post to update.
            title (str, optional): New title for the post. Defaults to None.
            content_md (str, optional): New content for the post in Markdown format. Defaults to None.
            tags (list, optional): New list of tags for the post. Defaults to None.
            categories (list, optional): New list of categories for the post. Defaults to None.
            status (str, optional): New status for the post. Defaults to None.

        Returns:
            bool: True if the post was updated successfully, False otherwise.
        """
        post = WordPressPost()
        if title: post.title = title  # type: ignore
        if content_md: post.content = markdown.markdown(content_md) # type: ignore
        if status: post.post_status = status  # type: ignore

        terms_names_dict = {}
        if tags:
            terms_names_dict['post_tag'] = tags
        if categories:
            terms_names_dict['category'] = categories

        if terms_names_dict:
            post.terms_names = terms_names_dict  # type: ignore
        logger.info(f"Attempting to update post with ID: {post_id}")
        try:
            self.client.call(EditPost(post_id, post))
            logger.info(f"Successfully updated post with ID: {post_id}")
            return True
        except xmlrpc_client.Fault as e:
            logger.error(f"WordPress XML-RPC error updating post {post_id}: {e}")
            raise # Re-raise to trigger retry
        except Exception as e:
            logger.error(f"Unexpected error updating post {post_id}: {e}", exc_info=True)
            return False

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10),
           stop=stop_after_attempt(5),
           retry=retry_if_exception_type(xmlrpc_client.Fault),
           before_sleep=before_log(logger, logging.INFO), # type: ignore
           after=after_log(logger, logging.WARNING))
    def upload_media(self, file_path: str, mime_type: Optional[str] = None) -> Optional[str]:
        """
        Uploads a media file to WordPress.

        Args:
            file_path (str): Absolute path to the file to upload.
            mime_type (Optional[str]): The MIME type of the file (e.g., 'image/png', 'image/jpeg').
                                       If None, it tries to guess from file extension.

        Returns:
            Optional[str]: The URL of the uploaded file, or None if an error occurred.
        """
        logger.info(f"Attempting to upload media: {file_path}")
        data = {
            'name': os.path.basename(file_path),
            'type': mime_type if mime_type else self._guess_mime_type(file_path),
        }

        try:
            with open(file_path, 'rb') as f:
                data['bits'] = xmlrpc_client.Binary(f.read())
        except FileNotFoundError:
            logger.error(f"Media file not found: {file_path}")
            return None
        except Exception as e:
            logger.error(f"Error reading media file {file_path}: {e}", exc_info=True)
            return None

        try:
            response: dict = self.client.call(UploadFile(data))  # type: ignore
            logger.info(f"Successfully uploaded media. URL: {response['url']}")
            return response['url']
        except xmlrpc_client.Fault as e:
            logger.error(f"WordPress XML-RPC error uploading media {file_path}: {e}")
            raise # Re-raise to trigger retry
        except Exception as e:
            logger.error(f"Unexpected error uploading media {file_path}: {e}", exc_info=True)
            return None

    def _guess_mime_type(self, file_path: str) -> str:
        """
        Helper to guess MIME type based on file extension.
        Uses the standard library `mimetypes` module.
        """
        mimetypes.init()
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or "application/octet-stream"

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10),
           stop=stop_after_attempt(5),
           retry=retry_if_exception_type(xmlrpc_client.Fault),
           before_sleep=before_log(logger, logging.INFO), # type: ignore
           after=after_log(logger, logging.WARNING))
    def ensure_category_exists(self, category_name: str) -> bool:
        """
        Ensures a category exists in WordPress, creating it if necessary.

        Args:
            category_name (str): The name of the category.

        Returns:
            bool: True if the category exists or was created, False otherwise.
        """
        logger.info(f"Ensuring category '{category_name}' exists...")
        try:
            categories = self.client.call(GetTerms('category'))
            for cat in categories:
                if cat.name == category_name:
                    logger.info(f"Category '{category_name}' already exists.")
                    return True
            
            # Category does not exist, create it
            self.client.call(NewTerm(category_name, 'category'))
            logger.info(f"Category '{category_name}' created.")
            return True
        except xmlrpc_client.Fault as e:
            logger.error(f"WordPress XML-RPC error ensuring category '{category_name}': {e}")
            raise # Re-raise to trigger retry
        except Exception as e:
            logger.error(f"Unexpected error ensuring category '{category_name}': {e}", exc_info=True)
            return False

if __name__ == '__main__':
    # These would typically come from environment variables
    WP_XMLRPC_URL = os.getenv('WP_XMLRPC_URL', 'http://localhost/wordpress/xmlrpc.php')
    WP_USERNAME = os.getenv('WP_USERNAME', 'your_wp_username')
    WP_APP_PASSWORD = os.getenv('WP_APP_PASSWORD', 'your_wp_app_password')

    if not WP_USERNAME or not WP_APP_PASSWORD:
        print("Please set WP_USERNAME and WP_APP_PASSWORD environment variables.")
    else:
        publisher = Publisher(WP_XMLRPC_URL, WP_USERNAME, WP_APP_PASSWORD)

        # Example: Publish a new post
        sample_title = "My First Automated Blog Post"
        sample_content = "This is a test post generated automatically by the **Automated Blog Generator** pipeline. It supports *Markdown*!"
        # post_id = publisher.publish_post(sample_title, sample_content, tags=['automation', 'test'], categories=['Technology'])

        # Example: Update an existing post (replace with a valid post_id from your WordPress)
        # if post_id:
        #     publisher.update_post(post_id, content_md="Updated content with more details.", status='draft')

        # Example: Upload an image (replace with a valid path to an image file)
        # image_path = "/path/to/your/image.png"
        # if os.path.exists(image_path):
        #     image_url = publisher.upload_media(image_path)
        #     print(f"Uploaded image URL: {image_url}")
        # else:
        #     print(f"Image file not found: {image_path}")

        # Example: Ensure a category exists
        # publisher.ensure_category_exists('New Category')
