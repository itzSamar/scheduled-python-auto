"""
Fetches trending YouTube videos using YouTube Data API.
Now focused on Roblox content specifically.
Analyzes trending content to identify topics for video creation.
"""
import logging
import time
import random
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from googleapiclient.errors import HttpError
from config import MAX_RETRIES, RETRIABLE_STATUS_CODES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# File to track used topics
USED_TOPICS_FILE = "used_topics.json"


class TrendsFetcher:
    """Fetches and analyzes YouTube trending videos."""
    
    def __init__(self, youtube_service=None):
        """
        Initialize TrendsFetcher.
        
        Args:
            youtube_service: Authenticated YouTube API service object
        """
        self.youtube_service = youtube_service
        if not self.youtube_service:
            raise ValueError("YouTube service is required")
    
    def fetch_trending_videos(self, region: str = "US", max_results: int = 10, roblox_only: bool = True) -> List[Dict]:
        """
        Fetch trending YouTube videos using YouTube Data API.
        Now focused on Roblox content specifically.
        
        Args:
            region: Country code for trending videos (default: US)
            max_results: Maximum number of results to return
            roblox_only: If True, only fetch Roblox-related content (default: True)
            
        Returns:
            List of trending video dictionaries with title, description, etc.
        """
        videos = []
        retry = 0
        
        while retry < MAX_RETRIES:
            try:
                if roblox_only:
                    logger.info(f"Fetching trending Roblox videos (attempt {retry + 1})...")
                else:
                    logger.info(f"Fetching trending videos (attempt {retry + 1})...")
                
                if roblox_only:
                    # Search for Roblox-related trending content
                    # Use search API with Roblox keywords and sort by viewCount
                    search_request = self.youtube_service.search().list(
                        part="snippet",
                        q="Roblox",
                        type="video",
                        order="viewCount",
                        publishedAfter=(datetime.now() - timedelta(days=7)).isoformat() + "Z",  # Last 7 days
                        maxResults=min(max_results * 2, 50),  # Get more to filter
                        regionCode=region
                    )
                    search_response = search_request.execute()
                    
                    # Extract video IDs from search results
                    video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
                    
                    if not video_ids:
                        logger.warning("No Roblox videos found in search")
                        return []
                    
                    # Get detailed video information
                    request = self.youtube_service.videos().list(
                        part="snippet,statistics",
                        id=",".join(video_ids[:max_results]),
                        maxResults=min(len(video_ids), max_results)
                    )
                else:
                    # Original behavior: fetch general trending videos
                    request = self.youtube_service.videos().list(
                        part="snippet,statistics",
                        chart="mostPopular",
                        regionCode=region,
                        maxResults=min(max_results, 50)  # YouTube API max is 50
                    )
                
                response = request.execute()
                
                if "items" in response:
                    current_date = datetime.now()
                    # Prioritize videos from the last 7 days for Roblox content (very recent trending)
                    recent_cutoff = current_date - timedelta(days=7)
                    
                    recent_videos = []
                    older_videos = []
                    
                    for item in response["items"]:
                        published_at_str = item["snippet"].get("publishedAt", "")
                        video_data = {
                            "id": item["id"],
                            "video_id": item["id"],
                            "title": item["snippet"].get("title", ""),
                            "description": item["snippet"].get("description", ""),
                            "channel_name": item["snippet"].get("channelTitle", ""),
                            "channel_id": item["snippet"].get("channelId", ""),
                            "published_at": published_at_str,
                            "view_count": item["statistics"].get("viewCount", "0"),
                            "like_count": item["statistics"].get("likeCount", "0"),
                            "tags": item["snippet"].get("tags", [])
                        }
                        
                        # Parse publish date to check if recent
                        try:
                            if published_at_str:
                                # YouTube API returns ISO 8601 format: 2025-01-15T10:30:00Z
                                published_date = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                                if published_date.replace(tzinfo=None) >= recent_cutoff:
                                    recent_videos.append(video_data)
                                else:
                                    older_videos.append(video_data)
                            else:
                                # If no date, treat as older
                                older_videos.append(video_data)
                        except Exception:
                            # If date parsing fails, add to older (safer)
                            older_videos.append(video_data)
                    
                    # Filter for Roblox-related content if roblox_only is True
                    if roblox_only:
                        roblox_videos = []
                        for video in recent_videos + older_videos:
                            title_lower = video.get("title", "").lower()
                            desc_lower = video.get("description", "").lower()
                            tags_lower = " ".join(video.get("tags", [])).lower()
                            
                            # Check if video is Roblox-related
                            roblox_keywords = ["roblox", "blox", "rblx", "obbie", "obby"]
                            if any(keyword in title_lower or keyword in desc_lower or keyword in tags_lower 
                                   for keyword in roblox_keywords):
                                roblox_videos.append(video)
                        
                        videos = roblox_videos
                        if roblox_videos:
                            logger.info(f"Found {len(roblox_videos)} Roblox-related trending videos")
                    else:
                        # Prioritize recent videos, then add older ones
                        videos = recent_videos + older_videos
                        if recent_videos:
                            logger.info(f"Found {len(recent_videos)} recent trending videos (last 7 days)")
                
                logger.info(f"Successfully fetched {len(videos)} trending videos")
                return videos[:max_results]
                
            except HttpError as e:
                if e.resp.status in RETRIABLE_STATUS_CODES:
                    retry += 1
                    wait_time = (2 ** retry) + random.random()
                    logger.warning(f"Retriable HTTP error {e.resp.status}, retrying in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"HTTP error: {e}")
                    raise
            except Exception as e:
                retry += 1
                wait_time = (2 ** retry) + random.random()
                logger.warning(f"Error fetching trends, retrying in {wait_time:.2f}s...")
                if retry >= MAX_RETRIES:
                    logger.error(f"Failed to fetch trends after {MAX_RETRIES} attempts: {e}")
                    raise
                time.sleep(wait_time)
        
        return []
    
    def analyze_trending_topics(self, videos: List[Dict]) -> Dict[str, any]:
        """
        Analyze trending videos to extract common topics and keywords.
        
        Args:
            videos: List of trending video dictionaries
            
        Returns:
            Dictionary with analyzed topics, keywords, and trends
        """
        if not videos:
            return {
                "topics": [],
                "keywords": [],
                "common_themes": [],
                "top_video": None
            }
        
        # Extract titles and descriptions
        titles = [v.get("title", "") for v in videos if v.get("title")]
        descriptions = [v.get("description", "") for v in videos if v.get("description")]
        
        # Simple keyword extraction (can be enhanced with NLP)
        all_text = " ".join(titles + descriptions).lower()
        
        # Common words to ignore
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "are", "was", "were", "this", "that", "video", "watch", "youtube"}
        
        # Extract keywords (simple approach - can be improved)
        words = all_text.split()
        word_freq = {}
        for word in words:
            word = word.strip(".,!?;:()[]{}'\"")
            if len(word) > 3 and word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get top keywords
        top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Get top video (first one, or can be based on views/likes)
        top_video = videos[0] if videos else None
        
        return {
            "topics": titles[:5],  # Top 5 trending topics
            "keywords": [kw[0] for kw in top_keywords],
            "common_themes": list(set([v.get("channel_name", "") for v in videos[:5] if v.get("channel_name")])),
            "top_video": top_video,
            "video_count": len(videos)
        }
    
    def _load_used_topics(self) -> set:
        """Load previously used topics from file."""
        if not os.path.exists(USED_TOPICS_FILE):
            return set()
        
        try:
            with open(USED_TOPICS_FILE, 'r') as f:
                data = json.load(f)
                return set(data.get("used_topics", []))
        except Exception as e:
            logger.warning(f"Could not load used topics file: {e}")
            return set()
    
    def _save_used_topic(self, topic_title: str):
        """Save a topic title to the used topics file."""
        used_topics = self._load_used_topics()
        normalized = self._normalize_topic_title(topic_title)
        used_topics.add(normalized)
        
        try:
            with open(USED_TOPICS_FILE, 'w') as f:
                json.dump({"used_topics": list(used_topics)}, f, indent=2)
            logger.debug(f"Saved used topic: {topic_title}")
        except Exception as e:
            logger.warning(f"Could not save used topic: {e}")
    
    def clear_used_topics(self):
        """Clear all used topics (useful for testing or reset)."""
        try:
            if os.path.exists(USED_TOPICS_FILE):
                os.remove(USED_TOPICS_FILE)
                logger.info("Cleared used topics file")
            else:
                logger.info("No used topics file to clear")
        except Exception as e:
            logger.warning(f"Could not clear used topics: {e}")
    
    def get_used_topics_count(self) -> int:
        """Get the number of topics that have been used."""
        return len(self._load_used_topics())
    
    def _normalize_topic_title(self, title: str) -> str:
        """Normalize topic title for comparison (remove extra spaces, lowercase)."""
        return title.lower().strip()
    
    def _is_topic_used(self, topic_title: str) -> bool:
        """Check if a topic has already been used."""
        used_topics = self._load_used_topics()
        normalized = self._normalize_topic_title(topic_title)
        return normalized in used_topics
    
    def get_trending_topic_for_video(self, region: str = "US", roblox_only: bool = True) -> Optional[Dict]:
        """
        Get a single trending topic suitable for video creation.
        Now focused on Roblox content specifically.
        Skips topics that have already been used.
        Prioritizes recent/current trending content.
        
        Args:
            region: Country code for trending videos
            roblox_only: If True, only fetch Roblox-related content (default: True)
            
        Returns:
            Dictionary with topic information for video creation, or None
        """
        # Fetch more videos to have options if some are already used
        # Increased to 20 for Roblox content to have more options
        videos = self.fetch_trending_videos(region=region, max_results=20, roblox_only=roblox_only)
        if not videos:
            return None
        
        # Videos are already sorted by recency (recent first) from fetch_trending_videos
        # So we'll naturally prioritize recent content
        
        analysis = self.analyze_trending_topics(videos)
        
        # Try to find a video that hasn't been used yet (prioritizing recent ones)
        selected_video = None
        for video in videos:
            video_title = video.get("title", "")
            if video_title and not self._is_topic_used(video_title):
                selected_video = video
                logger.info(f"Selected new trending topic: {video_title}")
                # Log publish date if available to show it's recent
                pub_date = video.get("published_at", "")
                if pub_date:
                    try:
                        from datetime import datetime
                        pub_dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                        days_ago = (datetime.now() - pub_dt.replace(tzinfo=None)).days
                        if days_ago <= 7:
                            logger.info(f"  ✓ Very recent content (published {days_ago} days ago)")
                        elif days_ago <= 30:
                            logger.info(f"  ✓ Recent content (published {days_ago} days ago)")
                    except:
                        pass
                break
        
        # If all trending videos have been used, use the top one anyway
        # (but log a warning)
        if not selected_video:
            selected_video = analysis.get("top_video")
            if selected_video:
                video_title = selected_video.get("title", "")
                logger.warning(f"All trending topics have been used. Reusing: {video_title}")
                logger.warning("Consider fetching more results or clearing used_topics.json")
        
        if not selected_video:
            return None
        
        # Mark this topic as used (will be saved after successful video creation)
        video_title = selected_video.get("title", "")
        
        return {
            "title": video_title,
            "description": selected_video.get("description", ""),
            "keywords": analysis.get("keywords", [])[:5],
            "trending_topics": analysis.get("topics", [])[:3],
            "source_video_id": selected_video.get("video_id") or selected_video.get("id", ""),
            "channel": selected_video.get("channel_name", ""),
            "published_at": selected_video.get("published_at", ""),
            "_topic_title": video_title  # Store for tracking
        }

