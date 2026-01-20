#!/usr/bin/env python3
"""
HeyGen Video Generation Script
Generates videos using HeyGen API, downloads them, and saves metadata.
"""
import sys
import os
import requests
import time
import json
from datetime import datetime
from typing import Dict, Optional

# HeyGen API configuration
HEYGEN_API_KEY = "sk_V2_hgu_kF8e1wR7N0S_rwGrfxZZHu5zHZdIMoUsQcvDJi9mknRh"
HEYGEN_API_BASE_URL = "https://api.heygen.com/v1"

HEYGEN_HEADERS = {
    "X-API-KEY": HEYGEN_API_KEY,
    "Content-Type": "application/json"
}

# Output directory
GENERATED_VIDEOS_DIR = "generated_videos"

# Import ContentOptimizer for metadata generation
try:
    from content_optimizer import ContentOptimizer
except ImportError:
    print("Warning: content_optimizer not found. Metadata generation will be simplified.")
    ContentOptimizer = None


def ensure_output_directory():
    """Ensure the generated_videos directory exists."""
    if not os.path.exists(GENERATED_VIDEOS_DIR):
        os.makedirs(GENERATED_VIDEOS_DIR)
        print(f"✓ Created directory: {GENERATED_VIDEOS_DIR}")


def generate_metadata(video_description: str, keywords: list = None) -> Dict:
    """
    Generate optimized metadata (title, description, hashtags) for the video.
    
    Args:
        video_description: Description of what the video should be about
        keywords: Optional list of keywords
        
    Returns:
        Dictionary with title, description, hashtags, and tags
    """
    if ContentOptimizer:
        optimizer = ContentOptimizer()
        trend_data = {
            "title": video_description,
            "keywords": keywords or []
        }
        metadata = optimizer.optimize_metadata(trend_data)
        return metadata
    else:
        # Fallback simple metadata generation
        title = f"{video_description[:50]} - AI Generated Video"
        description = f"This video is about: {video_description}\n\n"
        description += "Generated using HeyGen AI video generation.\n\n"
        
        # Simple hashtag generation
        words = video_description.lower().split()
        hashtags = [f"#{word}" for word in words[:5] if len(word) > 3]
        
        return {
            "title": title,
            "description": description + " ".join(hashtags),
            "hashtags": [h.replace("#", "") for h in hashtags],
            "tags": words[:10]
        }


