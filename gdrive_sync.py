# gdrive_sync.py
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import os
import io
import logging
import traceback

# Import configuration from config.py
# Make sure DB_FILE_NAME, SERVICE_ACCOUNT_FILE, GDRIVE_FOLDER_ID are defined in config.py
from config import DB_FILE_NAME, SERVICE_ACCOUNT_FILE, GDRIVE_FOLDER_ID

# Configure logging for this module
logger = logging.getLogger(__name__) # Use the logger configured in monitor.py or main app

# Google Drive API scopes
# Changed to 'drive.file' as it grants access to files created or opened by the app.
# If you need broader access (e.g., listing all files in a folder not created by this app),
# then 'https://www.googleapis.com/auth/drive' might be necessary, but it's more permissive.
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    """Authenticates with Google Drive API using service account."""
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            logger.critical(f"Service account file not found: {SERVICE_ACCOUNT_FILE}. Cannot authenticate with Google Drive.")
            return None
            
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build('drive', 'v3', credentials=credentials)
        return service
    except Exception as e:
        logger.error(f"Error authenticating with Google Drive: {e}\n{traceback.format_exc()}")
        return None

def upload_file():
    """
    Uploads the local DB_FILE_NAME to Google Drive.
    If the file exists on Drive in the specified folder, it updates it;
    otherwise, it creates a new one.
    Returns True on success, False on failure.
    """
    service = get_drive_service()
    if not service:
        logger.error("Google Drive service not available for upload. Skipping upload.")
        return False

    if not os.path.exists(DB_FILE_NAME):
        logger.warning(f"Local database file '{DB_FILE_NAME}' not found for upload. Skipping upload.")
        return False

    try:
        # Search for the file in the specified folder
        # 'trashed=false' ensures we only look for active, non-trashed files.
        query = f"name='{DB_FILE_NAME}' and '{GDRIVE_FOLDER_ID}' in parents and trashed=false"
        results = service.files().list(q=query, fields="files(id)").execute()
        items = results.get('files', [])

        file_metadata = {
            'name': DB_FILE_NAME,
            'parents': [GDRIVE_FOLDER_ID]
        }
        # Use resumable=True for potentially large files or unstable connections
        media = MediaFileUpload(DB_FILE_NAME, mimetype='application/octet-stream', resumable=True)

        if items: # File exists on Drive, update it
            file_id = items[0]['id']
            service.files().update(fileId=file_id, media_body=media).execute()
            logger.info(f"Updated '{DB_FILE_NAME}' (ID: {file_id}) on Google Drive.")
        else: # File does not exist on Drive, create new
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            logger.info(f"Uploaded '{DB_FILE_NAME}' (ID: {file.get('id')}) to Google Drive.")
        return True

    except Exception as e:
        logger.error(f"Failed to upload '{DB_FILE_NAME}' to Google Drive: {e}\n{traceback.format_exc()}")
        return False

def download_file():
    """
    Downloads DB_FILE_NAME from Google Drive to the local filesystem.
    Returns True on successful download or if file doesn't exist on Drive (meaning new local DB needed),
    False on error during download.
    """
    service = get_drive_service()
    if not service:
        logger.error("Google Drive service not available for download. Cannot attempt download.")
        return False

    try:
        # Search for the file in the specified folder
        query = f"name='{DB_FILE_NAME}' and '{GDRIVE_FOLDER_ID}' in parents and trashed=false"
        results = service.files().list(q=query, fields="files(id)").execute()
        items = results.get('files', [])

        if not items:
            logger.warning(f"'{DB_FILE_NAME}' not found in Google Drive folder '{GDRIVE_FOLDER_ID}'. A new local DB will be used/created.")
            return True # Not an error, just means no existing file to download.

        file_id = items[0]['id']
        request = service.files().get_media(fileId=file_id)
        
        # Ensure the directory for the DB file exists if DB_FILE_NAME includes a path (e.g., 'data/price_track.db')
        db_dir = os.path.dirname(DB_FILE_NAME)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True) # exist_ok=True prevents error if dir already exists

        # Open file in binary write mode
        fh = io.FileIO(DB_FILE_NAME, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            logger.debug(f"Download progress: {int(status.progress() * 100)}%.")
        fh.close() # Close the file handle after successful download
        logger.info(f"Downloaded '{DB_FILE_NAME}' from Google Drive.")
        return True

    except Exception as e:
        logger.error(f"Failed to download '{DB_FILE_NAME}' from Google Drive: {e}\n{traceback.format_exc()}")
        return False
