from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload  # ✅ Needed
import os
import io  # ✅ Needed for download

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'credentials.json'

# Drive folder ID where your DB is stored
DRIVE_FOLDER_ID = '1DwVufFvv6f1tvGX_s1WfrBbCl6M57LDL'
DB_FILE_NAME = 'price_tracker.db'

def get_drive_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=credentials)

def upload_file():
    service = get_drive_service()

    # Delete old file with same name (if any)
    results = service.files().list(
        q=f"name='{DB_FILE_NAME}' and '{DRIVE_FOLDER_ID}' in parents and trashed=false",
        spaces='drive',
        fields="files(id, name)"
    ).execute()
    items = results.get('files', [])
    for item in items:
        service.files().delete(fileId=item['id']).execute()

    # Upload fresh copy
    file_metadata = {
        'name': DB_FILE_NAME,
        'parents': [DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(DB_FILE_NAME, mimetype='application/octet-stream')
    service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    print(f"✅ Uploaded {DB_FILE_NAME} to Drive.")

def download_file():
    service = get_drive_service()

    results = service.files().list(
        q=f"name='{DB_FILE_NAME}' and '{DRIVE_FOLDER_ID}' in parents and trashed=false",
        spaces='drive',
        fields="files(id, name)"
    ).execute()
    items = results.get('files', [])
    if not items:
        print(f"⚠️ No file named {DB_FILE_NAME} found in Drive.")
        return

    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)
    fh = open(DB_FILE_NAME, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.close()
    print(f"✅ Downloaded {DB_FILE_NAME} from Drive.")
