"""
Handles YouTube video uploads using YouTube Data API v3.
Manages OAuth authentication and video uploads with metadata.
"""
import os
import sys
import httplib2
import logging
import random
import time
import warnings
from typing import Dict, Optional

# Suppress Python 3.9 compatibility warnings from Google API libraries
warnings.filterwarnings("ignore", category=FutureWarning, message=".*importlib.metadata.*")
warnings.filterwarnings("ignore", message=".*packages_distributions.*")

# Suppress stderr during import to catch the error message
import contextlib
import io

stderr_suppressor = io.StringIO()
with contextlib.redirect_stderr(stderr_suppressor):
    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_httplib2 import AuthorizedHttp
    except Exception:
        # If import fails, re-raise without suppression
        raise

from config import (
    CLIENT_SECRETS_FILE,
    YOUTUBE_UPLOAD_SCOPE,
    YOUTUBE_SCOPES,
    YOUTUBE_API_SERVICE_NAME,
    YOUTUBE_API_VERSION,
    MAX_RETRIES,
    RETRIABLE_STATUS_CODES,
    DEFAULT_CATEGORY_ID,
    DEFAULT_PRIVACY_STATUS,
    VALID_PRIVACY_STATUSES
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Retriable exceptions
RETRIABLE_EXCEPTIONS = (
    httplib2.HttpLib2Error,
    IOError,
    ConnectionError,
    TimeoutError
)


class YouTubeUploader:
    """Handles YouTube video uploads and channel management."""
    
    def __init__(self, client_secrets_file: str = None):
        """
        Initialize YouTubeUploader.
        
        Args:
            client_secrets_file: Path to OAuth client secrets JSON file
        """
        self.client_secrets_file = client_secrets_file or CLIENT_SECRETS_FILE
        self.credentials_file = "youtube-oauth2.json"
        self.youtube_service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with YouTube API using OAuth 2.0."""
        creds = None
        
        # Load existing credentials
        if os.path.exists(self.credentials_file):
            try:
                creds = Credentials.from_authorized_user_file(self.credentials_file, YOUTUBE_SCOPES)
            except Exception as e:
                logger.warning(f"Error loading credentials: {e}")
        
        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Error refreshing credentials: {e}")
                    creds = None
            
            if not creds:
                if not os.path.exists(self.client_secrets_file):
                    raise FileNotFoundError(
                        f"OAuth credentials file not found: {self.client_secrets_file}\n"
                        "Please download your OAuth credentials from Google Cloud Console."
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file,
                    YOUTUBE_SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(self.credentials_file, 'w') as token:
                token.write(creds.to_json())
        
        # Build YouTube service
        http = AuthorizedHttp(creds, http=httplib2.Http())
        self.youtube_service = build(
            YOUTUBE_API_SERVICE_NAME,
            YOUTUBE_API_VERSION,
            http=http
        )
        
        logger.info("Successfully authenticated with YouTube API")
    
    def upload_video(self, video_path: str, metadata: Dict, 
                    privacy_status: str = None, category_id: str = None) -> Optional[str]:
        """
        Upload a video to YouTube.
        
        Args:
            video_path: Path to video file
            metadata: Dictionary with title, description, tags
            privacy_status: Privacy status (public, private, unlisted)
            category_id: YouTube category ID
            
        Returns:
            Video ID if successful, None otherwise
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        privacy_status = privacy_status or metadata.get("privacy_status", DEFAULT_PRIVACY_STATUS)
        category_id = category_id or metadata.get("category_id", DEFAULT_CATEGORY_ID)
        
        if privacy_status not in VALID_PRIVACY_STATUSES:
            raise ValueError(f"Invalid privacy status: {privacy_status}")
        
        # Prepare video metadata
        body = {
            "snippet": {
                "title": metadata.get("title", "Untitled Video"),
                "description": metadata.get("description", ""),
                "tags": metadata.get("tags", []),
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": privacy_status
            }
        }
        
        # Create media upload object
        media = MediaFileUpload(
            video_path,
            chunksize=-1,
            resumable=True,
            mimetype="video/*"
        )
        
        # Create insert request
        insert_request = self.youtube_service.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )
        
        # Execute upload with retry logic
        return self._resumable_upload(insert_request)
    
    def _resumable_upload(self, insert_request) -> Optional[str]:
        """
        Execute resumable upload with exponential backoff retry logic.
        
        Args:
            insert_request: YouTube API insert request object
            
        Returns:
            Video ID if successful, None otherwise
        """
        response = None
        error = None
        retry = 0
        
        while response is None:
            try:
                logger.info("Uploading video...")
                status, response = insert_request.next_chunk()
                
                if response is not None:
                    if 'id' in response:
                        video_id = response['id']
                        logger.info(f"Video uploaded successfully! Video ID: {video_id}")
                        logger.info(f"Video URL: https://www.youtube.com/watch?v={video_id}")
                        return video_id
                    else:
                        logger.error(f"Upload failed with unexpected response: {response}")
                        return None
                        
            except HttpError as e:
                error_content = str(e.content) if hasattr(e, 'content') else str(e)
                error_reason = ""
                error_message = ""
                
                # Try to extract error reason from response
                try:
                    import json
                    if hasattr(e, 'content'):
                        error_data = json.loads(e.content.decode('utf-8'))
                        error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', '')
                        error_message = error_data.get('error', {}).get('message', '')
                except:
                    pass
                
                # Check for quota exceeded error (403 with quotaExceeded reason)
                if e.resp.status == 403 and ('quotaExceeded' in error_reason or 'quota' in error_content.lower() or 'limit' in error_content.lower()):
                    logger.error("\n" + "="*60)
                    logger.error("YOUTUBE API QUOTA EXCEEDED")
                    logger.error("="*60)
                    logger.error("You have reached your daily YouTube API quota limit.")
                    logger.error("")
                    logger.error("YouTube API Quota Limits:")
                    logger.error("  • Default quota: 10,000 units per day")
                    logger.error("  • Video upload (videos.insert): 1,600 units per upload")
                    logger.error("  • Approximate uploads per day: ~6 videos (with default quota)")
                    logger.error("")
                    logger.error("Solutions:")
                    logger.error("  1. Wait until tomorrow (quota resets daily)")
                    logger.error("  2. Request a quota increase:")
                    logger.error("     - Go to Google Cloud Console")
                    logger.error("     - Select your project")
                    logger.error("     - Navigate to 'APIs & Services' > 'Quotas'")
                    logger.error("     - Search for 'YouTube Data API v3'")
                    logger.error("     - Request increase for 'Queries per day'")
                    logger.error("")
                    logger.error("  3. Check your current quota usage:")
                    logger.error("     - Google Cloud Console > APIs & Services > Dashboard")
                    logger.error("     - Look for 'YouTube Data API v3' usage")
                    logger.error("")
                    logger.error(f"Error details: {error_message if error_message else error_content}")
                    logger.error("="*60)
                    return None
                
                # Check for other 403 errors (forbidden)
                if e.resp.status == 403:
                    logger.error("\n" + "="*60)
                    logger.error("YOUTUBE API ERROR (403 Forbidden)")
                    logger.error("="*60)
                    logger.error("Possible causes:")
                    logger.error("  • Quota exceeded (see above)")
                    logger.error("  • Invalid OAuth credentials")
                    logger.error("  • Insufficient permissions")
                    logger.error("  • Account restrictions")
                    logger.error("")
                    logger.error(f"Error: {error_message if error_message else error_content}")
                    logger.error("="*60)
                    return None
                
                if e.resp.status in RETRIABLE_STATUS_CODES:
                    error = f"A retriable HTTP error {e.resp.status} occurred: {error_content}"
                else:
                    logger.error(f"Non-retriable HTTP error {e.resp.status}: {error_content}")
                    raise
                    
            except RETRIABLE_EXCEPTIONS as e:
                error = f"A retriable error occurred: {e}"
            
            if error is not None:
                logger.warning(error)
                retry += 1
                
                if retry > MAX_RETRIES:
                    logger.error("No longer attempting to retry.")
                    return None
                
                max_sleep = 2 ** retry
                sleep_seconds = random.random() * max_sleep
                logger.info(f"Sleeping {sleep_seconds:.2f} seconds and then retrying...")
                time.sleep(sleep_seconds)
                error = None
        
        return None
    
    def update_video_metadata(self, video_id: str, metadata: Dict) -> bool:
        """
        Update video metadata (title, description, tags).
        
        Args:
            video_id: YouTube video ID
            metadata: Dictionary with updated metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            body = {
                "id": video_id,
                "snippet": {
                    "title": metadata.get("title"),
                    "description": metadata.get("description"),
                    "tags": metadata.get("tags", [])
                }
            }
            
            # Get existing video to preserve other fields
            video_response = self.youtube_service.videos().list(
                part="snippet",
                id=video_id
            ).execute()
            
            if not video_response.get("items"):
                logger.error(f"Video {video_id} not found")
                return False
            
            existing_snippet = video_response["items"][0]["snippet"]
            body["snippet"]["categoryId"] = existing_snippet.get("categoryId")
            
            # Update video
            update_response = self.youtube_service.videos().update(
                part="snippet",
                body=body
            ).execute()
            
            logger.info(f"Video metadata updated successfully: {video_id}")
            return True
            
        except HttpError as e:
            logger.error(f"Error updating video metadata: {e}")
            return False
    
    def get_channel_info(self) -> Optional[Dict]:
        """
        Get information about the authenticated user's channel.
        
        Returns:
            Dictionary with channel information, or None if failed
        """
        try:
            channels_response = self.youtube_service.channels().list(
                part="snippet,contentDetails,statistics",
                mine=True
            ).execute()
            
            if channels_response.get("items"):
                channel = channels_response["items"][0]
                return {
                    "id": channel["id"],
                    "title": channel["snippet"]["title"],
                    "description": channel["snippet"]["description"],
                    "subscriber_count": channel["statistics"].get("subscriberCount", "0"),
                    "video_count": channel["statistics"].get("videoCount", "0"),
                    "view_count": channel["statistics"].get("viewCount", "0")
                }
            return None
            
        except HttpError as e:
            logger.error(f"Error getting channel info: {e}")
            return None

