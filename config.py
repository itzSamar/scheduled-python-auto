"""
Configuration management for YouTube Auto-Posting System.
Loads API keys from environment variables and provides default settings.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
DECART_API_KEY = os.getenv("DECART_API_KEY", "")
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY", "sk_V2_hgu_kF8e1wR7N0S_rwGrfxZZHu5zHZdIMoUsQcvDJi9mknRh")
HF_API_KEY = os.getenv("HF_API_KEY", "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")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "ieHmqHRg1utOegnSmmKqH9fBI7SqzNRz72KMEyZRJXxBU2zMvNkKwL0e")  # Free API key from https://www.pexels.com/api/

# YouTube OAuth Configuration
CLIENT_SECRETS_FILE = "client_secrets.json"
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
# Combined scopes for both uploading and reading channel info
YOUTUBE_SCOPES = [
    YOUTUBE_UPLOAD_SCOPE,
    YOUTUBE_READONLY_SCOPE
]
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# Default Video Settings
DEFAULT_CATEGORY_ID = "22"  # People & Blogs
DEFAULT_PRIVACY_STATUS = "public"  # Default to public for YouTube Shorts
VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")

# API Endpoints
DECART_API_BASE_URL = "https://api.decart.ai/v1"
DECART_TEXT_TO_VIDEO_MODEL = "lucy-pro-t2v"  # Text-to-video model

# Retry Configuration
MAX_RETRIES = 10
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]  # Note: 403 (quota exceeded) is NOT retriable

# YouTube API Quota Information
# Default quota: 10,000 units per day
# Video upload (videos.insert): 1,600 units per upload
# Approximate uploads per day: ~6 videos (with default quota)
# To increase quota: Google Cloud Console > APIs & Services > Quotas

# Video Generation Settings
VIDEO_GENERATION_TIMEOUT = 900  # 15 minutes timeout for video generation (HeyGen can take longer, especially with queue)

# Background Footage (YouTube "pot")
# Use a single known-good Minecraft parkour background video and clip random segments from it.
BACKGROUND_POT_URL = os.getenv("BACKGROUND_POT_URL", "https://www.youtube.com/watch?v=7yl7Wc1dtWc")

# Channel Configuration
REQUIRED_CHANNEL_NAME = "RedditReviews"  # Only upload to this specific channel

def validate_config():
    """Validate that required configuration is present."""
    errors = []
    
    # HeyGen API key is required for video generation
    if not HEYGEN_API_KEY:
        errors.append("HEYGEN_API_KEY is not set in .env file")
    
    if not os.path.exists(CLIENT_SECRETS_FILE):
        errors.append(f"{CLIENT_SECRETS_FILE} file not found. Please add your YouTube OAuth credentials.")
    
    return errors

