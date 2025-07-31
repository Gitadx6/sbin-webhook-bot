from google.cloud import storage
import os
import logging
import traceback

# Import configuration from config.py
# Make sure DB_FILE_NAME and GCS_BUCKET_NAME are defined in config.py
from config import DB_FILE_NAME, GCS_BUCKET_NAME

# Configure logging for this module
logger = logging.getLogger(__name__) # Use the logger configured in app.py or monitor.py

def get_gcs_client():
    """
    Authenticates with Google Cloud Storage and returns a client.
    It implicitly uses GOOGLE_APPLICATION_CREDENTIALS environment variable.
    """
    try:
        # The storage.Client() constructor will automatically look for credentials
        # in the environment, including the path specified by GOOGLE_APPLICATION_CREDENTIALS.
        client = storage.Client()
        logger.debug("Google Cloud Storage client initialized.")
        return client
    except Exception as e:
        logger.error(f"Error initializing Google Cloud Storage client: {e}\n{traceback.format_exc()}")
        return None

def upload_file_to_gcs():
    """
    Uploads the local DB_FILE_NAME to a specified Google Cloud Storage bucket.
    If the file exists in the bucket, it overwrites it.
    Returns True on success, False on failure.
    """
    client = get_gcs_client()
    if not client:
        logger.error("Google Cloud Storage client not available for upload. Skipping upload.")
        return False

    if not GCS_BUCKET_NAME:
        logger.error("GCS_BUCKET_NAME is not configured. Cannot upload file.")
        return False

    if not os.path.exists(DB_FILE_NAME):
        logger.warning(f"Local database file '{DB_FILE_NAME}' not found for upload. Skipping upload.")
        return False

    try:
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(DB_FILE_NAME) # The object name in GCS will be the same as local file name

        # Upload the file, overwriting if it exists
        blob.upload_from_filename(DB_FILE_NAME)
        logger.info(f"Successfully uploaded '{DB_FILE_NAME}' to GCS bucket '{GCS_BUCKET_NAME}'.")
        return True

    except Exception as e:
        logger.error(f"Failed to upload '{DB_FILE_NAME}' to GCS bucket '{GCS_BUCKET_NAME}': {e}\n{traceback.format_exc()}")
        return False

def download_file_from_gcs():
    """
    Downloads DB_FILE_NAME from Google Cloud Storage to the local filesystem.
    Returns True on successful download or if file doesn't exist in GCS (meaning new local DB needed),
    False on error during download.
    """
    client = get_gcs_client()
    if not client:
        logger.error("Google Cloud Storage client not available for download. Cannot attempt download.")
        return False

    if not GCS_BUCKET_NAME:
        logger.error("GCS_BUCKET_NAME is not configured. Cannot download file.")
        return False

    try:
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(DB_FILE_NAME)

        if not blob.exists():
            logger.warning(f"'{DB_FILE_NAME}' not found in GCS bucket '{GCS_BUCKET_NAME}'. A new local DB will be used/created.")
            return True # Not an error, just means no existing file to download.

        # Ensure the directory for the DB file exists if DB_FILE_NAME includes a path
        db_dir = os.path.dirname(DB_FILE_NAME)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        # Download the file
        blob.download_to_filename(DB_FILE_NAME)
        logger.info(f"Successfully downloaded '{DB_FILE_NAME}' from GCS bucket '{GCS_BUCKET_NAME}'.")
        return True

    except Exception as e:
        logger.error(f"Failed to download '{DB_FILE_NAME}' from GCS bucket '{GCS_BUCKET_NAME}': {e}\n{traceback.format_exc()}")
        return False

# Example usage (for local testing)
if __name__ == "__main__":
    # Ensure you have GOOGLE_APPLICATION_CREDENTIALS set in your environment
    # or a service account key file named 'service_account_key.json' in the same directory
    # and GOOGLE_APPLICATION_CREDENTIALS pointing to it.
    # Also set a dummy GCS_BUCKET_NAME for testing
    os.environ["GCS_BUCKET_NAME"] = "your-test-bucket-name" # Replace with a real bucket for testing

    # Create a dummy file to upload
    with open("test_db.db", "w") as f:
        f.write("This is some dummy database content.")
    
    # Temporarily set DB_FILE_NAME for testing this module
    original_db_file_name = DB_FILE_NAME
    DB_FILE_NAME = "test_db.db"

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger.info("--- Testing GCS Sync Module ---")

    # Test Upload
    logger.info("Attempting to upload test_db.db...")
    if upload_file_to_gcs():
        logger.info("Upload test successful.")
    else:
        logger.error("Upload test failed.")

    # Clean up local dummy file
    if os.path.exists("test_db.db"):
        os.remove("test_db.db")
        logger.info("Removed local test_db.db after upload test.")

    # Test Download
    logger.info("Attempting to download test_db.db...")
    if download_file_from_gcs():
        logger.info("Download test successful.")
        if os.path.exists("test_db.db"):
            with open("test_db.db", "r") as f:
                content = f.read()
            logger.info(f"Downloaded file content: '{content}'")
            os.remove("test_db.db") # Clean up downloaded file
    else:
        logger.error("Download test failed.")

    # Restore original DB_FILE_NAME
    DB_FILE_NAME = original_db_file_name
