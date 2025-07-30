
"""
Exporter Module: Triggers Simply Static to export the WordPress site to static HTML.
"""

import os
import requests
import time

class Exporter:
    """
    Manages the export of the WordPress site to static HTML using Simply Static.
    Assumes Simply Static is configured to export to a local folder.
    """

    def __init__(self, wordpress_url: str, simply_static_export_trigger_url: str = None, export_path: str = None):
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
            print(f"Warning: Export path {self.export_path} does not exist. Please ensure Simply Static is configured correctly.")

    def trigger_simply_static_export(self) -> bool:
        """
        Triggers the Simply Static export process via a configured URL.

        Returns:
            bool: True if the trigger was successful, False otherwise.
        """
        if not self.simply_static_export_trigger_url:
            print("Simply Static export trigger URL not provided. Please trigger export manually.")
            return False

        print(f"Attempting to trigger Simply Static export via: {self.simply_static_export_trigger_url}")
        try:
            response = requests.get(self.simply_static_export_trigger_url, timeout=60)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
            print(f"Simply Static export triggered successfully. Response: {response.text[:200]}...")
            # TODO: Implement a more robust way to check if the export is complete.
            # This might involve polling a status endpoint if Simply Static provides one,
            # or waiting for a certain file to appear/be modified in the export_path.
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error triggering Simply Static export: {e}")
            return False

    def wait_for_export_completion(self, timeout: int = 300, check_interval: int = 10) -> bool:
        """
        Waits for the Simply Static export to complete by checking for the existence
        of a key file or directory in the export path.

        Args:
            timeout (int): Maximum time to wait in seconds.
            check_interval (int): How often to check for completion in seconds.

        Returns:
            bool: True if export completed within timeout, False otherwise.
        """
        if not self.export_path:
            print("Export path not specified. Cannot wait for export completion automatically.")
            return False

        print(f"Waiting for Simply Static export to complete in {self.export_path}...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            # TODO: Implement a more sophisticated check for export completion.
            # For example, check for a specific file that is known to be generated last,
            # or check if the directory modification time has updated recently.
            # For now, a simple check for directory existence is used.
            if os.path.exists(self.export_path) and len(os.listdir(self.export_path)) > 0:
                print("Simply Static export directory seems to be populated.")
                return True
            time.sleep(check_interval)
        print("Timeout waiting for Simply Static export completion.")
        return False

    def get_export_path(self) -> str:
        """
        Returns the configured export path.
        """
        return self.export_path

# Example Usage (for testing purposes, will be removed in final main.py)
if __name__ == '__main__':
    # These would typically come from environment variables
    WP_URL = os.getenv("WP_URL", "http://localhost/wordpress")
    SIMPLY_STATIC_TRIGGER_URL = os.getenv("SIMPLY_STATIC_TRIGGER_URL") # e.g., http://localhost/wordpress/?simply_static_export=1
    STATIC_EXPORT_PATH = os.getenv("STATIC_EXPORT_PATH", "/tmp/simply-static-export")

    exporter = Exporter(
        wordpress_url=WP_URL,
        simply_static_export_trigger_url=SIMPLY_STATIC_TRIGGER_URL,
        export_path=STATIC_EXPORT_PATH
    )

    # Example: Trigger and wait for export
    # if exporter.trigger_simply_static_export():
    #     if exporter.wait_for_export_completion():
    #         print("Simply Static export process finished.")
    #     else:
    #         print("Simply Static export did not complete in time.")
    # else:
    #     print("Failed to trigger Simply Static export.")

    print(f"Configured export path: {exporter.get_export_path()}")


