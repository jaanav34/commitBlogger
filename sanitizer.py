import logging
from bs4 import BeautifulSoup
import unicodedata

logger = logging.getLogger(__name__)

class Sanitizer:
    """
    Handles the cleaning and sanitization of AI-generated Markdown and HTML content
    to prevent issues during rendering and publishing.
    """

    def sanitize_content(self, content_md: str) -> str:
        """
        Runs a series of cleaning functions on the content to ensure it's safe for publishing.

        Args:
            content_md (str): The raw Markdown content from the AI.

        Returns:
            str: The cleaned and sanitized content.
        """
        logger.info("Sanitizing content...")
        
        # Step 1: Fix potentially broken HTML embedded in the Markdown.
        # This is the most critical step for fixing issues like unclosed <code> tags.
        sanitized_content = self.fix_malformed_html(content_md)
        
        # Step 2: Normalize Unicode to remove non-standard characters.
        # This helps prevent server hangs from "dirty" text.
        sanitized_content = self.normalize_unicode(sanitized_content)

        logger.info("Content sanitization complete.")
        return sanitized_content

    def fix_malformed_html(self, text: str) -> str:
        """
        Parses the text as HTML, fixes structural issues, and extracts only the
        content within the <body> tag to avoid adding extra <html> wrappers.

        Args:
            text (str): The input string, which may contain malformed HTML.

        Returns:
            str: The string with corrected HTML structure.
        """
        try:
            soup = BeautifulSoup(text, 'lxml')
            if soup.body:
                # Return only the inner content of the body tag
                return ''.join(str(c) for c in soup.body.contents)
            else:
                # If for some reason a body tag wasn't created, return the parsed string
                return str(soup)
        except Exception as e:
            logger.error(f"Error during HTML sanitization: {e}")
            return text # Return original text on failure

    def normalize_unicode(self, text: str) -> str:
        """
        Normalizes Unicode characters to their standard representation.
        This can help eliminate "weird" characters that might cause rendering issues.

        Args:
            text (str): The input string.

        Returns:
            str: The normalized string.
        """
        try:
            # NFKC (Normalization Form Compatibility Composition) is a good choice for
            # ensuring consistent character representation.
            return unicodedata.normalize('NFKC', text)
        except Exception as e:
            logger.error(f"Error during Unicode normalization: {e}")
            return text # Return original text on failure