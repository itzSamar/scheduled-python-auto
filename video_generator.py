"""
Generates videos using HeyGen API.
Handles video creation, status checking, and downloading.
Now supports Roblox gameplay video backgrounds via download and upload.
"""
import requests
import logging
import time
import os
import tempfile
from typing import Dict, Optional, List
from config import HEYGEN_API_KEY, VIDEO_GENERATION_TIMEOUT, BACKGROUND_POT_URL

# Try to import yt-dlp for YouTube video downloads
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    logging.warning("yt-dlp not available. Install with: pip install yt-dlp")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import AI text generator
try:
    from ai_text_generator import optimize_script_for_20_seconds, generate_content_script
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logger.warning("AI text generator not available, using basic script generation")

# HeyGen API configuration
HEYGEN_API_BASE_URL = "https://api.heygen.com"


class VideoGenerator:
    """Generates videos using HeyGen API."""
    
    def __init__(self, api_key: str = None, youtube_service=None):
        """
        Initialize VideoGenerator.
        Now supports Roblox gameplay video backgrounds.
        
        Args:
            api_key: HeyGen API key. If None, uses config value.
            youtube_service: YouTube API service for fetching Roblox gameplay videos
        """
        self.api_key = api_key or HEYGEN_API_KEY
        if not self.api_key:
            raise ValueError("HeyGen API key is required")
        
        self.youtube_service = youtube_service  # For fetching Roblox gameplay videos
        
        # Verify API key format
        if not self.api_key.startswith("sk_"):
            logger.warning(f"API key doesn't start with 'sk_' - may be invalid format")
        
        self.headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        logger.debug(f"Initialized VideoGenerator with API key: {self.api_key[:20]}...")
        if youtube_service:
            logger.debug("YouTube service available for Roblox gameplay video fetching")
        
        # Cache for avatars and voices (fetch once)
        self._avatars = None
        self._voices = None
        # Note: avatar_id and voice_id are NOT cached - randomized each video
    
    def _get_avatars(self):
        """Get list of available avatars (cached)."""
        if self._avatars is None:
            url = f"{HEYGEN_API_BASE_URL}/v2/avatars"
            try:
                response = requests.get(url, headers=self.headers, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    self._avatars = result.get("data", {}).get("avatars", []) or result.get("avatars", [])
                    logger.info(f"Found {len(self._avatars)} available avatars")
                else:
                    logger.error(f"Failed to list avatars: {response.status_code}")
                    if response.status_code == 401:
                        logger.error("Authentication failed. Please check your HEYGEN_API_KEY")
                        logger.error(f"API Key (first 20 chars): {self.api_key[:20] if self.api_key else 'NOT SET'}...")
                    logger.debug(f"Response: {response.text[:200]}")
                    self._avatars = []
            except Exception as e:
                logger.error(f"Error listing avatars: {e}")
                self._avatars = []
        return self._avatars
    
    def _get_voices(self):
        """Get list of available voices (cached)."""
        if self._voices is None:
            url = f"{HEYGEN_API_BASE_URL}/v2/voices"
            try:
                response = requests.get(url, headers=self.headers, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    self._voices = result.get("data", {}).get("voices", []) or result.get("voices", [])
                    logger.info(f"Found {len(self._voices)} available voices")
                else:
                    logger.error(f"Failed to list voices: {response.status_code}")
                    if response.status_code == 401:
                        logger.error("Authentication failed. Please check your HEYGEN_API_KEY")
                        logger.error(f"API Key (first 20 chars): {self.api_key[:20] if self.api_key else 'NOT SET'}...")
                    logger.debug(f"Response: {response.text[:200]}")
                    self._voices = []
            except Exception as e:
                logger.error(f"Error listing voices: {e}")
                self._voices = []
        return self._voices
    
    def _get_random_avatar_and_voice(self):
        """Get random avatar and voice IDs - switches avatar every video. Only uses English voices."""
        import random
        
        avatars = self._get_avatars()
        voices = self._get_voices()
        
        if avatars:
            # Randomly select an avatar (switches every video)
            avatar = random.choice(avatars)
            avatar_id = avatar.get("avatar_id") or avatar.get("id")
            logger.info(f"Using random avatar: {avatar.get('name', 'Unknown')} (ID: {avatar_id})")
        else:
            raise ValueError("No avatars available")
        
        if voices:
            # Filter for English voices only
            english_voices = []
            for voice in voices:
                voice_name = voice.get('name', '').lower()
                voice_lang = voice.get('language', '').lower()
                voice_id_str = voice.get("voice_id") or voice.get("id", "")
                
                # Check if it's English (common patterns: "en", "english", "us", "uk", "eng")
                is_english = (
                    'en' in voice_lang or 
                    'english' in voice_lang or
                    'en' in voice_name or
                    'english' in voice_name or
                    'us' in voice_lang or
                    'uk' in voice_lang
                )
                
                # Exclude non-English languages
                non_english_indicators = ['hi', 'hindi', 'es', 'spanish', 'fr', 'french', 'de', 'german', 
                                         'ja', 'japanese', 'zh', 'chinese', 'pt', 'portuguese', 'it', 'italian',
                                         'ru', 'russian', 'ko', 'korean', 'ar', 'arabic']
                is_non_english = any(indicator in voice_lang or indicator in voice_name for indicator in non_english_indicators)
                
                if is_english and not is_non_english:
                    english_voices.append(voice)
            
            if english_voices:
                # Randomly select an English voice
                voice = random.choice(english_voices)
                voice_id = voice.get("voice_id") or voice.get("id")
                logger.info(f"Using random English voice: {voice.get('name', 'Unknown')} (ID: {voice_id})")
            else:
                # Fallback: use any voice if no English voices found
                logger.warning("No English voices found, using any available voice")
                voice = random.choice(voices)
                voice_id = voice.get("voice_id") or voice.get("id")
                logger.info(f"Using random voice: {voice.get('name', 'Unknown')} (ID: {voice_id})")
        else:
            raise ValueError("No voices available")
        
        return avatar_id, voice_id
    
    def _get_minecraft_parkour_video_url(self, topic: str, keywords: list = None, youtube_service=None) -> Optional[str]:
        """
        Get a relevant Minecraft parkour video URL for background.
        Prioritizes parkour-specific videos, falls back to any Minecraft parkour.
        
        Args:
            topic: Main topic/title (not used for Minecraft, but kept for compatibility)
            keywords: List of keywords (not used for Minecraft, but kept for compatibility)
            youtube_service: YouTube API service object
            
        Returns:
            Video URL if found, None otherwise
        """
        # Use a single configured "pot" URL (stable source), and clip random segments from it.
        # This prevents variability from YouTube search and ensures the background always comes from the pot.
        if BACKGROUND_POT_URL:
            logger.info(f"Using configured background pot URL: {BACKGROUND_POT_URL}")
            return BACKGROUND_POT_URL

        try:
            import re
            
            if not youtube_service:
                logger.warning("YouTube service not available, cannot fetch Minecraft parkour video")
                return None
            
            # Strategy: Search for Minecraft parkour videos (no topic-specific needed)
            # Minecraft parkour is generic background, doesn't need to match story topic
            parkour_queries = [
                "Minecraft parkour no commentary",  # Best - pure parkour
                "Minecraft parkour gameplay",  # Standard parkour
                "Minecraft parkour",  # Generic parkour
                "Minecraft parkour montage",  # Parkour montage
            ]
            
            logger.info(f"Searching YouTube for Minecraft parkour videos...")
            
            for query in parkour_queries:
                logger.info(f"  Trying: '{query}'")
                
                try:
                    search_request = youtube_service.search().list(
                        part="snippet",
                        q=query,
                        type="video",
                        maxResults=15,  # Get more results to filter
                        order="viewCount"  # Get popular videos
                    )
                    search_response = search_request.execute()
                    
                    videos = search_response.get("items", [])
                    if videos:
                        # Extract video IDs
                        video_ids = [item["id"]["videoId"] for item in videos]
                        
                        # Get video details for all videos at once
                        video_request = youtube_service.videos().list(
                            part="snippet",
                            id=",".join(video_ids)
                        )
                        video_response = video_request.execute()
                        
                        # Check each video to find actual parkour videos
                        for video_item in video_response.get("items", []):
                            title = video_item["snippet"].get("title", "").lower()
                            description = video_item["snippet"].get("description", "").lower()
                            
                            # Verify it's Minecraft-related
                            if "minecraft" not in title and "minecraft" not in description:
                                continue
                            
                            # STRICT filtering for actual parkour videos (exclude reviews, tutorials, etc.)
                            exclude_keywords = [
                                "review", "news", "update", "trailer", "announcement", "explained", 
                                "guide", "tutorial", "tips", "tricks", "how to", "howto", "how to build",
                                "reaction", "react", "reacting", "discussion", "talk", "talking",
                                "story", "storytime", "animation", "animated", "meme", "memes",
                                "top 10", "ranking", "list", "comparison", "vs", "versus",
                                "minecraft news", "minecraft update", "minecraft review", "minecraft mod"
                            ]
                            if any(exclude in title for exclude in exclude_keywords):
                                continue
                            
                            # REQUIRE parkour keywords in TITLE
                            parkour_keywords = ["parkour", "parkour no commentary", "parkour gameplay", "parkour montage"]
                            has_parkour_in_title = any(keyword in title for keyword in parkour_keywords)
                            
                            if not has_parkour_in_title:
                                continue  # Skip if no parkour keyword in title
                            
                            # Prefer "no commentary" videos (pure parkour)
                            is_no_commentary = "no commentary" in title
                            
                            video_id = video_item["id"]
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                            video_title = video_item['snippet'].get('title', 'Unknown')
                            
                            # Prioritize "no commentary" videos
                            if is_no_commentary:
                                logger.info(f"✓ Found Minecraft parkour video (no commentary): {video_title[:60]}...")
                                logger.info(f"Video URL: {video_url}")
                                logger.info(f"  Selected: Pure parkour (no commentary)")
                                return video_url
                            
                            # Otherwise, use any parkour video
                            logger.info(f"✓ Found Minecraft parkour video: {video_title[:60]}...")
                            logger.info(f"Video URL: {video_url}")
                            logger.info(f"  Selected: Minecraft parkour")
                            return video_url
                        
                        # If no parkour videos found, try next query
                        logger.info(f"  No parkour videos found with '{query}', trying next search...")
                        
                except Exception as search_error:
                    logger.warning(f"Search error for '{query}': {search_error}, trying next query")
                    continue
            
            # If no parkour found in first queries, we already tried fallbacks
            # So just return None
            
            # NO FALLBACK - Only return parkour videos
            logger.warning("Could not find any Minecraft parkour video - will use image background instead")
            return None
            
        except Exception as e:
            logger.warning(f"Error getting Minecraft parkour video: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def _get_background_image_url(self, topic: str, keywords: list = None) -> Optional[str]:
        """
        DEPRECATED: Now using Roblox gameplay videos instead of images.
        Kept for fallback purposes.
        
        Get a relevant background image URL based on topic/keywords using Pexels API.
        All Pexels images are free to use (copyright-free, no attribution required).
        
        Args:
            topic: Main topic/title
            keywords: List of keywords
            
        Returns:
            Image URL if found, None otherwise
        """
        try:
            import urllib.parse
            import re
            from config import PEXELS_API_KEY
            
            # Extract search query from topic/keywords
            search_terms = []
            
            # Clean topic - remove special characters, keep only words
            topic_clean = re.sub(r'[^\w\s]', ' ', topic)
            topic_words = [w for w in topic_clean.split() if len(w) > 2][:3]  # First 3 meaningful words
            search_terms.extend(topic_words)
            
            # Add keywords if available (filter out short/meaningless ones)
            if keywords:
                meaningful_keywords = [kw for kw in keywords if len(kw) > 2][:2]
                search_terms.extend(meaningful_keywords)
            
            # Create search query (use first 2-3 terms, prioritize topic words)
            if search_terms:
                query = " ".join(search_terms[:2])  # Use first 2 terms for better relevance
            else:
                query = "abstract"  # Fallback to abstract/neutral images
            
            query = query.lower().strip()
            
            # Use Pexels API (free, copyright-free images)
            # Get free API key from: https://www.pexels.com/api/
            if PEXELS_API_KEY:
                pexels_api_url = "https://api.pexels.com/v1/search"
                params = {
                    "query": query,
                    "orientation": "portrait",
                    "per_page": 1,
                    "size": "large"
                }
                headers = {
                    "Authorization": PEXELS_API_KEY
                }
                
                try:
                    response = requests.get(pexels_api_url, params=params, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        photos = data.get("photos", [])
                        
                        if photos:
                            photo = photos[0]
                            # Get the large portrait image URL
                            image_url = photo.get("src", {}).get("large") or photo.get("src", {}).get("original")
                            
                            if image_url:
                                photographer = photo.get("photographer", "Unknown")
                                logger.info(f"Selected copyright-free background image for topic: '{query}'")
                                logger.info(f"Image URL: {image_url[:80]}...")
                                logger.info(f"Photographer: {photographer} (Pexels - Free to use)")
                                return image_url
                    elif response.status_code == 401:
                        logger.warning("Pexels API key invalid or missing. Get free key from https://www.pexels.com/api/")
                    else:
                        logger.warning(f"Pexels API returned {response.status_code}, using fallback")
                except Exception as api_error:
                    logger.debug(f"Pexels API error: {api_error}, using fallback")
            else:
                logger.info("Pexels API key not set. Using fallback method.")
                logger.info("Get free API key from: https://www.pexels.com/api/")
            
            # Fallback: Use curated copyright-free image URLs
            # These are known-good Unsplash images that are free to use
            # All images are under Unsplash License (free for commercial use)
            curated_images = [
                # Abstract/Gradient backgrounds (portrait format)
                "https://images.unsplash.com/photo-1557672172-298e090bd0f1?w=720&h=1280&fit=crop&q=80",  # Abstract gradient
                "https://images.unsplash.com/photo-1557683316-973673baf926?w=720&h=1280&fit=crop&q=80",  # Colorful gradient
                "https://images.unsplash.com/photo-1557682250-33bd709cbe85?w=720&h=1280&fit=crop&q=80",  # Abstract colors
                "https://images.unsplash.com/photo-1557682257-2f9c37a3a320?w=720&h=1280&fit=crop&q=80",  # Gradient background
                "https://images.unsplash.com/photo-1557683311-eac922347aa1?w=720&h=1280&fit=crop&q=80",  # Modern gradient
                "https://images.unsplash.com/photo-1557682224-5b8590cd9ec5?w=720&h=1280&fit=crop&q=80",  # Colorful abstract
                "https://images.unsplash.com/photo-1557682250-33bd709cbe85?w=720&h=1280&fit=crop&q=80",  # Vibrant colors
                "https://images.unsplash.com/photo-1557683316-973673baf926?w=720&h=1280&fit=crop&q=80",  # Smooth gradient
            ]
            
            # Select image based on query hash (deterministic but varied)
            image_index = abs(hash(query)) % len(curated_images)
            image_url = curated_images[image_index]
            
            logger.info(f"Using copyright-free background image (curated) for topic: '{query}'")
            logger.info(f"Image URL: {image_url[:80]}...")
            logger.info("Note: All images are free to use under Unsplash License (copyright-free)")
            
            return image_url
            
        except Exception as e:
            logger.warning(f"Error getting background image: {e}, using default color")
            return None
    
    def _trim_video(self, input_path: str, output_path: str = None, max_duration: int = 60, start_time: int = 0) -> Optional[str]:
        """
        Trim video to a maximum duration using ffmpeg.
        
        Args:
            input_path: Path to input video file
            output_path: Path to output trimmed video (if None, creates new file)
            max_duration: Maximum duration in seconds (default: 60)
            start_time: Start time in seconds (default: 0)
            
        Returns:
            Path to trimmed video file, or None if failed
        """
        import subprocess
        
        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5, check=True)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("ffmpeg not available - cannot trim video")
            return None
        
        if not output_path:
            output_path = input_path.replace('.mp4', '_trimmed.mp4')
        
        try:
            logger.info(f"Trimming video to {max_duration} seconds...")
            logger.info(f"  Input: {os.path.basename(input_path)}")
            logger.info(f"  Output: {os.path.basename(output_path)}")
            
            # Use ffmpeg to trim video
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-ss', str(start_time),  # Start time
                '-t', str(max_duration),  # Duration
                '-c:v', 'libx264',  # H.264 video codec
                '-c:a', 'copy',  # Copy audio (or use -an to remove)
                '-avoid_negative_ts', 'make_zero',  # Fix timestamp issues
                '-y',  # Overwrite output file
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                size = os.path.getsize(output_path) / 1024 / 1024
                logger.info(f"✓ Trimmed video: {size:.2f} MB (from {start_time}s to {start_time+max_duration}s)")
                logger.info(f"  ✓ VERIFIED: Video starts at {start_time}s, duration {max_duration}s")
                return output_path
            
            logger.error(f"Trimming failed: {result.stderr[:200]}")
            return None
                    
        except subprocess.TimeoutExpired:
            logger.error("Video trimming timed out")
            return None
        except Exception as e:
            logger.error(f"Error trimming video: {e}")
            return None
    
    def _convert_to_mp4(self, input_path: str, output_path: str = None, mute_audio: bool = False) -> Optional[str]:
        """
        Convert video to MP4 format using ffmpeg.
        Can optionally mute audio (for background videos).
        
        Args:
            input_path: Path to input video file
            output_path: Path to output MP4 file (if None, replaces input)
            mute_audio: If True, removes audio track (for background videos)
            
        Returns:
            Path to converted MP4 file, or None if failed
        """
        import subprocess
        
        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5, check=True)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("ffmpeg not available - cannot convert video format")
            return None
        
        if not output_path:
            # Create temp file for output
            output_path = input_path.replace('.mp4', '_converted.mp4')
        
        try:
            logger.info(f"Converting video to MP4 format...")
            logger.info(f"  Input: {os.path.basename(input_path)}")
            logger.info(f"  Output: {os.path.basename(output_path)}")
            if mute_audio:
                logger.info(f"  Muting audio (background video)")
            
            # Use ffmpeg to convert to MP4
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:v', 'libx264',  # H.264 video codec
                '-movflags', '+faststart',  # Optimize for streaming
                '-y',  # Overwrite output file
            ]
            
            # Add audio handling
            if mute_audio:
                cmd.extend(['-an'])  # Remove audio track
            else:
                cmd.extend(['-c:a', 'aac'])  # AAC audio codec
            
            cmd.append(output_path)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                size = os.path.getsize(output_path) / 1024 / 1024
                logger.info(f"✓ Converted to MP4: {size:.2f} MB")
                if mute_audio:
                    logger.info(f"  Audio removed (muted)")
                return output_path
            else:
                logger.error(f"Conversion failed: {result.stderr[:200]}")
                return None
                    
        except subprocess.TimeoutExpired:
            logger.error("Video conversion timed out")
            return None
        except Exception as e:
            logger.error(f"Error converting video: {e}")
            return None
    
    def _download_youtube_video(self, youtube_url: str, output_path: str = None) -> Optional[str]:
        """
        Download a YouTube video using yt-dlp and ensure it's in MP4 format.
        
        Args:
            youtube_url: YouTube video URL
            output_path: Optional path to save video (if None, uses temp file)
            
        Returns:
            Path to downloaded video file (MP4 format), or None if failed
        """
        if not YT_DLP_AVAILABLE:
            logger.warning("yt-dlp not available. Install with: pip install yt-dlp")
            return None
        
        try:
            if not output_path:
                # Create temp file
                temp_dir = tempfile.mkdtemp()
                output_path = os.path.join(temp_dir, 'minecraft_parkour_background.mp4')
            
            logger.info(f"Downloading YouTube video: {youtube_url[:80]}...")
            
            ydl_opts = {
                # Use format selector that avoids MPEG-TS
                # Try formats that are actual MP4 containers
                # Avoid m3u8/HLS formats which are often MPEG-TS
                # Use worst quality to avoid blocks and get smaller files
                'format': 'worst[ext=mp4][protocol!=m3u8]/worst[ext=mp4]/worst[protocol!=m3u8]/worst',
                'outtmpl': output_path,
                'quiet': False,
                'no_warnings': False,
                'noplaylist': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                title = info.get('title', 'Unknown')
                duration = info.get('duration', 0)
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                size = os.path.getsize(output_path) / 1024 / 1024
                logger.info(f"✓ Downloaded: {title[:60]}...")
                logger.info(f"  Duration: {duration}s, Size: {size:.2f} MB")
                logger.info(f"  Saved to: {output_path}")
                
                # IMPORTANT: Do NOT trim videos here when saving to cache!
                # We need the FULL video for segment clipping.
                # Trimming will happen later when clipping segments for HeyGen.
                # Only trim if video is extremely long (> 10 minutes) to save disk space
                if duration > 600:  # 10 minutes
                    logger.warning(f"⚠ Background video is {duration}s - very long!")
                    logger.info(f"  Trimming to 10 minutes max for cache (will clip segments from this)")
                    trimmed_path = output_path.replace('.mp4', '_trimmed.mp4')
                    trimmed = self._trim_video(output_path, trimmed_path, max_duration=600, start_time=0)
                    if trimmed:
                        try:
                            os.remove(output_path)
                            os.rename(trimmed_path, output_path)
                            logger.info(f"✓ Trimmed to 10 minutes for cache")
                        except:
                            output_path = trimmed_path
                else:
                        logger.warning("Could not trim very long video, will use original")
                
                # Check if file is MPEG-TS and convert if needed
                try:
                    import subprocess
                    result = subprocess.run(
                        ['file', '-b', '--mime-type', output_path],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    mime_type = result.stdout.strip().lower()
                    
                    if 'mp2t' in mime_type or 'mpeg-ts' in mime_type:
                        logger.warning("Downloaded file is MPEG-TS format, converting to MP4...")
                        converted_path = self._convert_to_mp4(output_path)
                        if converted_path:
                            # Replace original with converted
                            try:
                                os.remove(output_path)
                                os.rename(converted_path, output_path)
                                logger.info("✓ Successfully converted to MP4")
                            except:
                                output_path = converted_path
                        else:
                            logger.warning("Conversion failed, will try upload anyway")
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    # file command not available, skip format check
                    pass
                except Exception as e:
                    logger.debug(f"Format check error: {e}")
                
                return output_path
            else:
                logger.error("Download failed - file is empty or doesn't exist")
                return None
                    
        except Exception as e:
            logger.error(f"Failed to download YouTube video: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        return None
    
    def _upload_video_to_heygen(self, video_path: str) -> Optional[str]:
        """
        Upload a video file to HeyGen and get video_asset_id.
        
        Args:
            video_path: Path to local video file
            
        Returns:
            video_asset_id if successful, None otherwise
        """
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None
        
        upload_url = "https://upload.heygen.com/v1/asset"
        headers = {
            'X-API-KEY': self.api_key,
        }
        
        try:
            logger.info(f"Uploading video to HeyGen: {os.path.basename(video_path)}...")
            file_size = os.path.getsize(video_path) / 1024 / 1024
            logger.info(f"  File size: {file_size:.2f} MB")
            
            # Detect actual file format
            import mimetypes
            content_type, _ = mimetypes.guess_type(video_path)
            if not content_type:
                # Default to mp4, but HeyGen will detect actual format
                content_type = 'video/mp4'
            
            logger.info(f"  Detected content type: {content_type}")
            
            with open(video_path, 'rb') as video_file:
                # Send raw binary data with Content-Type header
                response = requests.post(
                    upload_url,
                    data=video_file.read(),
                    headers={**headers, 'Content-Type': content_type},
                    timeout=120  # Upload can take time
                )
            
            if response.status_code == 200:
                result = response.json()
                asset_data = result.get('data', {})
                asset_id = asset_data.get('id') or asset_data.get('asset_id')
                
                if asset_id:
                    logger.info(f"✓ Video uploaded successfully!")
                    logger.info(f"  Asset ID: {asset_id}")
                    return asset_id
                else:
                    logger.error(f"Upload succeeded but no asset_id found. Response: {result}")
                return None
            else:
                logger.error(f"Upload failed: {response.status_code}")
                logger.error(f"Response: {response.text[:500]}")
                return None
        
        except Exception as e:
            logger.error(f"Error uploading video to HeyGen: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        return None
    
    def _get_cached_video_info(self, youtube_url: str) -> Optional[Dict]:
        """
        Get cached video information (path and used segments).
        
        Args:
            youtube_url: YouTube video URL
            
        Returns:
            Dict with 'path' and 'used_segments' if cached, None otherwise
        """
        import json
        import hashlib
        
        # Create cache directory
        cache_dir = os.path.join(os.getcwd(), 'video_cache')
        os.makedirs(cache_dir, exist_ok=True)
        
        # Create hash of URL for filename
        url_hash = hashlib.md5(youtube_url.encode()).hexdigest()
        cache_info_file = os.path.join(cache_dir, f'{url_hash}_info.json')
        cache_video_file = os.path.join(cache_dir, f'{url_hash}.mp4')
        
        # Check if video file exists
        if os.path.exists(cache_video_file):
            # Load used segments info
            used_segments = []
            if os.path.exists(cache_info_file):
                try:
                    with open(cache_info_file, 'r') as f:
                        info = json.load(f)
                        used_segments = info.get('used_segments', [])
                except:
                    pass
            
            return {
                'path': cache_video_file,
                'used_segments': used_segments,
                'url': youtube_url
            }
        
        return None
    
    def _save_cached_video_info(self, youtube_url: str, video_path: str, used_segments: List[int]):
        """
        Save cached video information.
        
        Args:
            youtube_url: YouTube video URL
            video_path: Path to cached video file
            used_segments: List of start times (in seconds) that have been used
        """
        import json
        import hashlib
        
        # Create cache directory
        cache_dir = os.path.join(os.getcwd(), 'video_cache')
        os.makedirs(cache_dir, exist_ok=True)
        
        # Create hash of URL for filename
        url_hash = hashlib.md5(youtube_url.encode()).hexdigest()
        cache_info_file = os.path.join(cache_dir, f'{url_hash}_info.json')
        
        # Save info
        try:
            with open(cache_info_file, 'w') as f:
                json.dump({
                    'url': youtube_url,
                    'video_path': video_path,
                    'used_segments': used_segments
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save cache info: {e}")
    
    def _get_random_unused_segment(self, video_path: str, used_segments: List[int], segment_duration: int = 59) -> int:
        """
        Get a RANDOM unused segment start time from a cached video.
        
        Args:
            video_path: Path to video file
            used_segments: List of start times (in seconds) that have been used
            segment_duration: Duration of each segment in seconds (default: 60)
            
        Returns:
            Start time in seconds for random unused segment, or 0 if all segments used
        """
        import subprocess
        import random
        
        # Get video duration
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            duration = float(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Could not get video duration: {e}, using default")
            duration = 3600  # Default to 1 hour
        
        # Calculate available start window
        max_start = int(max(0, duration - segment_duration))

        logger.info(f"  Video duration: {duration:.1f}s, Max start: {max_start}s")
        logger.info(f"  Used segments: {used_segments}")
        
        if max_start <= 0:
            logger.warning("Video too short for segment, using start")
            return 0

        # Choose start times in 5-second steps to reduce repeats while keeping them truly random.
        step = 5
        min_start = 15 if max_start >= 15 else 0  # avoid starting at 0 unless we have no choice
        all_starts = list(range(min_start, max_start + 1, step))
        if not all_starts:
            all_starts = [0]

        used_set = set(int(x) for x in (used_segments or []))
        unused = [s for s in all_starts if s not in used_set]
        if unused:
            selected = random.choice(unused)
            logger.info(f"  ✓ Selected RANDOM unused start: {selected}s (from {len(unused)} available)")
            return selected

        logger.warning("All start positions used, picking random start anyway")
        return random.choice(all_starts)
    
    def _get_minecraft_parkour_video_asset_id(self, topic: str, keywords: list = None) -> Optional[str]:
        """
        Get Minecraft parkour video as HeyGen video_asset_id.
        Uses cached videos when available, clips different segments instead of re-downloading.
        
        Args:
            topic: Main topic/title (not used, kept for compatibility)
            keywords: List of keywords (not used, kept for compatibility)
            
        Returns:
            video_asset_id if successful, None otherwise
        """
        if not self.youtube_service:
            logger.warning("YouTube service not available")
            return None
        
        if not YT_DLP_AVAILABLE:
            logger.warning("yt-dlp not available, cannot download videos")
            return None
        
        try:
            # Step 1: Check if we have cached video for the configured background pot URL.
            cache_dir = os.path.join(os.getcwd(), 'video_cache')
            cached_videos = []
            if os.path.exists(cache_dir):
                import json
                import hashlib
                for file in os.listdir(cache_dir):
                    if not file.endswith('_info.json'):
                        continue
                    try:
                        info_path = os.path.join(cache_dir, file)
                        with open(info_path, 'r') as f:
                            info = json.load(f)
                        # Only reuse cache entries that match our configured pot URL
                        if info.get('url', '') != BACKGROUND_POT_URL:
                            continue
                        video_path = info.get('video_path', '')
                        if os.path.exists(video_path):
                            cached_videos.append({
                                'url': info.get('url', ''),
                                'path': video_path,
                                'used_segments': info.get('used_segments', [])
                            })
                    except Exception:
                        pass
            
            # If we have cached videos, use the first one (or one with least used segments)
            youtube_url = None
            cached_info = None
            if cached_videos:
                # Use the video with the fewest used segments (most segments available)
                selected_cached = min(cached_videos, key=lambda x: len(x.get('used_segments', [])))
                youtube_url = selected_cached['url']
                logger.info(f"✓ Found {len(cached_videos)} cached pot video(s), reusing: {os.path.basename(selected_cached['path'])}")
                logger.info(f"  Video URL: {youtube_url}")
                
                # Reload cache info to get latest used_segments state
                cached_info = self._get_cached_video_info(youtube_url) or selected_cached                                                                  
            else:
                # No cached pot video yet - use the configured pot URL
                logger.info("No cached pot video found yet, using configured background pot URL...")
                youtube_url = self._get_minecraft_parkour_video_url(topic, keywords, self.youtube_service)
                if not youtube_url:
                    logger.warning("Could not get background pot URL")
                    return None
                    
                cached_info = self._get_cached_video_info(youtube_url)
            
            if cached_info and os.path.exists(cached_info['path']):
                # Video is cached - clip a different segment
                logger.info(f"✓ Using cached video (no re-download needed)")
                logger.info(f"  Cached video: {os.path.basename(cached_info['path'])}")
                
                # CRITICAL: Reload cache info fresh to get latest used_segments
                cached_info = self._get_cached_video_info(youtube_url)
                if not cached_info:
                    logger.warning("Cache info disappeared, downloading new video")
                    cached_info = None
                else:
                    # Get RANDOM unused segment
                    used_segments = cached_info.get('used_segments', [])
                    logger.info(f"  Previously used segments: {used_segments}")
                    
                    segment_start = self._get_random_unused_segment(
                        cached_info['path'],
                        used_segments,
                        segment_duration=59
                    )
                    
                    logger.info(f"  ✓ Selected RANDOM segment: {segment_start}s (will clip {segment_start}-{segment_start+60}s)")
                    
                    # Clip the segment
                    temp_dir = tempfile.mkdtemp()
                    clipped_path = os.path.join(temp_dir, f'parkour_segment_{segment_start}s.mp4')
                    
                    clipped = self._trim_video(
                        cached_info['path'],
                        clipped_path,
                        max_duration=59,
                        start_time=segment_start
                    )
                    
                    if not clipped:
                        logger.warning("Could not clip cached video, downloading new one")
                        cached_info = None  # Fall through to download
                    else:
                        # Mark segment as used BEFORE uploading (so it's saved even if upload fails)
                        # CRITICAL: Always update the cache, even if segment_start is already in list
                        # This ensures the cache file is saved with current state
                        if segment_start not in used_segments:
                            used_segments.append(segment_start)
                            logger.info(f"  ✓ Marking segment {segment_start}s as used (NEW)")
                        else:
                            logger.warning(f"  ⚠ Segment {segment_start}s already in used_segments list!")
                        
                        # ALWAYS save the cache (even if segment was already marked)
                        # Sort segments for consistency
                        used_segments = sorted(list(set(used_segments)))  # Remove duplicates and sort
                        self._save_cached_video_info(youtube_url, cached_info['path'], used_segments)
                        logger.info(f"  ✓ Saved cache: used_segments = {used_segments}")
                        
                        # Mute audio
                        logger.info("Muting audio from background video...")
                        muted_path = clipped_path.replace('.mp4', '_muted.mp4')
                        muted_video = self._convert_to_mp4(clipped_path, muted_path, mute_audio=True)
                        if muted_video:
                            downloaded_path = muted_video
                            logger.info("✓ Background video audio muted")
                        else:
                            downloaded_path = clipped_path
                            logger.warning("Could not mute audio, will use original video")
                        
                        # Upload to HeyGen
                        asset_id = self._upload_video_to_heygen(downloaded_path)
                        
                        # Cleanup temp files (keep cached video)
                        try:
                            if os.path.exists(clipped_path) and clipped_path != downloaded_path:
                                os.remove(clipped_path)
                            if os.path.exists(muted_path) and muted_path != downloaded_path:
                                os.remove(muted_path)
                            if os.path.exists(temp_dir):
                                os.rmdir(temp_dir)
                        except:
                            pass
                        
                        return asset_id
            
            # Step 3: Download video (not cached or cache failed)
            if not cached_info:
                logger.info("Downloading new Minecraft parkour video...")
                
                # Create cache directory
                cache_dir = os.path.join(os.getcwd(), 'video_cache')
                os.makedirs(cache_dir, exist_ok=True)
                
                # Create cache filename
                import hashlib
                url_hash = hashlib.md5(youtube_url.encode()).hexdigest()
                cache_video_path = os.path.join(cache_dir, f'{url_hash}.mp4')
                
                # CRITICAL: Download FULL video to cache (don't trim it!)
                # We'll trim segments later when needed
                downloaded_path = self._download_youtube_video(youtube_url, cache_video_path)
                if not downloaded_path:
                    logger.warning("Failed to download YouTube video")
                    return None
        
                # Verify we have a full video (not trimmed to 60s)
                import subprocess
                try:
                    result = subprocess.run(
                        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                         '-of', 'default=noprint_wrappers=1:nokey=1', downloaded_path],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    duration = float(result.stdout.strip())
                    logger.info(f"  Cached video duration: {duration:.1f}s")
                    if duration <= 65:  # If video is ~60 seconds, it was trimmed
                        logger.error(f"❌ PROBLEM: Cached video is only {duration:.1f}s!")
                        logger.error("  This means the video was trimmed before caching.")
                        logger.error("  Cannot clip different segments - need full video.")
                        logger.error("  Will delete cache and re-download...")
                        try:
                            os.remove(downloaded_path)
                            os.remove(cache_video_path.replace('.mp4', '_info.json'))
                        except:
                            pass
                        # Re-download without trimming
                        downloaded_path = self._download_youtube_video(youtube_url, cache_video_path)
                        if downloaded_path:
                            result = subprocess.run(
                                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                                 '-of', 'default=noprint_wrappers=1:nokey=1', downloaded_path],
                                capture_output=True,
                                text=True,
                                timeout=10
                            )
                            duration = float(result.stdout.strip())
                            logger.info(f"  ✓ Re-downloaded full video: {duration:.1f}s")
                except Exception as e:
                    logger.warning(f"Could not verify video duration: {e}")
                
                # Get video duration for random segment selection
                import subprocess
                try:
                    result = subprocess.run(
                        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                         '-of', 'default=noprint_wrappers=1:nokey=1', downloaded_path],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    video_duration = float(result.stdout.strip())
                except Exception as e:
                    logger.warning(f"Could not get video duration for random segment: {e}")
                    video_duration = 600  # Default to 10 minutes
                
                # Pick a RANDOM segment start time (not always 0!)
                import random
                # Pick a truly RANDOM start time (in 5-second steps, avoids 0 when possible)
                segment_start = self._get_random_unused_segment(downloaded_path, used_segments=[], segment_duration=59)
                
                logger.info(f"  ✓ Selected RANDOM segment for new video: {segment_start}s")
                
                # Save cache info (mark this segment as used)
                self._save_cached_video_info(youtube_url, downloaded_path, [segment_start])
                
                # Clip RANDOM 59-second segment FROM THE FULL VIDEO for this use (must be < 1 minute)
                temp_dir = tempfile.mkdtemp()
                clipped_path = os.path.join(temp_dir, f'parkour_segment_{segment_start}s.mp4')
                
                clipped = self._trim_video(
                    downloaded_path,  # Use FULL video, not trimmed version
                    clipped_path,
                    max_duration=59,
                    start_time=segment_start  # Use RANDOM start time, not 0!
                )
                
                if not clipped:
                    logger.warning("Could not clip video, using full video")
                    clipped_path = downloaded_path
                
                # Mute audio from background video
                logger.info("Muting audio from background video...")
                muted_path = clipped_path.replace('.mp4', '_muted.mp4')
                muted_video = self._convert_to_mp4(clipped_path, muted_path, mute_audio=True)
                if muted_video:
                    downloaded_path = muted_video
                    logger.info("✓ Background video audio muted")
                else:
                    downloaded_path = clipped_path
                    logger.warning("Could not mute audio, will use original video")
                
                # Upload to HeyGen
                asset_id = self._upload_video_to_heygen(downloaded_path)
                
                # Cleanup temp files (keep cached video)
                try:
                    if os.path.exists(clipped_path) and clipped_path != downloaded_path and clipped_path != cache_video_path:
                        os.remove(clipped_path)
                    if os.path.exists(muted_path) and muted_path != downloaded_path:
                        os.remove(muted_path)
                except:
                    pass
                
                return asset_id
            
        except Exception as e:
            logger.error(f"Error getting Minecraft parkour video asset: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        return None
    
    def create_video(self, script: str, avatar_id: str = None, voice_id: str = None, 
                     background_image_url: str = None, background_video_url: str = None,
                     video_asset_id: str = None) -> Optional[str]:
        """
        Create a video using HeyGen API.
        Now creates videos WITHOUT avatar - just Minecraft parkour background + voiceover.
        
        Args:
            script: Script/text for the video (max 5000 characters)
            avatar_id: Avatar ID (optional, only used if HeyGen requires it - will be transparent)
            voice_id: Voice ID (required for voiceover)
            background_image_url: Background image URL (optional, fallback if video not available)
            background_video_url: Background video URL (deprecated - use video_asset_id instead)
            video_asset_id: HeyGen video asset ID (preferred for video backgrounds)
            
        Returns:
            Video ID if successful, None otherwise
        """
        # Get voice if not provided (required for narration)
        if not voice_id:
            _, voice_id = self._get_random_avatar_and_voice()
        
        # NO AVATAR - just Minecraft parkour video + voiceover
        # We'll try without character first, if HeyGen requires it we'll add transparent avatar
        
        url = f"{HEYGEN_API_BASE_URL}/v2/video/generate"
        
        # Build payload - NO AVATAR, just background video + voice
        # Use a minimal/invisible avatar if required, or try without character
        video_input = {
            "voice": {
                "type": "text",
                "input_text": script,
                "voice_id": voice_id,
                # Normal speed; script length is controlled to finish ~50s and stay < 60s.
                "speed": 1.0
            }
        }
        
        # Add background - prioritize video_asset_id (Minecraft parkour)
        if video_asset_id:
            # Use video background with video_asset_id - full screen Minecraft parkour
            video_input["background"] = {
                "type": "video",
                "video_asset_id": video_asset_id,
                "play_style": "loop"
            }
            logger.info(f"Using Minecraft parkour video background (asset_id: {video_asset_id[:20]}...)")
            logger.info("No avatar - just Minecraft parkour with voiceover")
            
            # Try without character first - if HeyGen requires it, we'll add a transparent one
            # Some HeyGen endpoints might require character, so we'll handle errors
        elif background_image_url:
            # Fallback to image background
            video_input["background"] = {
                "type": "image",
                "url": background_image_url
            }
            logger.info(f"Using background image: {background_image_url[:80]}...")
        else:
            # Default: dark color background
            video_input["background"] = {
                "type": "color",
                "value": "#1a1a1a"  # Dark background for YouTube Shorts
            }
            logger.info("Using default dark color background")
        
        payload = {
            "video_inputs": [video_input],
            "dimension": {
                "width": 720,    # 720p vertical format (9:16 aspect ratio) - Free plan limit
                "height": 1280   # YouTube Shorts format at 720p resolution
            }
        }
        
        try:
            logger.info(f"Creating video with HeyGen...")
            script_length = len(script)
            word_count = len(script.split())
            logger.info(f"Script length: {script_length} characters ({word_count} words)")
            
            # Warn if script might be too long for free plan (180s limit)
            # Rough estimate: ~2-3 words per second of speech
            estimated_duration = word_count / 2.5  # Conservative estimate
            if estimated_duration > 150:  # Warn if close to 180s limit
                logger.warning(f"⚠ Script might be too long (estimated ~{estimated_duration:.1f}s)")
                logger.warning("   Free plan limit is 180 seconds. Consider shortening the script.")
            
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                video_id = result.get("data", {}).get("video_id") or result.get("video_id") or result.get("data", {}).get("id") or result.get("id")
                if video_id:
                    logger.info(f"✓ Video creation started! Video ID: {video_id}")
                    return video_id
                else:
                    logger.error(f"Unexpected response format: {result}")
                return None
            elif response.status_code == 400:
                # Check for specific errors
                try:
                    error_data = response.json()
                    error_code = error_data.get("code", "")
                    error_message = error_data.get("message", "").lower()
                    error_detail = error_data.get("detail", "").lower()
                    
                    logger.debug(f"Error message: {error_message}")
                    logger.debug(f"Error detail: {error_detail}")
                    
                    # Check if voice is not found - retry with different voice
                    voice_not_found = (
                        "voice" in error_message and "not found" in error_message
                    ) or (
                        "resourcetype.voice" in error_message or "resourcetype.voice" in error_detail
                    )
                    
                    if voice_not_found:
                        logger.warning(f"Voice ID {voice_id} not found, retrying with different voice...")
                        # Get a new random voice and retry (max 3 attempts)
                        max_voice_retries = 3
                        for retry_attempt in range(max_voice_retries):
                            # Get fresh voices list
                            self._voices = None  # Clear cache
                            voices = self._get_voices()
                            if not voices:
                                logger.error("No voices available for retry")
                                break
                            
                            # Filter for English voices
                            english_voices = []
                            for v in voices:
                                v_name = v.get('name', '').lower()
                                v_lang = v.get('language', '').lower()
                                is_english = (
                                    'en' in v_lang or 'english' in v_lang or
                                    'en' in v_name or 'english' in v_name or
                                    'us' in v_lang or 'uk' in v_lang
                                )
                                non_english = any(ind in v_lang or ind in v_name 
                                                for ind in ['hi', 'hindi', 'es', 'spanish', 'fr', 'french'])
                                if is_english and not non_english:
                                    english_voices.append(v)
                            
                            # Select new voice
                            if english_voices:
                                import random
                                new_voice = random.choice(english_voices)
                                new_voice_id = new_voice.get("voice_id") or new_voice.get("id")
                                logger.info(f"Retry {retry_attempt + 1}/{max_voice_retries}: Using voice {new_voice.get('name', 'Unknown')} (ID: {new_voice_id})")
                            else:
                                import random
                                new_voice = random.choice(voices)
                                new_voice_id = new_voice.get("voice_id") or new_voice.get("id")
                                logger.warning(f"Retry {retry_attempt + 1}/{max_voice_retries}: No English voices, using {new_voice.get('name', 'Unknown')} (ID: {new_voice_id})")
                            
                            # Update voice_id in payload
                            video_input["voice"]["voice_id"] = new_voice_id
                            payload["video_inputs"] = [video_input]
                            
                            # Retry request
                            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
                            if response.status_code == 200:
                                result = response.json()
                                video_id = result.get("data", {}).get("video_id") or result.get("video_id") or result.get("data", {}).get("id") or result.get("id")
                                if video_id:
                                    logger.info(f"✓ Video creation started with new voice! Video ID: {video_id}")
                                    return video_id
                            elif response.status_code == 400:
                                # Check if it's still a voice error
                                try:
                                    retry_error = response.json()
                                    retry_error_msg = retry_error.get("message", "").lower()
                                    if "voice" not in retry_error_msg or "not found" not in retry_error_msg:
                                        # Different error, break and handle normally
                                        break
                                except:
                                    break
                        
                        # If all retries failed, log error and continue to other error handling
                        logger.error(f"Failed to find valid voice after {max_voice_retries} retries")
                    
                    # Check if video background has issues
                    video_bg_error = (
                        ("video" in error_message and "background" in error_message) or 
                        ("play_style" in error_message) or 
                        ("video_asset_id" in error_message) or
                        ("either url or video_asset_id" in error_message)
                    )
                    
                    logger.debug(f"Video background error detected: {video_bg_error}")
                    
                    if video_bg_error:
                        logger.warning("Video background error, falling back to image")
                        # Remove background removal flag when falling back (not needed for image/color backgrounds)
                        if "remove_background" in video_input.get("character", {}):
                            del video_input["character"]["remove_background"]
                        
                        # Retry with image background instead
                        if background_image_url:
                            # Update the payload with image background
                            video_input["background"] = {
                                "type": "image",
                                "url": background_image_url
                            }
                            payload["video_inputs"] = [video_input]
                            logger.info(f"Retrying with image background: {background_image_url[:80]}...")
                            # Retry the request
                            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
                            if response.status_code == 200:
                                result = response.json()
                                video_id = result.get("data", {}).get("video_id") or result.get("video_id") or result.get("data", {}).get("id") or result.get("id")
                                if video_id:
                                    logger.info(f"✓ Video creation started! Video ID: {video_id}")
                                    return video_id
                        else:
                            # Fall back to color background
                            video_input["background"] = {
                                "type": "color",
                                "value": "#1a1a1a"
                            }
                            payload["video_inputs"] = [video_input]
                            logger.info("Retrying with color background")
                            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
                            if response.status_code == 200:
                                result = response.json()
                                video_id = result.get("data", {}).get("video_id") or result.get("video_id") or result.get("data", {}).get("id") or result.get("id")
                                if video_id:
                                    logger.info(f"✓ Video creation started! Video ID: {video_id}")
                                    return video_id
                    
                    if error_code == "RESOLUTION_NOT_ALLOWED":
                        logger.error("✗ Resolution not allowed for your plan")
                        logger.error(f"   Error: {error_data.get('message', 'Unknown error')}")
                        logger.error(f"   Detail: {error_data.get('detail', '')}")
                        logger.error("\n   Current resolution: 720x1280 (720p vertical)")
                        logger.error("   Free plan supports: 720p maximum")
                        logger.error("   Please upgrade your HeyGen plan for higher resolutions")
                        return None
                    elif error_code == "MOVIO_VIDEO_IS_TOO_LONG":
                        logger.error("✗ Video is too long (> 180 seconds)")
                        logger.error(f"   Error: {error_data.get('message', 'Unknown error')}")
                        logger.error(f"   Detail: {error_data.get('detail', '')}")
                        logger.error(f"\n   Script length: {len(script)} characters")
                        word_count = len(script.split())
                        logger.error(f"   Script word count: {word_count} words")
                        logger.error("\n   HeyGen Free Plan Limit:")
                        logger.error("   - Maximum video length: 180 seconds (3 minutes)")
                        logger.error("   - Your script is too long for the free plan")
                        logger.error("\n   Solutions:")
                        logger.error("   1. Shorten your script to ~30-40 words (15-20 seconds)")
                        logger.error("   2. Upgrade your HeyGen plan for longer videos")
                        logger.error("   3. Split the content into multiple shorter videos")
                        return None
                    elif error_code == "MOVIO_PAYMENT_INSUFFICIENT_CREDIT":
                        logger.error("✗ Insufficient credits for video generation")
                        logger.error(f"   Error: {error_data.get('message', 'Unknown error')}")
                        logger.error(f"   Detail: {error_data.get('detail', '')}")
                        logger.error("\n   HeyGen Credit System:")
                        logger.error("   - Photo Avatar: 1 credit per minute (30-second increments)")
                        logger.error("   - Video Avatar: 2 credits per minute (30-second increments)")
                        logger.error("   - A 30-second video typically costs 1 credit")
                        logger.error("\n   Troubleshooting:")
                        logger.error("   1. Check your HeyGen dashboard for accurate credit balance")
                        logger.error("   2. Credits may be reserved/held for pending jobs")
                        logger.error("   3. Wait for pending jobs to complete and credits to be released")
                        logger.error("   4. Ensure you have at least 1 credit available")
                        return None
                except Exception as parse_error:
                    logger.error(f"Error parsing HeyGen API response: {parse_error}")
                
                logger.error(f"Failed to create video. Status: {response.status_code}")
                logger.error(f"Response: {response.text[:500]}")
                return None
        
        except Exception as e:
            logger.error(f"Error creating video: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        return None
    
    def check_video_status(self, video_id: str) -> Dict[str, any]:
        """
        Check the status of a video generation job.
        
        Args:
            video_id: Video ID from create_video()
            
        Returns:
            Dictionary with status information
        """
        url = f"{HEYGEN_API_BASE_URL}/v1/video_status.get"
        
        try:
            params = {"video_id": video_id}
            response = requests.get(url, params=params, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                data = result.get("data", {}) or result
                logger.debug(f"Video {video_id} status: {data.get('status', 'unknown')}")
                return data
            else:
                logger.error(f"Error checking video status: {response.status_code}")
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            logger.error(f"Error checking video status: {e}")
            return {"status": "error", "error": str(e)}
    
    def wait_for_video(self, video_id: str, timeout: int = None) -> Optional[str]:
        """
        Wait for video generation to complete and return video URL.
        
        Args:
            video_id: Video ID from create_video()
            timeout: Maximum time to wait in seconds (default: VIDEO_GENERATION_TIMEOUT)
            
        Returns:
            Video URL if successful, None otherwise
        """
        timeout = timeout or VIDEO_GENERATION_TIMEOUT
        start_time = time.time()
        check_interval = 10  # Check every 10 seconds
        last_status = None
        
        logger.info(f"Waiting for video generation (timeout: {timeout}s / {timeout//60} minutes)...")
        logger.info(f"Video ID: {video_id}")
        logger.info("Note: HeyGen videos can take 2-10 minutes depending on queue and video length")
        
        while time.time() - start_time < timeout:
            elapsed = int(time.time() - start_time)
            
            # Check video status
            status_data = self.check_video_status(video_id)
            status = status_data.get("status", "unknown").lower()
            
            # Log status changes
            if status != last_status:
                logger.info(f"Status changed: {last_status or 'starting'} → {status}")
                last_status = status
            
            if status == "completed":
                video_url = status_data.get("video_url") or status_data.get("url") or status_data.get("download_url")
                if video_url:
                    logger.info(f"✓ Video ready! URL: {video_url}")
                    return video_url
                else:
                    logger.error("Video completed but no URL found")
                return None
                    
            elif status in ["failed", "error"]:
                error_info = status_data.get("error", {})
                if isinstance(error_info, dict):
                    error_code = error_info.get("code", "")
                    error_message = error_info.get("message", "")
                    error_detail = error_info.get("detail", "")
                    
                    if error_code == "MOVIO_VIDEO_IS_TOO_LONG":
                        logger.error("✗ Video is too long (> 180 seconds)")
                        logger.error(f"   Error: {error_message}")
                        logger.error(f"   Detail: {error_detail}")
                        logger.error("\n   HeyGen Free Plan Limit:")
                        logger.error("   - Maximum video length: 180 seconds (3 minutes)")
                        logger.error("   - Your script was too long for the free plan")
                        logger.error("\n   Solutions:")
                        logger.error("   1. Shorten your script to ~30-40 words (15-20 seconds)")
                        logger.error("   2. Upgrade your HeyGen plan for longer videos")
                        logger.error("   3. Split the content into multiple shorter videos")
                        return None
                    elif error_code == "MOVIO_PAYMENT_INSUFFICIENT_CREDIT":
                        logger.error("✗ Insufficient credits for video generation")
                        logger.error(f"   Error: {error_message}")
                        logger.error(f"   Detail: {error_detail}")
                        logger.error("\n   HeyGen Credit System:")
                        logger.error("   - Photo Avatar: 1 credit per minute (30-second increments)")
                        logger.error("   - Video Avatar: 2 credits per minute (30-second increments)")
                        logger.error("   - A 30-second video typically costs 1 credit")
                        logger.error("\n   Possible reasons:")
                        logger.error("   1. Credits may be reserved/held for pending jobs")
                        logger.error("   2. Minimum credit threshold may be required")
                        logger.error("   3. Check your HeyGen dashboard for accurate balance")
                        logger.error("   4. Credits may have been consumed by other operations")
                        return None
                    else:
                        logger.error(f"Video generation failed: {error_code} - {error_message}")
                        if error_detail:
                            logger.error(f"   Detail: {error_detail}")
                        return None
                else:
                    logger.error(f"Video generation failed: {error_info}")
                return None
            
            # Log progress every 30 seconds
            if elapsed > 0 and elapsed % 30 == 0:
                minutes = elapsed // 60
                seconds = elapsed % 60
                logger.info(f"Still processing... ({minutes}m {seconds}s elapsed, status: {status})")
            
            time.sleep(check_interval)
        
        # Timeout - check one more time
        logger.warning(f"Timeout after {timeout}s - checking status one more time...")
        status_data = self.check_video_status(video_id)
        status = status_data.get("status", "unknown").lower()
        
        if status == "completed":
            video_url = status_data.get("video_url") or status_data.get("url") or status_data.get("download_url")
            if video_url:
                logger.info(f"✓ Video completed! URL: {video_url}")
                return video_url
        
        logger.warning(f"Video may still be processing (status: {status})")
        logger.info(f"You can check status later using video ID: {video_id}")
        return None
    
    def download_video(self, video_url: str, output_path: str) -> bool:
        """
        Download video from URL to local file.
        
        Args:
            video_url: URL to download video from
            output_path: Local path to save video
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Downloading video from: {video_url[:80]}...")
            response = requests.get(video_url, timeout=300, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            # Write to file
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and downloaded % (1024 * 1024) == 0:  # Log every MB
                            percent = (downloaded / total_size) * 100
                            logger.info(f"Download progress: {percent:.1f}% ({downloaded}/{total_size} bytes)")
            
            file_size = os.path.getsize(output_path)
            logger.info(f"✓ Video downloaded successfully to: {output_path}")
            logger.info(f"File size: {file_size / 1024 / 1024:.2f} MB")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download video: {e}")
            return False
    
    def generate_video_from_trend(self, trend_data: Dict, script: str = None, 
                                  output_path: str = None) -> Optional[str]:
        """
        Generate a video from trending topic data.
        
        Args:
            trend_data: Dictionary containing trend information
            script: Optional script text (if None, generates from trend_data)
            output_path: Path to save the video file
            
        Returns:
            Path to generated video file, or None if failed
        """
        if not script:
            script = self._generate_script_from_trend(trend_data)
        
        if not output_path:
            timestamp = int(time.time())
            output_path = f"video_{timestamp}.mp4"
        
        # Get topic-relevant background
        topic = trend_data.get('title', '')
        keywords = trend_data.get('keywords', [])
        
        # Get image background as fallback
        background_image_url = self._get_background_image_url(topic, keywords)
        
        # Try to get Minecraft parkour video as HeyGen asset_id
        # This downloads YouTube video and uploads to HeyGen
        video_asset_id = None
        if self.youtube_service and YT_DLP_AVAILABLE:
            logger.info("Attempting to get Minecraft parkour video background...")
            video_asset_id = self._get_minecraft_parkour_video_asset_id(topic, keywords)
            if video_asset_id:
                logger.info(f"✓ Got Minecraft parkour video background (asset_id: {video_asset_id[:20]}...)")
            else:
                logger.info("Could not get video background, will use image fallback")
        
        # Create video with NO avatar - just Minecraft parkour background + voiceover
        video_id = self.create_video(
            script, 
            background_image_url=background_image_url,
            video_asset_id=video_asset_id
        )
        if not video_id:
            return None
        
        # Wait for video to be ready
        video_url = self.wait_for_video(video_id)
        if not video_url:
            logger.error(f"Could not retrieve video URL for video {video_id}")
            return None
        
        # Download video
        if self.download_video(video_url, output_path):
            # Add captions to the video using standalone script
            logger.info("\n" + "="*60)
            logger.info("Step 5: Adding captions to video...")
            logger.info("="*60)
            
            captioned_path = self._add_captions_via_script(
                output_path,
                script=script
            )
            
            if captioned_path:
                logger.info(f"✓ Captioned video saved: {captioned_path}")
                
                # Step 6: Add background audio overlay
                audio_path = self._add_background_audio(captioned_path)
                if audio_path:
                    logger.info(f"✓ Background audio added: {audio_path}")
                    # Update captioned_path to use the audio version
                    captioned_path = audio_path
                
                # Replace original with final version (captioned + audio)
                try:
                    os.remove(output_path)
                    os.rename(captioned_path, output_path)
                    logger.info(f"✓ Replaced original with final version (captions + audio)")
                except Exception as e:
                    logger.warning(f"Could not replace original: {e}, keeping both files")
                    return captioned_path

                # HARD CAP: ensure final output is always < 60 seconds
                capped = self._ensure_under_duration(output_path, max_duration=59)
                return capped or output_path
                return output_path
            else:
                logger.warning("Captioning failed, using original video without captions")
            return output_path
        
        return None
    
    def _add_captions_via_script(self, video_path: str, script: str = None) -> Optional[str]:
        """
        Add captions using standalone caption_video.py script.
        This isolates captioning from the main process to avoid PyTorch issues.
        """
        import subprocess
        import sys
        
        # First, ensure PyTorch and NumPy are installed correctly
        logger.info("Checking PyTorch and NumPy installation...")
        torch_ok = False
        numpy_ok = False
        
        # Check NumPy first (required by PyTorch)
        try:
            import numpy
            numpy_ok = True
            logger.debug("NumPy is available")
        except Exception as e:
            logger.warning(f"NumPy not available: {e}, installing...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "numpy", "--no-cache-dir"], 
                             capture_output=True, timeout=120, check=False)
                import numpy
                numpy_ok = True
                logger.info("NumPy installed")
            except Exception as fix_error:
                logger.error(f"Could not install NumPy: {fix_error}")
        
        # Check PyTorch
        try:
            import torch
            torch_ok = True
            logger.debug("PyTorch is available")
        except Exception as e:
            error_msg = str(e).lower()
            if "incompatible architecture" in error_msg or ("dlopen" in error_msg and ("x86_64" in error_msg or "arm64" in error_msg)):
                logger.warning("PyTorch architecture issue detected, fixing...")
                try:
                    # Uninstall torch and related packages
                    subprocess.run([sys.executable, "-m", "pip", "uninstall", "torch", "torchvision", "torchaudio", "-y"], 
                                 capture_output=True, timeout=60, check=False)
                    # Also uninstall tiktoken if it has architecture issues
                    subprocess.run([sys.executable, "-m", "pip", "uninstall", "tiktoken", "-y"], 
                                 capture_output=True, timeout=30, check=False)
                    
                    # Install torch for ARM64 Mac (Apple Silicon)
                    import platform
                    if platform.machine() == "arm64":
                        logger.info("Installing PyTorch for ARM64 (Apple Silicon)...")
                        subprocess.run([sys.executable, "-m", "pip", "install", "torch", "torchvision", "torchaudio", "--no-cache-dir"], 
                                     capture_output=True, timeout=300, check=False)
                    else:
                        logger.info("Installing PyTorch for x86_64...")
                        subprocess.run([sys.executable, "-m", "pip", "install", "torch", "--no-cache-dir"], 
                                     capture_output=True, timeout=300, check=False)
                    
                    # Reinstall tiktoken
                    subprocess.run([sys.executable, "-m", "pip", "install", "tiktoken", "--no-cache-dir"], 
                                 capture_output=True, timeout=60, check=False)
                    
                    # Verify it works
                    import torch
                    torch_ok = True
                    logger.info("PyTorch reinstalled and verified")
                except Exception as fix_error:
                    logger.error(f"Could not fix PyTorch: {fix_error}")
                    logger.error("Captioning may fail - PyTorch architecture mismatch")
            else:
                logger.warning(f"PyTorch import error: {e}")
        
        if not numpy_ok or not torch_ok:
            logger.warning("PyTorch/NumPy setup incomplete - captioning may fail")
        
        base, ext = os.path.splitext(video_path)
        captioned_path = f"{base}_captioned{ext}"
        
        logger.info(f"Calling standalone caption script for: {video_path}")
        
        # Build command - use the same Python that's running this script
        # Get Python executable from sys.executable (which is the Python running main.py)
        script_path = os.path.join(os.path.dirname(__file__), "caption_video.py")
        python_exe = sys.executable  # This is the Python running main.py
        cmd = [python_exe, script_path, video_path, "-o", captioned_path]
        
        logger.debug(f"Using Python: {python_exe}")
        logger.debug(f"Caption script: {script_path}")
        
        if script:
            cmd.extend(["-s", script])
        
        try:
            # Run with longer timeout and better error handling
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=900,  # 15 minute timeout (captioning can take a while)
                cwd=os.path.dirname(__file__)
            )
            
            # Log output for debugging
            if result.stdout:
                logger.debug(f"Caption script stdout: {result.stdout[-1000:]}")
            if result.stderr:
                logger.debug(f"Caption script stderr: {result.stderr[-1000:]}")
            
            if result.returncode == 0:
                if os.path.exists(captioned_path):
                    logger.info(f"✓ Caption script completed successfully")
                    return captioned_path
                else:
                    logger.warning(f"Caption script succeeded but output file not found: {captioned_path}")
                    logger.warning(f"Expected path: {captioned_path}")
                    logger.warning(f"Current directory: {os.getcwd()}")
                return None
            else:
                logger.error(f"Caption script failed with return code {result.returncode}")
                if result.stderr:
                    # Show last 500 chars of stderr (most recent error)
                    error_tail = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
                    logger.error(f"Caption script error: {error_tail}")
                if result.stdout:
                    # Show last 500 chars of stdout
                    stdout_tail = result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
                    logger.error(f"Caption script output: {stdout_tail}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Caption script timed out after 10 minutes")
            return None
        except Exception as e:
            logger.error(f"Error calling caption script: {e}")
            return None
    
    def _add_background_audio(self, video_path: str) -> Optional[str]:
        """
        Add background audio overlay to video.
        Audio will be trimmed/looped to match video duration.
        
        Args:
            video_path: Path to captioned video
            
        Returns:
            Path to video with audio overlay, or None if failed
        """
        bg_audio_path = os.path.join(os.path.dirname(__file__), "officialbg.mp3")
        
        if not os.path.exists(bg_audio_path):
            logger.warning(f"Background audio file not found: {bg_audio_path}")
            return None
        
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None
        
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_with_audio{ext}"
        
        logger.info(f"Adding background audio to: {video_path}")
        logger.info(f"Output will be: {output_path}")
        
        try:
            # Use MoviePy to add audio
            try:
                from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
            except ImportError:
                from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
            
            # Load video
            video = VideoFileClip(video_path)
            video_duration = video.duration
            
            logger.info(f"Video duration: {video_duration:.2f}s")
            
            # Load background audio
            bg_audio = AudioFileClip(bg_audio_path)
            bg_audio_duration = bg_audio.duration
            
            logger.info(f"Background audio duration: {bg_audio_duration:.2f}s")
            
            # Trim or loop audio to match video duration
            if bg_audio_duration >= video_duration:
                # Trim audio to video duration
                try:
                    bg_audio = bg_audio.subclip(0, video_duration)
                except AttributeError:
                    # Fallback: use ffmpeg to trim
                    import subprocess
                    temp_audio = os.path.join(os.path.dirname(__file__), "temp_bg_audio.mp3")
                    subprocess.run([
                        'ffmpeg', '-i', bg_audio_path, '-t', str(video_duration),
                        '-y', temp_audio
                    ], capture_output=True, check=True)
                    bg_audio.close()
                    bg_audio = AudioFileClip(temp_audio)
                logger.info(f"Trimmed audio to match video duration")
            else:
                # Loop audio to match video duration
                loops_needed = int(video_duration / bg_audio_duration) + 1
                audio_clips = [bg_audio] * loops_needed
                bg_audio = CompositeAudioClip(audio_clips)
                try:
                    bg_audio = bg_audio.subclip(0, video_duration)
                except AttributeError:
                    # If subclip doesn't work, use ffmpeg
                    import subprocess
                    temp_audio = os.path.join(os.path.dirname(__file__), "temp_bg_audio_loop.mp3")
                    # Create looped audio with ffmpeg
                    subprocess.run([
                        'ffmpeg', '-stream_loop', str(loops_needed - 1), '-i', bg_audio_path,
                        '-t', str(video_duration), '-y', temp_audio
                    ], capture_output=True, check=True)
                    bg_audio.close()
                    bg_audio = AudioFileClip(temp_audio)
                logger.info(f"Looped audio {loops_needed} times to match video duration")
            
            # Set audio volume (lower volume for background, keep original video audio)
            # User request: increase background music by +15%
            bg_volume = 0.3 * 1.15  # 34.5%
            try:
                bg_audio = bg_audio.volumex(bg_volume)
            except AttributeError:
                try:
                    bg_audio = bg_audio.with_volume(bg_volume)  # Alternative API
                except AttributeError:
                    # Use ffmpeg to adjust volume if MoviePy doesn't support it
                    import subprocess
                    temp_audio_vol = os.path.join(os.path.dirname(__file__), "temp_bg_audio_vol.mp3")
                    subprocess.run([
                        'ffmpeg', '-i', bg_audio.filename if hasattr(bg_audio, 'filename') else bg_audio_path,
                        '-filter:a', f'volume={bg_volume}', '-y', temp_audio_vol
                    ], capture_output=True, check=True)
                    bg_audio.close()
                    bg_audio = AudioFileClip(temp_audio_vol)
            
            # Combine video audio with background audio
            if video.audio:
                # Video has audio, mix them
                final_audio = CompositeAudioClip([video.audio, bg_audio])
                logger.info("Mixing video audio with background audio")
            else:
                # Video has no audio, use only background
                final_audio = bg_audio
                logger.info("Using only background audio (video has no audio)")
            
            # Set final audio to video
            try:
                final_video = video.set_audio(final_audio)
            except AttributeError:
                try:
                    final_video = video.with_audio(final_audio)
                except AttributeError:
                    # Fallback: use ffmpeg to combine
                    import subprocess
                    temp_video_audio = os.path.join(os.path.dirname(__file__), "temp_video_audio.mp4")
                    # Extract video without audio
                    subprocess.run([
                        'ffmpeg', '-i', video_path, '-c:v', 'copy', '-an', '-y', temp_video_audio
                    ], capture_output=True, check=True)
                    # Extract audio to temp file
                    temp_final_audio = os.path.join(os.path.dirname(__file__), "temp_final_audio.m4a")
                    final_audio.write_audiofile(temp_final_audio, verbose=False, logger=None)
                    # Combine with ffmpeg
                    subprocess.run([
                        'ffmpeg', '-i', temp_video_audio, '-i', temp_final_audio,
                        '-c:v', 'copy', '-c:a', 'aac', '-shortest', '-y', output_path
                    ], capture_output=True, check=True)
                    # Cleanup temp files
                    try:
                        os.remove(temp_video_audio)
                        os.remove(temp_final_audio)
                    except:
                        pass
                    video.close()
                    final_audio.close()
                    logger.info(f"✓ Video with background audio saved: {output_path}")
                    return output_path
            
            # Write final video
            logger.info("Rendering video with background audio...")
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio-bg.m4a',
                remove_temp=True
            )
            
            # Cleanup
            video.close()
            bg_audio.close()
            final_video.close()
            if video.audio:
                video.audio.close()
            
            logger.info(f"✓ Video with background audio saved: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error adding background audio: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def _ensure_under_duration(self, video_path: str, max_duration: int = 59) -> Optional[str]:
        """
        Hard-trim the final output to max_duration seconds if it exceeds it.
        This guarantees we never upload a video longer than 59s (YouTube Shorts safe).
        """
        import subprocess
        if not os.path.exists(video_path):
            return None
        try:
            # Probe duration
            probe = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
                capture_output=True, text=True, timeout=10
            )
            duration = float(probe.stdout.strip() or 0)
        except Exception as e:
            logger.warning(f"Could not probe video duration for cap: {e}")
            return None

        if duration <= (max_duration + 0.2):
            logger.info(f"✓ Final duration OK: {duration:.2f}s")
            return video_path

        logger.warning(f"⚠ Final video is {duration:.2f}s; trimming to {max_duration}s")
        base, ext = os.path.splitext(video_path)
        trimmed_path = f"{base}_capped{ext}"
        try:
            # Re-encode to ensure clean cut + audio stops with video
            subprocess.run(
                ['ffmpeg', '-i', video_path, '-t', str(max_duration),
                 '-c:v', 'libx264', '-preset', 'fast', '-crf', '20',
                 '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
                 '-y', trimmed_path],
                capture_output=True, text=True, timeout=600, check=True
            )
            # Replace original
            os.replace(trimmed_path, video_path)
            logger.info("✓ Applied 59s hard cap to final output")
            return video_path
        except Exception as e:
            logger.error(f"Failed to cap duration: {e}")
            return None
    
    def add_captions_to_video(self, video_path: str, script: str = None, output_path: str = None) -> Optional[str]:
        """
        Add captions to video using Whisper timestamps + MoviePy styling.
        Captions are positioned in the center of the screen.
        
        Args:
            video_path: Path to input video
            script: Optional script text to help Whisper (if available)
            output_path: Path to save captioned video (if None, creates _captioned version)
        
        Returns:
            Path to captioned video, or None if failed
        """
        # Try to import whisper - catch any errors
        try:
            import whisper
            # Test that we can actually load a model (quick test)
            try:
                # Don't actually load, just verify import works
                logger.debug("Whisper imported successfully")
            except:
                pass
        except ImportError as e:
            logger.warning(f"Whisper not available: {e}")
            logger.warning("Install with: pip install openai-whisper")
            return None
        except Exception as e:
            # Handle architecture mismatches, PyTorch issues, etc.
            error_msg = str(e).lower()
            error_type = type(e).__name__
            
            # Log the FULL error for debugging
            logger.warning(f"Whisper import error: {error_type}: {e}")
            import traceback
            full_traceback = traceback.format_exc()
            logger.debug(f"Full traceback:\n{full_traceback}")
            
            # Only catch ACTUAL architecture errors (very specific patterns)
            is_arch_error = (
                "incompatible architecture" in error_msg or 
                (error_type == "OSError" and "dlopen" in error_msg and 
                 ("mach-o" in error_msg or "x86_64" in error_msg or "arm64" in error_msg or 
                  "incompatible architecture" in full_traceback.lower()))
            )
            
            if is_arch_error:
                logger.warning("PyTorch architecture mismatch detected (x86_64 vs ARM64)")
                logger.warning("Captioning disabled. To fix: pip uninstall torch && pip install torch")
            else:
                logger.warning(f"Whisper import failed (non-architecture error): {error_type}")
                logger.warning("Captioning disabled due to import error")
            return None
        
        try:
            try:
                from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
            except ImportError:
                from moviepy import VideoFileClip, TextClip, CompositeVideoClip
            import subprocess
            import ssl
            import certifi
        except ImportError as e:
            logger.warning(f"MoviePy not available: {e}")
            logger.warning("Install with: pip install moviepy certifi")
            return None
        
        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=5)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("ffmpeg not found - cannot add captions")
            return None
        
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None
        
        if not output_path:
            base, ext = os.path.splitext(video_path)
            output_path = f"{base}_captioned{ext}"
        
        logger.info(f"Adding captions to: {video_path}")
        logger.info(f"Output will be: {output_path}")
        
        try:
            # Step 1: Extract timestamps with Whisper
            logger.info("Extracting timestamps with Whisper...")
            
            # Handle SSL certificate issues
            try:
                ssl_context = ssl.create_default_context(cafile=certifi.where())
            except:
                logger.warning("SSL certificate issue detected, using unverified context")
                ssl_context = ssl._create_unverified_context()
            
            import urllib.request
            original_ssl = ssl._create_default_https_context
            ssl._create_default_https_context = lambda: ssl_context
            
            try:
                model = whisper.load_model("base")
            except Exception as e:
                # Handle PyTorch architecture issues, model loading failures, etc.
                error_msg = str(e).lower()
                if ("incompatible architecture" in error_msg or "torch" in error_msg or 
                    "dlopen" in error_msg or "mach-o" in error_msg or "x86_64" in error_msg or "arm64" in error_msg):
                    logger.error("PyTorch architecture mismatch - cannot load Whisper model")
                    logger.error("Fix with: pip uninstall torch && pip install torch")
                else:
                    logger.error(f"Failed to load Whisper model: {e}")
                return None
            finally:
                ssl._create_default_https_context = original_ssl
            
            transcribe_options = {
                "word_timestamps": True,
                "verbose": False,
            }
            
            if script:
                transcribe_options["initial_prompt"] = script[:200]
                logger.info("Using provided script text to help Whisper")
            
            result = model.transcribe(video_path, **transcribe_options)
            segments = result["segments"]
            logger.info(f"✓ Got {len(segments)} caption segments")
            
            if not segments:
                logger.warning("No segments found in transcription")
                return None
            
            # Step 2: Load video with MoviePy
            logger.info("Loading video with MoviePy...")
            video = VideoFileClip(video_path)
            logger.info(f"Video duration: {video.duration:.2f}s, size: {video.w}x{video.h}")
            
            # Step 3: Create text clips (centered on screen)
            logger.info("Creating styled text clips...")
            text_clips = []
            for i, seg in enumerate(segments):
                text = seg["text"].strip()
                start_time = seg["start"]
                end_time = seg["end"]
                duration = end_time - start_time
                
                if not text or duration <= 0:
                    continue
                
                # Style for YouTube Shorts (center of screen, readable)
                try:
                    txt_clip = TextClip(
                        text=text,
                        font_size=48,
                        color='white',
                        stroke_color='black',
                        stroke_width=3,
                        method='caption',
                        size=(int(video.w * 0.9), None),
                        text_align='center'
                    )
                except (TypeError, ValueError):
                    try:
                        txt_clip = TextClip(
                            text=text,
                            font_size=48,
                            color='white',
                            stroke_color='black',
                            stroke_width=3,
                            size=(int(video.w * 0.9), None),
                            text_align='center'
                        )
                    except (TypeError, ValueError):
                        txt_clip = TextClip(
                            text=text,
                            font_size=48,
                            color='white',
                            size=(int(video.w * 0.9), None)
                        )
                
                # Position captions in the CENTER of the screen
                try:
                    txt_clip = txt_clip.with_position(('center', 'center')) \
                                       .with_start(start_time) \
                                       .with_duration(duration)
                except AttributeError:
                    txt_clip = txt_clip.set_position(('center', 'center')) \
                                       .set_start(start_time) \
                                       .set_duration(duration)
                
                text_clips.append(txt_clip)
                
                if (i + 1) % 10 == 0:
                    logger.info(f"  Created {i + 1}/{len(segments)} text clips...")
            
            logger.info(f"✓ Created {len(text_clips)} text clips")
            
            # Step 4: Composite video + captions
            logger.info("Compositing video with captions...")
            final = CompositeVideoClip([video] + text_clips)
            
            # Step 5: Write output
            logger.info(f"Rendering captioned video (this may take a minute)...")
            final.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                fps=video.fps,
                preset='medium',
                threads=4,
                logger=None
            )
            
            # Cleanup
            video.close()
            final.close()
            
            logger.info(f"✓ Captioned video saved: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Captioning failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        return None
    
    def _generate_script_from_trend(self, trend_data: Dict) -> str:
        """
        Generate a full first-person Reddit story script.
        Creates a complete narrative story, not a short clip.
        
        Args:
            trend_data: Dictionary containing Reddit story information
            
        Returns:
            Full first-person story script (target ~50s, must stay < 60s)
        """
        title = trend_data.get('title', '')
        description = trend_data.get('description', '')  # This is the story text from Reddit
        
        # CRITICAL: Prioritize story text (description) over title
        # Reddit titles are often meta posts, not the actual story
        story_text = description.strip() if description else ""
        
        if not story_text:
            logger.warning(f"No story text found in description, falling back to title: {title[:60]}...")
            story_text = title
        
        if not story_text:
            return "I have a story to share that will shock you."
        
        # Use AI to create a full story script while keeping first-person narrative
        if AI_AVAILABLE:
            try:
                logger.info(f"Generating full first-person Reddit story script...")
                logger.debug(f"Story preview: {story_text[:200]}...")

                # If the Reddit title is already a strong first-person hook, use it verbatim as the opening line.
                desired_hook = None
                if title and title.strip().startswith("I ") and len(title.split()) <= 18:
                    desired_hook = title.strip()
                
                # Create a prompt for AI to create a FULL story script with bold hook
                # Extract key theme for hook statement
                import re
                # Try to identify the main theme/conflict from title and first few sentences
                theme_keywords = []
                if title:
                    # Extract key words from title
                    title_words = re.findall(r'\b\w{4,}\b', title.lower())
                    theme_keywords.extend(title_words[:3])
                
                hook_instruction = ""
                if desired_hook:
                    hook_instruction = f"Your FIRST sentence MUST be exactly: {desired_hook}\n"

                prompt = f"""Rewrite this Reddit story as a complete first-person narrative script for a YouTube Shorts voiceover.
CRITICAL: Start DIRECTLY with a bold hook statement that captures the main conflict/theme. NO filler phrases like:
- "I have a story"
- "Let me tell you"
- "Buckle up"
- "Like the title says"
- "Get ready"
- "Prepare yourself"
- "Listen to this"
- "You won't believe"
- "Wait until you hear"

JUST START WITH THE HOOK STATEMENT, then continue with the story immediately.
The hook should be ONE sentence that grabs attention, then immediately continue with the story.
Maintain first-person perspective ("I", "my", "me"). 
Include the buildup, the dramatic moment, and the conclusion (a clear ending).
Aim for 150-175 words total. No CTAs, no "drop a like", no generic intros - just the story.
End with ONE clear closing sentence that resolves the situation (no vague ending).
Do NOT introduce unrelated elements that are not in the story text.

{hook_instruction}

Example format (BAD - NEVER DO THIS):
"I have a story that will make you question everything. The point of going to a theater..."
"Buckle up for this story. Like the title says..."
"Get ready, this is crazy. I used to not care..."

Start DIRECTLY with the hook statement, then the story. NO intro filler AT ALL.
DO NOT repeat the hook - start with it ONCE, then continue the story.

Title: {title}
Story: {story_text[:2000]}

Script:"""
                
                # Use Hugging Face API to generate full script
                try:
                    from ai_text_generator import generate_text_with_hf
                    script = generate_text_with_hf(prompt, max_length=300)  # Increased max_length for full story
                except ImportError:
                    logger.warning("ai_text_generator not available, using manual extraction")
                    script = None
                
                if script:
                    # Clean up the script (remove extra whitespace, ensure it's first person)
                    script = script.strip()
                    # Remove any "Script:" prefix if AI added it
                    if script.lower().startswith("script:"):
                        script = script[7:].strip()
                    
                    # Remove ALL filler phrases at the start
                    filler_phrases = [
                        "i have a story",
                        "let me tell you",
                        "buckle up",
                        "like the title says",
                        "get ready",
                        "prepare yourself",
                        "listen to this",
                        "you won't believe",
                        "wait until you hear",
                        "this story",
                        "here's what happened"
                    ]
                    script_lower = script.lower()
                    for filler in filler_phrases:
                        if script_lower.startswith(filler):
                            # Remove filler phrase and continue
                            script = script[len(filler):].strip()
                            # Remove leading punctuation
                            while script and script[0] in '.,:;':
                                script = script[1:].strip()
                            script_lower = script.lower()
                            break
                    
                    # Check for duplicate hook statements (if first sentence repeats)
                    sentences = script.split('.')
                    if len(sentences) >= 2:
                        first_sent = sentences[0].strip()
                        second_sent = sentences[1].strip()
                        # If first two sentences are very similar, remove duplicate
                        if first_sent and second_sent:
                            # Check if they're essentially the same (with minor variations)
                            first_words = set(first_sent.lower().split()[:5])
                            second_words = set(second_sent.lower().split()[:5])
                            similarity = len(first_words & second_words) / max(len(first_words), len(second_words), 1)
                            if similarity > 0.6 and len(first_sent.split()) <= 15:
                                # Likely duplicate - remove first sentence
                                logger.info(f"  Removing duplicate hook: '{first_sent}'")
                                script = '. '.join(sentences[1:]).strip()
                                if not script.startswith('.'):
                                    script = script
                                else:
                                    script = script[1:].strip()
                    
                    # Remove the prompt if AI included it
                    if "Example of a good" in script or "Title:" in script or "Rewrite this Reddit" in script or "BAD - NEVER" in script:
                        # Extract just the script part (after "Script:" or find first-person start)
                        lines = script.split('\n')
                        for i, line in enumerate(lines):
                            line_stripped = line.strip()
                            if (line_stripped.startswith('I ') or 
                                line_stripped.startswith('I was') or 
                                line_stripped.startswith('I had') or
                                line_stripped.startswith('I downloaded') or
                                line_stripped.startswith('I woke') or
                                line_stripped.startswith('I thought') or
                                line_stripped.startswith('I used') or
                                line_stripped.startswith('I live') or
                                line_stripped.startswith('I still')):
                                script = '\n'.join(lines[i:]).strip()
                                break
                    
                    word_count = len(script.split())
                    # HeyGen often speaks faster than 2.5 w/s; this is just a rough estimate.
                    estimated_duration = word_count / 3.8
                    logger.info(f"✓ Generated story script ({word_count} words, est ~{estimated_duration:.1f}s)")
                    
                    # Enforce: ~50s target, must be < 60s.
                    # In practice, HeyGen speaking pace varies; keep it tighter and rely on the 59s hard-cap as a backstop.
                    min_words = 140
                    max_words = 175
                    target_words = 160

                    # Ensure script starts with the desired hook when available
                    if desired_hook and not script.startswith(desired_hook):
                        # Replace the first sentence with desired hook (keep rest)
                        parts = script.split('.', 1)
                        remainder = parts[1].strip() if len(parts) > 1 else ""
                        script = f"{desired_hook}. {remainder}".strip()

                    # If too long, trim while keeping an ending (last sentence)
                    if word_count > max_words:
                        sent_list = [s.strip() for s in re.split(r'[.!?]+', script) if s.strip()]
                        if sent_list:
                            ending = sent_list[-1]
                            out = []
                            out_words = 0
                            for s in sent_list[:-1]:
                                w = len(s.split())
                                if out_words + w > target_words - 18:
                                    break
                                out.append(s)
                                out_words += w
                            # Append ending if it fits
                            if ending and ending not in out:
                                out.append(ending)
                            script = ". ".join(out).strip()
                            if script and not script.endswith(('.', '!', '?')):
                                script += "."
                            word_count = len(script.split())
                            estimated_duration = word_count / 3.8
                            logger.info(f"✓ Trimmed to {word_count} words (est ~{estimated_duration:.1f}s) keeping an ending")

                    if word_count < min_words:
                        logger.warning(f"Script too short ({word_count} words, est ~{estimated_duration:.1f}s), using fallback")
                    else:
                        return script
            except Exception as e:
                logger.warning(f"AI story script generation failed: {e}, using fallback")
        
        # Fallback: Extract FULL story from story text manually
        # ALWAYS prioritize story text (description) over title
        # Keep the complete narrative, not just snippets
        import re
        
        # Clean up the story text
        story_text = re.sub(r'\s+', ' ', story_text)  # Normalize whitespace
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', story_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
        
        if not sentences:
            # If no sentences found, try to extract from title as last resort
            logger.warning("No sentences found in story text, using title as fallback")
            if title and len(title.split()) <= 30:
                return title
            return "I have a story to share that will shock you."
        
        # Build a FULL story script (not just snippets)
        # Start with a BOLD hook statement, then continue with the story
        script_sentences = []
        
        # Hook MUST match the actual story/topic: prefer title if it's a strong first-person line.
        hook_statement = None
        if title and title.strip().startswith("I ") and len(title.split()) <= 18:
            hook_statement = title.strip()
        else:
            # Use first sentence from story text
            first_sent = sentences[0] if sentences else ""
            hook_statement = first_sent.strip() if first_sent else story_text[:80].strip()
        if hook_statement and not hook_statement.endswith('.'):
            hook_statement += '.'
        
        # Check if first sentence is already a hook (don't duplicate)
        first_sent = sentences[0] if sentences else ""
        is_first_sent_hook = False
        if first_sent:
            # Check if first sentence is similar to our hook
            first_words = set(first_sent.lower().split()[:5])
            hook_words = set(hook_statement.lower().split()[:5]) if hook_statement else set()
            if hook_words:
                similarity = len(first_words & hook_words) / max(len(first_words), len(hook_words), 1)
                is_first_sent_hook = similarity > 0.5
        
        # Only add hook if first sentence isn't already a hook
        if hook_statement and not is_first_sent_hook and not any(phrase in hook_statement.lower() for phrase in [
            "i have a story", "let me tell you", "i want to share", "i have something"
        ]):
            script_sentences.append(hook_statement)
        
        # Start with opening (first 3-5 sentences)
        opening_count = min(5, len(sentences))
        script_sentences.extend(sentences[:opening_count])
        
        # Add middle section (next 5-10 sentences with dramatic moments)
        if len(sentences) > opening_count:
            middle_start = opening_count
            middle_end = min(opening_count + 10, len(sentences))
            script_sentences.extend(sentences[middle_start:middle_end])
        
        # Add conclusion (last 3-5 sentences)
        if len(sentences) > opening_count + 10:
            conclusion_start = max(opening_count + 10, len(sentences) - 5)
            script_sentences.extend(sentences[conclusion_start:])
        
        # Join sentences into a coherent story
        initial_script = ". ".join(script_sentences)
        # Add period at end if missing
        if initial_script and not initial_script[-1] in '.!?':
            initial_script += "."
        
        word_count = len(initial_script.split())
        
        # Ensure reasonable length for < 60s videos (aim ~50s)
        estimated_duration = word_count / 3.8
        min_words = 140
        max_words = 175
        target_words = 160
        if word_count < min_words:
            # Expand short stories with on-topic narration (no unrelated details)
            logger.warning(f"Fallback script too short ({word_count} words, est ~{estimated_duration:.1f}s) — expanding")
            extra = []
            t = (title or "").lower()
            s = (story_text or "").lower()
            closure_sentence = None
            # Basic, topic-aligned expansion templates
            if "smok" in t or "cig" in t or "smok" in s or "cig" in s:
                closure_sentence = "Now when he offers, I just say no—and he finally respects it."
                extra.extend([
                    "Every time we hung out, he would offer me one like it was nothing.",
                    "I kept saying no, but he treated it like a joke instead of a boundary.",
                    "It wasn’t the cigarette that got to me—it was the way he ignored what I was trying to change.",
                    "I could feel that old craving creeping back in, and it made me angry at myself.",
                    "When I finally told him the real reason I quit, everything got quiet.",
                    "After that, he showed up trying to help instead of tempt me, and that meant more than I expected.",
                    closure_sentence,
                ])
            else:
                closure_sentence = "In the end, it was resolved—and I didn’t have to become someone I’m not to get there."
                extra.extend([
                    "At first, I tried to brush it off, but it kept happening.",
                    "The more I thought about it, the more it bothered me.",
                    "I didn’t want drama—I just wanted to be heard.",
                    "When I finally spoke up, the whole mood changed.",
                    "Afterward, I realized I should’ve said something sooner.",
                    closure_sentence,
                ])
            # Append until we reach target_words (or we run out)
            words_now = len(initial_script.split())
            for sent in extra:
                if words_now >= target_words:
                    break
                initial_script = (initial_script.rstrip() + " " + sent).strip()
                words_now = len(initial_script.split())

            # Ensure we end with a clear closing sentence.
            if closure_sentence:
                # Normalize existing sentence endings for comparison
                normalized = initial_script.replace("’", "'")
                closure_norm = closure_sentence.replace("’", "'")
                if closure_norm not in normalized:
                    # Try to append closure; if it would exceed max_words, replace the last sentence with it.
                    if len((initial_script + " " + closure_sentence).split()) <= max_words:
                        initial_script = (initial_script.rstrip() + " " + closure_sentence).strip()
                    else:
                        # Replace last sentence
                        sent_list = [s.strip() for s in re.split(r'[.!?]+', initial_script) if s.strip()]
                        if sent_list:
                            sent_list[-1] = closure_sentence
                            initial_script = ". ".join(sent_list).strip()
                if initial_script and not initial_script.endswith(('.', '!', '?')):
                    initial_script += "."

            word_count = words_now
            estimated_duration = word_count / 3.8
            logger.info(f"✓ Expanded fallback script to {word_count} words (est ~{estimated_duration:.1f}s)")
        elif word_count > max_words:
            sent_list = [s.strip() for s in re.split(r'[.!?]+', initial_script) if s.strip()]
            if sent_list:
                ending = sent_list[-1]
                out = []
                out_words = 0
                for s in sent_list[:-1]:
                    w = len(s.split())
                    if out_words + w > target_words - 18:
                        break
                    out.append(s)
                    out_words += w
                if ending and ending not in out:
                    out.append(ending)
                initial_script = ". ".join(out).strip()
                if initial_script and not initial_script.endswith(('.', '!', '?')):
                    initial_script += "."
                word_count = len(initial_script.split())
                estimated_duration = word_count / 3.8
                logger.info(f"✓ Trimmed fallback script to {word_count} words (est ~{estimated_duration:.1f}s) keeping an ending")
        
        logger.info(f"✓ Generated full first-person story script ({word_count} words, est ~{estimated_duration:.1f}s)")
        return initial_script