def list_heygen_avatars():
    """List available HeyGen avatars."""
    url = "https://api.heygen.com/v2/avatars"
    
    try:
        response = requests.get(url, headers=HEYGEN_HEADERS, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            avatars = result.get("data", {}).get("avatars", []) or result.get("avatars", [])
            return avatars
        else:
            print(f"✗ Failed to list avatars. Status: {response.status_code}")
            return []
    except Exception as e:
        print(f"✗ Error listing avatars: {e}")
        return []


def list_heygen_voices():
    """List available HeyGen voices."""
    url = "https://api.heygen.com/v2/voices"
    
    try:
        response = requests.get(url, headers=HEYGEN_HEADERS, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            voices = result.get("data", {}).get("voices", []) or result.get("voices", [])
            return voices
        else:
            print(f"✗ Failed to list voices. Status: {response.status_code}")
            return []
    except Exception as e:
        print(f"✗ Error listing voices: {e}")
        return []


def create_heygen_video(script: str, avatar_id: str = None, voice_id: str = None, video_name: str = None) -> Optional[str]:
    """
    Create a video using HeyGen API v2.
    
    Args:
        script: Script/text for the video (max 5000 characters)
        avatar_id: Avatar ID (REQUIRED)
        voice_id: Voice ID (REQUIRED)
        video_name: Optional name for the video
        
    Returns:
        Video ID if successful, None otherwise
    """
    if not HEYGEN_API_KEY:
        print("✗ ERROR: HeyGen API key not set!")
        print("Please set HEYGEN_API_KEY in the script or as environment variable.")
        return None
    
    if not avatar_id or not voice_id:
        print("✗ ERROR: avatar_id and voice_id are REQUIRED!")
        print("   Use list_heygen_avatars() and list_heygen_voices() to get available IDs")
        return None
    
    # Use the correct HeyGen v2 API endpoint
    url = "https://api.heygen.com/v2/video/generate"
    
    # Build payload according to HeyGen API v2 structure
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "text",
                    "input_text": script,
                    "voice_id": voice_id,
                    "speed": 1.0
                }
            }
        ],
        "dimension": {
            "width": 1280,
            "height": 720
        }
    }
    
    print(f"\n🎬 Creating video with HeyGen...")
    print(f"   Script length: {len(script)} characters")
    if avatar_id:
        print(f"   Avatar ID: {avatar_id}")
    if voice_id:
        print(f"   Voice ID: {voice_id}")
    
    try:
        response = requests.post(url, json=payload, headers=HEYGEN_HEADERS, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            video_id = result.get("data", {}).get("video_id") or result.get("video_id") or result.get("data", {}).get("id") or result.get("id")
            if video_id:
                print(f"✓ Video creation started! Video ID: {video_id}")
                return video_id
            else:
                print(f"✗ Unexpected response format: {result}")
                return None
        elif response.status_code == 404:
            print(f"✗ Endpoint not found (404)")
            print(f"   URL tried: {url}")
            print(f"   This might mean:")
            print(f"   1. The API endpoint has changed")
            print(f"   2. Your API key doesn't have access to this endpoint")
            print(f"   3. The endpoint requires different parameters")
            print(f"\n   Please check:")
            print(f"   - Your HeyGen dashboard: https://app.heygen.com/")
            print(f"   - API documentation: https://docs.heygen.com/")
            print(f"   - Ensure your API key is active and has the right permissions")
            return None
        elif response.status_code == 401:
            print(f"✗ Authentication failed (401)")
            print(f"   Your API key may be invalid or expired")
            print(f"   Please check your API key in HeyGen dashboard")
            return None
        elif response.status_code == 400:
            print(f"✗ Bad request (400)")
            print(f"   Response: {response.text[:500]}")
            print(f"   This usually means required parameters are missing")
            print(f"   Required: avatar_id, voice_id, script")
            return None
        else:
            print(f"✗ Failed to create video. Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return None
            
    except requests.exceptions.ConnectionError as e:
        print(f"✗ Connection error: {e}")
        print(f"   Check your internet connection")
        return None
    except Exception as e:
        print(f"✗ ERROR creating video: {e}")
        import traceback
        traceback.print_exc()
        return None


def check_video_status(video_id: str, max_wait_time: int = 600, poll_interval: int = 10) -> Optional[str]:
    """
    Poll for video completion and return video URL.
    
    Args:
        video_id: Video ID to check
        max_wait_time: Maximum time to wait in seconds (default 10 minutes)
        poll_interval: Time between polls in seconds (default 10 seconds)
        
    Returns:
        Video URL if completed, None otherwise
    """
    # Use v1 API endpoint for status check (HeyGen uses v1 for status)
    status_url = f"https://api.heygen.com/v1/video_status.get"
    
    start_time = time.time()
    
    print(f"\n⏳ Waiting for video to be ready...")
    print(f"   Video ID: {video_id}")
    
    while time.time() - start_time < max_wait_time:
        try:
            params = {"video_id": video_id}
            response = requests.get(status_url, params=params, headers=HEYGEN_HEADERS, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                data = result.get("data", {}) or result
                status = data.get("status", "").lower()
                
                print(f"   Status: {status}")
                
                if status == "completed":
                    # HeyGen returns video_url in the response
                    video_url = data.get("video_url") or data.get("url") or data.get("download_url")
                    if video_url:
                        print(f"✓ Video completed!")
                        return video_url
                    else:
                        print(f"✗ Video completed but no URL found in response")
                        print(f"Response data: {data}")
                        return None
                elif status in ["failed", "error"]:
                    error_msg = data.get("error", "Unknown error")
                    print(f"✗ Video generation failed: {error_msg}")
                    return None
                elif status in ["processing", "pending", "waiting", "generating"]:
                    # Continue polling
                    pass
                else:
                    print(f"   Unknown status: {status}")
            
            time.sleep(poll_interval)
                    
        except Exception as e:
            print(f"✗ Error checking status: {e}")
            time.sleep(poll_interval)
    
    print(f"✗ Timeout waiting for video (waited {max_wait_time}s)")
    return None


def download_video(video_url: str, output_path: str) -> bool:
    """
    Download video from URL.
    
    Args:
        video_url: URL of the video to download
        output_path: Path to save the video
        
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"\n📥 Downloading video...")
        print(f"   URL: {video_url[:80]}...")
        
        response = requests.get(video_url, timeout=120, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r   Progress: {percent:.1f}% ({downloaded}/{total_size} bytes)", end='')
        
        print()  # New line after progress
        file_size = os.path.getsize(output_path)
        print(f"✓ Video downloaded successfully!")
        print(f"   Saved to: {output_path}")
        print(f"   File size: {file_size / 1024 / 1024:.2f} MB")
        return True
        
    except Exception as e:
        print(f"✗ ERROR downloading video: {e}")
        return False


def save_metadata(metadata: Dict, video_filename: str):
    """
    Save metadata to JSON file alongside the video.
    
    Args:
        metadata: Dictionary with video metadata
        video_filename: Name of the video file
    """
    metadata_filename = video_filename.replace('.mp4', '_metadata.json')
    metadata_path = os.path.join(GENERATED_VIDEOS_DIR, metadata_filename)
    
    metadata_with_info = {
        **metadata,
        "generated_at": datetime.now().isoformat(),
        "video_file": video_filename,
        "source": "HeyGen API"
    }
    
    try:
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata_with_info, f, indent=2, ensure_ascii=False)
        print(f"✓ Metadata saved to: {metadata_path}")
    except Exception as e:
        print(f"✗ Error saving metadata: {e}")


def generate_video_with_metadata(
    video_description: str,
    keywords: list = None,
    video_name: str = None,
    avatar_id: str = None,
    voice_id: str = None
) -> Optional[Dict]:
    """
    Complete workflow: Generate video, download, and save metadata.
    
    Args:
        video_description: Description of what the video should be about
        template_id: HeyGen template ID
        keywords: Optional list of keywords
        video_name: Optional name for the video
        
    Returns:
        Dictionary with video info and metadata, or None if failed
    """
    print("=" * 60)
    print("HeyGen Video Generation")
    print("=" * 60)
    
    # Ensure output directory exists
    ensure_output_directory()
    
    # Generate metadata
    print(f"\n📝 Generating metadata for video...")
    print(f"   Description: {video_description}")
    metadata = generate_metadata(video_description, keywords)
    print(f"✓ Title: {metadata['title']}")
    print(f"✓ Hashtags: {', '.join(metadata.get('hashtags', [])[:5])}")
    
    # Create video
    script = video_description  # Use description as script, or customize
    video_id = create_heygen_video(script, avatar_id, voice_id, video_name)
    
    if not video_id:
        return None
    
    # Wait for video to be ready
    video_url = check_video_status(video_id)
    
    if not video_url:
        return None
    
    # Download video
    timestamp = int(time.time())
    video_filename = f"video_{timestamp}.mp4"
    video_path = os.path.join(GENERATED_VIDEOS_DIR, video_filename)
    
    if not download_video(video_url, video_path):
        return None
    
    # Save metadata
    save_metadata(metadata, video_filename)
    
    return {
        "video_id": video_id,
        "video_path": video_path,
        "video_filename": video_filename,
        "video_url": video_url,
        "metadata": metadata
    }


if __name__ == "__main__":
    # Check for API key
    if not HEYGEN_API_KEY:
        # Try to get from environment variable
        HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY", "")
        if HEYGEN_API_KEY:
            HEYGEN_HEADERS["X-API-KEY"] = HEYGEN_API_KEY
    
    if not HEYGEN_API_KEY:
        print("✗ ERROR: HeyGen API key not found!")
        print("\nPlease either:")
        print("1. Set HEYGEN_API_KEY in the script")
        print("2. Set it as environment variable: export HEYGEN_API_KEY=your_key")
        print("3. Add it to your .env file")
        sys.exit(1)
    
    # Example usage
    try:
        VIDEO_DESCRIPTION = "A cat walking in a sunny garden, exploring nature peacefully"
        
        # First, get available avatars and voices
        print("\n" + "=" * 60)
        print("Fetching available avatars and voices...")
        print("=" * 60)
        
        avatars = list_heygen_avatars()
        voices = list_heygen_voices()
        
        if avatars:
            print(f"\n✓ Found {len(avatars)} avatar(s)")
            # Use first available avatar
            AVATAR_ID = avatars[0].get("avatar_id") or avatars[0].get("id")
            avatar_name = avatars[0].get("name") or avatars[0].get("avatar_name") or "Unknown"
            print(f"   Using avatar: {avatar_name} (ID: {AVATAR_ID})")
        else:
            print("\n✗ No avatars found. Cannot create video without avatar_id.")
            sys.exit(1)
        
        if voices:
            print(f"\n✓ Found {len(voices)} voice(s)")
            # Use first available voice
            VOICE_ID = voices[0].get("voice_id") or voices[0].get("id")
            voice_name = voices[0].get("name") or voices[0].get("voice_name") or "Unknown"
            print(f"   Using voice: {voice_name} (ID: {VOICE_ID})")
        else:
            print("\n✗ No voices found. Cannot create video without voice_id.")
            sys.exit(1)
        
        result = generate_video_with_metadata(
            video_description=VIDEO_DESCRIPTION,
            keywords=["cat", "nature", "garden", "animals"],
            video_name="Cat in Garden Video",
            avatar_id=AVATAR_ID,
            voice_id=VOICE_ID
        )
        
        print("\n" + "=" * 60)
        if result:
            print("✓ SUCCESS! Video generated and saved.")
            print(f"\nVideo saved to: {result['video_path']}")
            print(f"Metadata saved alongside video")
            print(f"\nTitle: {result['metadata']['title']}")
            print(f"Hashtags: {', '.join(result['metadata'].get('hashtags', []))}")
            sys.exit(0)
        else:
            print("✗ FAILED - Check errors above")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
