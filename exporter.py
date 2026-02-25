
"""
Exporter Module: Triggers Simply Static to export the WordPress site to static HTML.
"""

import os
import requests
import time
import logging
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, before_log, after_log, before_sleep_log

# Configure logging for this module
logger = logging.getLogger(__name__)

class Exporter:
    """
    Manages the export of the WordPress site to static HTML using Simply Static.
    Assumes Simply Static is configured to export to a local folder.
    """

    def __init__(self, wordpress_url: str, simply_static_export_trigger_url: str, export_path: str):
        """
        Initializes the Exporter.

        Args:
            wordpress_url (str): The base URL of your WordPress site (e.g., http://localhost/wordpress).
            simply_static_export_trigger_url (str, optional): The URL to trigger Simply Static export.
                                                              This can be found in Simply Static settings.
                                                              If not provided, manual trigger is assumed.
            export_path (str, optional): The local path where Simply Static exports the files.
                                         This is crucial for the deployer module.
        """
        self.wordpress_url = wordpress_url
        self.simply_static_export_trigger_url = simply_static_export_trigger_url
        self.export_path = export_path
        if self.export_path and not os.path.exists(self.export_path):
            logger.warning(f"Export path {self.export_path} does not exist. Please ensure Simply Static is configured correctly.")

    @retry(wait=wait_exponential(multiplier=1, min=4, max=10),
           stop=stop_after_attempt(3),
           retry=retry_if_exception_type(requests.exceptions.RequestException),
           before_sleep=before_sleep_log(logger, logging.INFO),
           after=after_log(logger, logging.WARNING))
    def trigger_simply_static_export(self) -> bool:
        """
        Triggers the Simply Static export process via a configured URL.

        Returns:
            bool: True if the trigger was successful, False otherwise.
        """
        if not self.simply_static_export_trigger_url:
            logger.warning("Simply Static export trigger URL not provided. Please trigger export manually.")
            return False

        logger.info(f"Attempting to trigger Simply Static export via: {self.simply_static_export_trigger_url}")
        try:
            response = requests.get(self.simply_static_export_trigger_url, timeout=60)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
            logger.info(f"Simply Static export triggered successfully. Response: {response.text[:200]}...")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error triggering Simply Static export: {e}")
            raise # Re-raise to trigger retry

    def wait_for_export_completion(self, timeout: int = 300, check_interval: int = 10) -> bool:
        """
        Waits for the Simply Static export to complete by checking for the existence
        and recent modification of files in the export path.

        Args:
            timeout (int): Maximum time to wait in seconds.
            check_interval (int): How often to check for completion in seconds.

        Returns:
            bool: True if export completed within timeout, False otherwise.
        """
        if not self.export_path:
            logger.warning("Export path not specified. Cannot wait for export completion automatically.")
            return False

        logger.info(f"Waiting for Simply Static export to complete in {self.export_path}...")
        start_time = time.time()
        last_mod_time = 0
        initial_file_count = 0

        # Get initial state of the directory
        if os.path.exists(self.export_path):
            initial_file_count = len(os.listdir(self.export_path))
            try:
                last_mod_time = os.path.getmtime(self.export_path)
            except OSError:
                pass # Directory might be empty or inaccessible initially

        while time.time() - start_time < timeout:
            current_file_count = 0
            current_mod_time = 0

            if os.path.exists(self.export_path):
                current_file_count = len(os.listdir(self.export_path))
                try:
                    current_mod_time = os.path.getmtime(self.export_path)
                except OSError:
                    pass

            # Check if files have appeared or directory has been modified recently
            if current_file_count > 0 and current_mod_time > last_mod_time:
                logger.info("Simply Static export directory is being populated/modified.")
                last_mod_time = current_mod_time # Update last modification time
                # Continue waiting for a short period to ensure all files are written
                time.sleep(check_interval / 2) 
                
            # If directory is populated and no recent changes, assume complete
            if current_file_count > 0 and (time.time() - last_mod_time > check_interval):
                logger.info("Simply Static export appears to be complete (no recent changes detected).")
                return True

            time.sleep(check_interval)

        logger.warning("Timeout waiting for Simply Static export completion.")
        return False

    def get_export_path(self) -> str:
        """
        Returns the configured export path.
        """
        return self.export_path

if __name__ == '__main__':
    # These would typically come from environment variables
    WP_URL = os.getenv("WP_URL", "http://localhost/wordpress")
    SIMPLY_STATIC_TRIGGER_URL = os.getenv("SIMPLY_STATIC_TRIGGER_URL") # e.g., http://localhost/wordpress/?simply_static_export=1
    STATIC_EXPORT_PATH = os.getenv("STATIC_EXPORT_PATH", "/tmp/simply-static-export")

    # Create a dummy export path for testing
    if not os.path.exists(STATIC_EXPORT_PATH):
        os.makedirs(STATIC_EXPORT_PATH, exist_ok=True)
        print(f"Created dummy export path: {STATIC_EXPORT_PATH}")

    exporter = Exporter(
        wordpress_url=WP_URL,
        simply_static_export_trigger_url=SIMPLY_STATIC_TRIGGER_URL, # type:ignore
        export_path=STATIC_EXPORT_PATH
    )

    # Example: Trigger and wait for export
    # if exporter.trigger_simply_static_export():
    #     # Simulate files being written to the directory over time
    #     print("Simulating file writing...")
    #     for i in range(3):
    #         with open(os.path.join(STATIC_EXPORT_PATH, f"test_file_{i}.html"), "w") as f:
    #             f.write(f"<html><body>Test {i}</body></html>")
    #         time.sleep(5) # Simulate delay in file writing

    #     if exporter.wait_for_export_completion(timeout=30, check_interval=2):
    #         print("Simply Static export process finished.")
    #     else:
    #         print("Simply Static export did not complete in time.")
    # else:
    #     print("Failed to trigger Simply Static export.")

    print(f"Configured export path: {exporter.get_export_path()}")


