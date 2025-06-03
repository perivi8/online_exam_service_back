import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import Config
import logging

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    try:
        # Use service account credentials from environment variable or file
        service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT')
        if service_account_json:
            import json
            credentials = Credentials.from_service_account_info(
                json.loads(service_account_json), scopes=SCOPES
            )
        else:
            # Fallback to a service account file (upload to Render manually)
            credentials = Credentials.from_service_account_file(
                'service_account.json', scopes=SCOPES
            )
        logger.info("Google Drive service initialized successfully")
        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        logger.error(f"Failed to initialize Google Drive service: {str(e)}")
        raise

def upload_video(file_path, file_name):
    try:
        service = get_drive_service()
        file_metadata = {'name': file_name, 'parents': ['root']}
        media = MediaFileUpload(file_path)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        logger.info(f"Uploaded video {file_name} to Google Drive with ID {file.get('id')}")
        return file.get('id')
    except Exception as e:
        logger.error(f"Failed to upload video {file_name}: {str(e)}")
        raise