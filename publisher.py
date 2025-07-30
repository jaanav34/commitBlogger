
"""
Publisher Module: Handles publishing content to a locally hosted WordPress instance
via XML-RPC or REST API.
"""

import os
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost, EditPost
from wordpress_xmlrpc.methods.media import UploadFile
from wordpress_xmlrpc.methods.taxonomies import GetTerms, NewTerm
from wordpress_xmlrpc.compat import xmlrpc_client

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
        self.client = Client(xmlrpc_url, username, app_password)
        print(f"Connected to WordPress XML-RPC at {xmlrpc_url}")

    def publish_post(self, title: str, content_md: str, tags: list = None, categories: list = None, status: str = 'publish') -> str:
        """
        Publishes a new post to WordPress.

        Args:
            title (str): The title of the blog post.
            content_md (str): The content of the blog post in Markdown format.
            tags (list, optional): A list of tags for the post. Defaults to None.
            categories (list, optional): A list of categories for the post. Defaults to None.
            status (str): The status of the post (e.g., 'publish', 'draft'). Defaults to 'publish'.

        Returns:
            str: The ID of the newly created post, or None if an error occurred.
        """
        post = WordPressPost()
        post.title = title
        post.content = content_md
        post.post_status = status

        if tags:
            post.terms_names.tags = tags
        if categories:
            post.terms_names.category = categories

        print(f"Attempting to publish post: {title}")
        try:
            post_id = self.client.call(NewPost(post))
            print(f"Successfully published post with ID: {post_id}")
            return post_id
        except Exception as e:
            print(f"Error publishing post: {e}")
            # TODO: Implement robust error handling and retry mechanism
            return None

    def update_post(self, post_id: str, title: str = None, content_md: str = None, tags: list = None, categories: list = None, status: str = None) -> bool:
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
        post = WordPressPost(post_id)
        if title: post.title = title
        if content_md: post.content = content_md
        if tags: post.terms_names.tags = tags
        if categories: post.terms_names.category = categories
        if status: post.post_status = status

        print(f"Attempting to update post with ID: {post_id}")
        try:
            self.client.call(EditPost(post_id, post))
            print(f"Successfully updated post with ID: {post_id}")
            return True
        except Exception as e:
            print(f"Error updating post {post_id}: {e}")
            return False

    def upload_media(self, file_path: str, mime_type: str = None) -> str:
        """
        Uploads a media file to WordPress.

        Args:
            file_path (str): Absolute path to the file to upload.
            mime_type (str, optional): The MIME type of the file (e.g., 'image/png', 'image/jpeg').
                                       If None, it tries to guess from file extension.

        Returns:
            str: The URL of the uploaded file, or None if an error occurred.
        """
        print(f"Attempting to upload media: {file_path}")
        data = {
            'name': os.path.basename(file_path),
            'type': mime_type if mime_type else self._guess_mime_type(file_path),
        }

        with open(file_path, 'rb') as f:
            data['bits'] = xmlrpc_client.Binary(f.read())

        try:
            response = self.client.call(UploadFile(data))
            print(f"Successfully uploaded media. URL: {response['url']}")
            return response['url']
        except Exception as e:
            print(f"Error uploading media {file_path}: {e}")
            return None

    def _guess_mime_type(self, file_path: str) -> str:
        """
        Helper to guess MIME type based on file extension.
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".png": return "image/png"
        if ext == ".jpg" or ext == ".jpeg": return "image/jpeg"
        if ext == ".gif": return "image/gif"
        if ext == ".pdf": return "application/pdf"
        # TODO: Add more MIME types as needed
        return "application/octet-stream"

    def ensure_category_exists(self, category_name: str) -> bool:
        """
        Ensures a category exists in WordPress, creating it if necessary.

        Args:
            category_name (str): The name of the category.

        Returns:
            bool: True if the category exists or was created, False otherwise.
        """
        print(f"Ensuring category '{category_name}' exists...")
        try:
            categories = self.client.call(GetTerms('category'))
            for cat in categories:
                if cat.name == category_name:
                    print(f"Category '{category_name}' already exists.")
                    return True
            
            # Category does not exist, create it
            self.client.call(NewTerm(category_name, 'category'))
            print(f"Category '{category_name}' created.")
            return True
        except Exception as e:
            print(f"Error ensuring category '{category_name}': {e}")
            return False

# Example Usage (for testing purposes, will be removed in final main.py)
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



