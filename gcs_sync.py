import os
import json
from google.cloud import storage

# Retrieve the bucket name from an environment variable
# This is a best practice for production environments.
GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME')

if not GCS_BUCKET_NAME:
    raise ValueError("GCS_BUCKET_NAME environment variable is not set.")

def save_state_to_gcs(file_name: str, state: dict):
    """
    Saves the bot's state dictionary to a JSON file in a GCS bucket.
    The bucket name is retrieved from the GCS_BUCKET_NAME environment variable.
    
    Args:
        file_name (str): The name of the file to save the state to (e.g., 'trading_state.json').
        state (dict): The dictionary containing the bot's current state.
    """
    try:
        # The Google Cloud client will automatically use the
        # GOOGLE_APPLICATION_CREDENTIALS provided by the environment.
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(file_name)
        
        state_json = json.dumps(state, indent=2)

        blob.upload_from_string(state_json, content_type='application/json')
        
        print(f"Successfully saved state to gs://{GCS_BUCKET_NAME}/{file_name}")
    except Exception as e:
        # A real bot might implement exponential backoff and retries here.
        print(f"Error saving state to GCS: {e}")

def load_state_from_gcs(file_name: str) -> dict or None:
    """
    Loads the bot's state from a JSON file in a GCS bucket.
    The bucket name is retrieved from the GCS_BUCKET_NAME environment variable.
    
    Args:
        file_name (str): The name of the file to load the state from.
    
    Returns:
        dict or None: The bot's state dictionary if the file exists, otherwise None.
    """
    try:
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(file_name)

        if not blob.exists():
            print(f"No saved state found at gs://{GCS_BUCKET_NAME}/{file_name}")
            return None
        
        state_json = blob.download_as_text()
        state = json.loads(state_json)
        
        print(f"Successfully loaded state from gs://{GCS_BUCKET_NAME}/{file_name}")
        return state
    except Exception as e:
        print(f"Error loading state from GCS: {e}")
        return None

