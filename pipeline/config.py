"""
Settings and project paths. Secrets come from .env / .env.local (never hardcode keys).
"""
import os

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# .env.local is written by `elevenlabs onboard` (ELEVENLABS_API_KEY); .env holds everything else.
load_dotenv(os.path.join(ROOT, ".env"))
load_dotenv(os.path.join(ROOT, ".env.local"))

# ----------------------------
# Project layout
# ----------------------------
CONFIG_DIR = os.path.join(ROOT, "config")
DATA_DIR = os.path.join(ROOT, "data")
ANIMATOR_DIR = os.path.join(ROOT, "animator")
MUSIC_DIR = os.path.join(ROOT, "assets", "music")
OUTPUT_DIR = os.path.join(ROOT, "generated_videos")
LOGS_DIR = os.path.join(ROOT, "logs")

GENERATOR_CONFIG_PATH = os.path.join(CONFIG_DIR, "generator_config.json")
VOICES_PATH = os.path.join(CONFIG_DIR, "voices.json")
TRENDS_PATH = os.path.join(CONFIG_DIR, "trends.json")
KIT_PATH = os.path.join(ANIMATOR_DIR, "src", "kit.json")

HISTORY_DB_PATH = os.path.join(DATA_DIR, "video_history.db")
USED_TOPICS_PATH = os.path.join(DATA_DIR, "used_topics.json")
REJECTED_TOPICS_PATH = os.path.join(DATA_DIR, "rejected_topics.json")
AUTOPOSTER_STATE_PATH = os.path.join(DATA_DIR, "autoposter_state.json")
AUTOPOSTER_LOCK_PATH = os.path.join(DATA_DIR, "autoposter.lock")
VOICE_CACHE_DIR = os.path.join(DATA_DIR, "voice_cache")

# Screenplays written ahead of time (by hand or by the Cursor agent) are used before Ollama writes one.
SCREENPLAY_QUEUE_DIR = os.path.join(ROOT, "screenplays", "queue")
SCREENPLAY_USED_DIR = os.path.join(ROOT, "screenplays", "used")

# ----------------------------
# Story writing (local Ollama)
# ----------------------------
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
# Qwen3.8 27B at 3-bit (~13 GB): the strongest writer that fits the GPU memory macOS allows on a 24 GB Mac.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q3_K_XL")
# Smaller model for quick yes/no jobs (story triage, safety second opinion). Falls back to OLLAMA_MODEL.
OLLAMA_FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", "")

# ----------------------------
# Voices (ElevenLabs)
# ----------------------------
# Primary key, plus optional backups. When one month's characters run out, VoiceRenderer
# rotates to the next key with quota, and snaps back to the primary once it regenerates.
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_v4")
ELEVENLABS_KEY_STATE_PATH = os.path.join(DATA_DIR, "elevenlabs_key_state.json")


def elevenlabs_api_keys() -> list:
    """Ordered ElevenLabs keys: primary first, then KEY_2 / KEY_3 / comma-separated list."""
    keys: list = []
    multi = os.getenv("ELEVENLABS_API_KEYS", "")
    if multi.strip():
        keys.extend(k.strip() for k in multi.split(",") if k.strip())
    for name in ("ELEVENLABS_API_KEY", "ELEVENLABS_API_KEY_2", "ELEVENLABS_API_KEY_3"):
        value = (os.getenv(name) or "").strip()
        if value and value not in keys:
            keys.append(value)
    return keys

# Node binary used to run the animator (Remotion needs Node >= 18). Auto-detected when empty.
NODE_BINARY = os.getenv("NODE_BINARY", "")

# Buffer publishes one hosted video to each connected channel (YouTube, TikTok, ...).
BUFFER_API_KEY = os.getenv("BUFFER_API_KEY", "")
BUFFER_API_URL = os.getenv("BUFFER_API_URL", "https://api.buffer.com")

# ----------------------------
# YouTube
# ----------------------------
CLIENT_SECRETS_FILE = os.path.join(ROOT, "client_secrets.json")
YOUTUBE_TOKEN_FILE = os.path.join(ROOT, "youtube-oauth2.json")
# Cloud Agents secrets are env vars only (no file upload). Paste each JSON file's
# full contents into these, and materialize_secret_files() writes them to disk.
CLIENT_SECRETS_JSON = os.getenv("CLIENT_SECRETS_JSON", "")
YOUTUBE_OAUTH_JSON = os.getenv("YOUTUBE_OAUTH_JSON", "")
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
# Needed for updating video status/privacy (Unlisted -> Public).
YOUTUBE_MANAGE_SCOPE = "https://www.googleapis.com/auth/youtube"
YOUTUBE_SCOPES = [
    YOUTUBE_UPLOAD_SCOPE,
    YOUTUBE_READONLY_SCOPE,
    YOUTUBE_MANAGE_SCOPE,
]
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

DEFAULT_CATEGORY_ID = "22"  # People & Blogs
DEFAULT_PRIVACY_STATUS = "public"
VALID_PRIVACY_STATUSES = ("public", "private", "unlisted")

# Retry Configuration
MAX_RETRIES = 10
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]  # Note: 403 (quota exceeded) is NOT retriable

# YouTube API quota: 10,000 units/day by default; one upload (videos.insert) costs 1,600 units.

# Only upload to this specific channel
REQUIRED_CHANNEL_NAME = os.getenv("REQUIRED_CHANNEL_NAME", "RedditReviews")


def materialize_secret_files() -> None:
    """Write YouTube OAuth JSON files from env vars when Cloud Agents secrets are used."""
    for path, raw in (
        (CLIENT_SECRETS_FILE, CLIENT_SECRETS_JSON),
        (YOUTUBE_TOKEN_FILE, YOUTUBE_OAUTH_JSON),
    ):
        text = (raw or "").strip()
        if not text:
            continue
        # Allow secrets UIs that wrap JSON in single quotes.
        if (text.startswith("'") and text.endswith("'")) or (text.startswith('"') and text.endswith('"')):
            text = text[1:-1]
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
            if not text.endswith("\n"):
                f.write("\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def validate_config(need_voices: bool = True) -> list:
    """Returns a list of blocking configuration problems."""
    materialize_secret_files()
    errors = []
    if need_voices and not elevenlabs_api_keys():
        errors.append(
            "ELEVENLABS_API_KEY is not set (run `npx -y @elevenlabs/cli@latest onboard init` in the project folder, "
            "or add ELEVENLABS_API_KEY / ELEVENLABS_API_KEY_2 to .env.local)"
        )
    if not os.path.exists(CLIENT_SECRETS_FILE):
        errors.append(
            f"{os.path.basename(CLIENT_SECRETS_FILE)} not found. Add the file locally, or set CLIENT_SECRETS_JSON "
            "in Cloud Agents secrets to the full JSON contents."
        )
    return errors
