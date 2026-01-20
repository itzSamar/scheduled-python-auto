"""
Fetches Reddit stories from popular story subreddits.
Uses Reddit's public JSON API (no authentication required).
"""
import logging
import time
import random
import os
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from config import MAX_RETRIES, RETRIABLE_STATUS_CODES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# File to track used topics
USED_TOPICS_FILE = "used_topics.json"

# Popular Reddit story subreddits
REDDIT_STORY_SUBREDDITS = [
    "tifu",              # Today I Fucked Up
    "AmItheAsshole",     # AITA
    "relationship_advice",
    "entitledparents",
    "MaliciousCompliance",
    "ProRevenge",
    "pettyrevenge",
    "confession",
    "TrueOffMyChest",
    "unpopularopinion",
    "AskReddit",         # Sometimes has good stories
    "stories",
    "shortstories",
]


class RedditFetcher:
    """Fetches Reddit stories from popular story subreddits."""
    
    def __init__(self):
        """Initialize RedditFetcher."""
        self.base_url = "https://www.reddit.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        }
    
    def fetch_reddit_stories(self, subreddit: str = None, max_results: int = 10, sort: str = "hot") -> List[Dict]:
        """
        Fetch Reddit stories from a subreddit.
        
        Args:
            subreddit: Subreddit name (if None, tries multiple popular story subreddits)
            max_results: Maximum number of results to return
            sort: Sort order ("hot", "new", "top", "rising")
            
        Returns:
            List of Reddit post dictionaries with title, selftext, etc.
        """
        stories = []
        retry = 0
        
        # If no subreddit specified, try multiple popular ones
        subreddits_to_try = [subreddit] if subreddit else REDDIT_STORY_SUBREDDITS
        
        while retry < MAX_RETRIES and subreddits_to_try:
            try:
                # Pick a random subreddit if multiple available
                current_subreddit = random.choice(subreddits_to_try) if len(subreddits_to_try) > 1 else subreddits_to_try[0]
                subreddits_to_try.remove(current_subreddit)
                
                logger.info(f"Fetching Reddit stories from r/{current_subreddit} (attempt {retry + 1})...")
                
                # Reddit JSON API endpoint
                url = f"{self.base_url}/r/{current_subreddit}/{sort}.json"
                params = {
                    'limit': min(max_results * 2, 100),  # Get more to filter
                }
                
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                if 'data' in data and 'children' in data['data']:
                    posts = data['data']['children']
                    
                    for post_data in posts:
                        post = post_data.get('data', {})
                        
                        # Filter for text posts (stories) - skip images/videos/links
                        if post.get('is_self', False) and post.get('selftext', ''):
                            # Skip removed/deleted posts
                            if post.get('selftext') in ['[removed]', '[deleted]']:
                                continue
                            
                            # Skip very short posts (likely not stories)
                            if len(post.get('selftext', '')) < 100:
                                continue
                            
                            # Skip very long posts (too long for YouTube Shorts)
                            if len(post.get('selftext', '')) > 5000:
                                continue
                            
                            story_data = {
                                "id": post.get('id', ''),
                                "title": post.get('title', ''),
                                "text": post.get('selftext', ''),
                                "subreddit": post.get('subreddit', current_subreddit),
                                "author": post.get('author', ''),
                                "score": post.get('score', 0),
                                "num_comments": post.get('num_comments', 0),
                                "created_utc": post.get('created_utc', 0),
                                "url": f"https://www.reddit.com{post.get('permalink', '')}",
                                "upvote_ratio": post.get('upvote_ratio', 0),
                            }
                            
                            stories.append(story_data)
                            
                            if len(stories) >= max_results:
                                break
                    
                    if stories:
                        logger.info(f"Found {len(stories)} Reddit stories from r/{current_subreddit}")
                        return stories[:max_results]
                    else:
                        logger.info(f"No suitable stories found in r/{current_subreddit}, trying next...")
                        continue
                else:
                    logger.warning(f"Unexpected response format from r/{current_subreddit}")
                    continue
                    
            except requests.exceptions.RequestException as e:
                retry += 1
                wait_time = (2 ** retry) + random.random()
                logger.warning(f"Error fetching Reddit stories, retrying in {wait_time:.2f}s... ({e})")
                if retry >= MAX_RETRIES:
                    logger.error(f"Failed to fetch Reddit stories after {MAX_RETRIES} attempts")
                    if subreddits_to_try:
                        retry = 0  # Reset retry counter for next subreddit
                        continue
                    break
                time.sleep(wait_time)
            except Exception as e:
                logger.error(f"Unexpected error fetching Reddit stories: {e}")
                if subreddits_to_try:
                    continue
                break
        
        logger.warning(f"Could not fetch enough Reddit stories. Found {len(stories)} stories.")
        return stories[:max_results]
    
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
    
    def _normalize_topic_title(self, title: str) -> str:
        """Normalize topic title for comparison (remove extra spaces, lowercase)."""
        return title.lower().strip()
    
    def _is_topic_used(self, topic_title: str) -> bool:
        """Check if a topic has already been used."""
        used_topics = self._load_used_topics()
        normalized = self._normalize_topic_title(topic_title)
        return normalized in used_topics
    
    def get_reddit_story_for_video(self, max_results: int = 20) -> Optional[Dict]:
        """
        Get a single Reddit story suitable for video creation.
        Skips stories that have already been used.
        Prioritizes popular/recent stories.
        
        Args:
            max_results: Maximum number of stories to fetch for selection
            
        Returns:
            Dictionary with story information for video creation, or None
        """
        # Fetch stories from multiple subreddits
        stories = self.fetch_reddit_stories(max_results=max_results, sort="hot")
        
        if not stories:
            return None
        
        # Sort by score (upvotes) - most popular first
        stories.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        # Try to find a story that hasn't been used yet
        selected_story = None
        for story in stories:
            story_title = story.get("title", "")
            if story_title and not self._is_topic_used(story_title):
                selected_story = story
                logger.info(f"Selected new Reddit story: {story_title[:60]}...")
                logger.info(f"  From r/{story.get('subreddit', 'unknown')} ({story.get('score', 0)} upvotes)")
                break
        
        # If all stories have been used, use the top one anyway
        if not selected_story:
            selected_story = stories[0] if stories else None
            if selected_story:
                story_title = selected_story.get("title", "")
                logger.warning(f"All Reddit stories have been used. Reusing: {story_title[:60]}...")
                logger.warning("Consider fetching more results or clearing used_topics.json")
        
        if not selected_story:
            return None
        
        story_title = selected_story.get("title", "")
        story_text = selected_story.get("text", "")
        
        # Extract keywords from title and text
        import re
        text_for_keywords = f"{story_title} {story_text[:500]}".lower()
        words = re.findall(r'\b\w{4,}\b', text_for_keywords)  # Words with 4+ characters
        # Remove common stop words
        stop_words = {"that", "this", "with", "from", "have", "been", "were", "they", "what", "when", "where", "which", "would", "could", "should", "about", "after", "before", "during", "until", "while"}
        keywords = [w for w in words if w not in stop_words][:10]
        
        return {
            "title": story_title,
            "description": story_text[:1000],  # First 1000 chars for description
            "keywords": keywords,
            "subreddit": selected_story.get("subreddit", ""),
            "score": selected_story.get("score", 0),
            "num_comments": selected_story.get("num_comments", 0),
            "url": selected_story.get("url", ""),
            "_topic_title": story_title  # Store for tracking
        }

