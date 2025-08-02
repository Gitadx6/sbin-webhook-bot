# gcs_sync.py
This module contains functions for synchronizing files with Google Cloud Storage.
It includes a function to upload a file to a specified GCS bucket.
"""
from google.cloud import storage
import logging

# Set up logging for better visibility into the script's actions
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def upload_file_to_gcs(bucket_name, source_file_name, destination_blob_name):
    """
    Uploads a file to the Google Cloud Storage bucket.

    Args:
        bucket_name (str): The name of the GCS bucket.
        source_file_name (str): The local path of the file to be uploaded.
        destination_blob_name (str): The name to give the file in GCS.
    
    Returns:
        bool: True if the upload was successful, False otherwise.
    """
    try:
        # Initialize a client
        storage_client = storage.Client()
        
        # Get the bucket object
        bucket = storage_client.bucket(bucket_name)
        
        # Create a blob (the file object in GCS)
        blob = bucket.blob(destination_blob_name)
        
        # Upload the file from the local path
        blob.upload_from_filename(source_file_name)
        
        logging.info(
            f"File {source_file_name} uploaded to {destination_blob_name} in bucket {bucket_name}."
        )
        return True

    except Exception as e:
        logging.error(f"Error uploading file to GCS: {e}")
        return False

# Example usage (this part is for testing and won't run on import)
if __name__ == '__main__':
    # You would need to replace these with your actual bucket and file details
    # For a local test, create a dummy file named 'test_file.txt'
    # with some content in the same directory.
    test_bucket_name = 'your-gcs-bucket-name'
    test_source_file = 'test_file.txt'
    test_destination_blob = 'uploaded/test_file.txt'
    
    # Check if a dummy file exists before attempting to upload
    try:
        with open(test_source_file, 'w') as f:
            f.write("This is a test file for GCS upload.")
    except IOError:
        logging.error(f"Please create a file named {test_source_file} to test the upload.")
    
    # Run the upload function
    upload_success = upload_file_to_gcs(test_bucket_name, test_source_file, test_destination_blob)
    if upload_success:
        print("Upload successful.")
    else:
        print("Upload failed.")
