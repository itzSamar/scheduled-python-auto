"""
Fetches Reddit stories from funny/dramatic story subreddits.

Reddit's public JSON API is tried first; when it refuses (403/429, common for unauthenticated clients)
the Arctic Shift archive (https://arctic-shift.photon-reddit.com) serves the same posts with full text.
"""
import json
import logging
import os
import random
import re
import time
from typing import Dict, List, Optional

import requests

from .config import REJECTED_TOPICS_PATH, USED_TOPICS_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USED_TOPICS_FILE = USED_TOPICS_PATH
REJECTED_TOPICS_FILE = REJECTED_TOPICS_PATH
ARCTIC_SHIFT_URL = "https://arctic-shift.photon-reddit.com/api"

# Funny / dramatic story subreddits that adapt well to family-friendly cartoons
REDDIT_STORY_SUBREDDITS = [
    "MaliciousCompliance",
    "pettyrevenge",
    "entitledparents",
    "ChoosingBeggars",
    "IDontWorkHereLady",
    "TalesFromRetail",
    "TalesFromYourServer",
    "tifu",
    "AmItheAsshole",
    "ProRevenge",
]
FAVORED_SUBREDDITS = {"maliciouscompliance", "pettyrevenge", "entitledparents", "choosingbeggars", "idontworkherelady"}

MIN_TEXT, MAX_TEXT = 300, 5000
# Archive scores only settle after a few days; posts below this rarely have a payoff people liked.
MIN_ARCHIVE_SCORE = 150


class RedditFetcher:
    """Fetches Reddit stories from popular story subreddits."""

    def __init__(self):
        self.base_url = "https://www.reddit.com"
        self.headers = {"User-Agent": "AnimatedRedditStories/2.0 (story research; contact via channel)"}
        self._live_blocked = False

    # ----------------------------
    # Sources
    # ----------------------------
    def _fetch_live(self, subreddit: str, sort: str, limit: int) -> Optional[List[Dict]]:
        """Posts from reddit.com, or None when Reddit refuses unauthenticated access."""
        if self._live_blocked:
            return None
        try:
            r = requests.get(f"{self.base_url}/r/{subreddit}/{sort}.json", headers=self.headers,
                             params={"limit": min(limit, 100), "t": "month"}, timeout=20)
        except requests.RequestException as e:
            logger.warning(f"reddit.com unreachable ({e}); using the archive")
            self._live_blocked = True
            return None
        if r.status_code in (401, 403, 429):
            logger.info(f"reddit.com returned {r.status_code}; using the Arctic Shift archive")
            self._live_blocked = True
            return None
        if r.status_code != 200:
            return None
        return [c.get("data", {}) for c in (r.json().get("data") or {}).get("children", [])]

    def _fetch_archive(self, subreddit: str, limit: int) -> List[Dict]:
        """Recent-but-settled posts from the Arctic Shift archive (random window 3-60 days back)."""
        before = int(time.time() - random.uniform(3, 60) * 86400)
        posts: List[Dict] = []
        # The archive answers 422 "Timeout. Maybe slow down a bit" on wide windows of busy subs; retry narrower.
        for attempt, days in enumerate((21, 7)):
            try:
                r = requests.get(f"{ARCTIC_SHIFT_URL}/posts/search", timeout=40, params={
                    "subreddit": subreddit, "after": before - days * 86400, "before": before,
                    "limit": 100, "sort": "desc",
                })
                r.raise_for_status()
                posts = r.json().get("data") or []
                break
            except Exception as e:
                if attempt == 0:
                    time.sleep(2)
                    continue
                logger.warning(f"Arctic Shift fetch failed for r/{subreddit}: {e}")
                return []
        posts = [p for p in posts if (p.get("score") or 0) >= MIN_ARCHIVE_SCORE]
        posts.sort(key=lambda p: p.get("score") or 0, reverse=True)
        return posts[:limit]

    @staticmethod
    def _usable(post: Dict) -> bool:
        text = post.get("selftext") or ""
        return (
            post.get("is_self", True)
            and not post.get("over_18")
            and not post.get("removed_by_category")
            and text not in ("[removed]", "[deleted]")
            and MIN_TEXT <= len(text) <= MAX_TEXT
        )

    @staticmethod
    def _to_story(post: Dict, subreddit: str) -> Dict:
        return {
            "id": post.get("id", ""),
            "title": post.get("title", ""),
            "text": post.get("selftext", ""),
            "subreddit": post.get("subreddit", subreddit),
            "author": post.get("author", ""),
            "score": post.get("score", 0),
            "num_comments": post.get("num_comments", 0),
            "created_utc": post.get("created_utc", 0),
            "url": f"https://www.reddit.com{post.get('permalink', '')}",
            "upvote_ratio": post.get("upvote_ratio", 0),
        }

    def fetch_reddit_stories(self, subreddit: str = None, max_results: int = 10, sort: str = "hot") -> List[Dict]:
        """Story posts from one subreddit (or the first random story subreddit that has some)."""
        subs = [subreddit] if subreddit else random.sample(REDDIT_STORY_SUBREDDITS, len(REDDIT_STORY_SUBREDDITS))
        for sub in subs:
            posts = self._fetch_live(sub, sort, max_results * 2)
            if posts is None:
                posts = self._fetch_archive(sub, max_results * 2)
            stories = [self._to_story(p, sub) for p in posts if self._usable(p)]
            if stories:
                logger.info(f"Found {len(stories)} stories in r/{sub}")
                return stories[:max_results]
        logger.warning("Could not fetch any Reddit stories")
        return []

    def _fetch_mixed(self, max_results: int, subreddit_count: int = 4) -> List[Dict]:
        """Stories from several random story subreddits, deduplicated by post id."""
        by_id: Dict[str, Dict] = {}
        for sub in random.sample(REDDIT_STORY_SUBREDDITS, min(subreddit_count, len(REDDIT_STORY_SUBREDDITS))):
            for s in self.fetch_reddit_stories(subreddit=sub, max_results=max_results, sort="top"):
                by_id[s.get("id") or f"{s.get('subreddit', '')}-{s.get('title', '')}"] = s
        return list(by_id.values())

    # ----------------------------
    # Topic bookkeeping
    # ----------------------------
    def _load_used_topics(self) -> set:
        if not os.path.exists(USED_TOPICS_FILE):
            return set()
        try:
            with open(USED_TOPICS_FILE, "r") as f:
                return set((json.load(f) or {}).get("used_topics", []))
        except Exception as e:
            logger.warning(f"Could not load used topics file: {e}")
            return set()

    def _save_used_topic(self, topic_title: str):
        used_topics = self._load_used_topics()
        used_topics.add(self._normalize_topic_title(topic_title))
        try:
            with open(USED_TOPICS_FILE, "w") as f:
                json.dump({"used_topics": list(used_topics)}, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save used topic: {e}")

    def _normalize_topic_title(self, title: str) -> str:
        return title.lower().strip()

    def _is_topic_used(self, topic_title: str) -> bool:
        return self._normalize_topic_title(topic_title) in self._load_used_topics()

    def _load_rejected_topics(self) -> set:
        if not os.path.exists(REJECTED_TOPICS_FILE):
            return set()
        try:
            with open(REJECTED_TOPICS_FILE, "r") as f:
                return set((json.load(f) or {}).get("rejected_topics", []))
        except Exception as e:
            logger.warning(f"Could not load rejected topics file: {e}")
            return set()

    def _save_rejected_topic(self, topic_title: str, reason: str = "") -> None:
        rejected = self._load_rejected_topics()
        rejected.add(self._normalize_topic_title(topic_title))
        try:
            with open(REJECTED_TOPICS_FILE, "w") as f:
                json.dump({"rejected_topics": list(rejected), "last_reason": reason}, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save rejected topic: {e}")

    def _is_topic_rejected(self, topic_title: str) -> bool:
        return self._normalize_topic_title(topic_title) in self._load_rejected_topics()

    # ----------------------------
    # Selection
    # ----------------------------
    @staticmethod
    def _story_score(story: Dict) -> float:
        # Upvotes + comments + upvote ratio, compressed so extreme scores don't dominate.
        score = float(story.get("score", 0) or 0)
        comments = float(story.get("num_comments", 0) or 0)
        ratio = float(story.get("upvote_ratio", 0.0) or 0.0)
        base = (score ** 0.6) * (1.0 + min(3.0, comments / 150.0)) * (0.8 + ratio)
        if (story.get("subreddit") or "").lower() in FAVORED_SUBREDDITS:
            base *= 1.08
        return base

    def get_story_candidates(self, max_results: int = 20, limit: int = 8) -> List[Dict]:
        """Unused, non-rejected stories ranked by engagement (as trend_data dicts), for the writer to triage."""
        stories = [
            s for s in self._fetch_mixed(max_results)
            if s.get("title") and not self._is_topic_used(s["title"]) and not self._is_topic_rejected(s["title"])
        ]
        stories.sort(key=self._story_score, reverse=True)
        return [self._to_trend_data(s) for s in stories[:limit]]

    def get_reddit_story_for_video(self, max_results: int = 20) -> Optional[Dict]:
        """One unused story, picked at random from the best-engagement slice."""
        candidates = self.get_story_candidates(max_results=max_results, limit=12)
        if not candidates:
            return None
        return random.choice(candidates[: min(5, len(candidates))])

    def fetch_story_by_url(self, url: str) -> Optional[Dict]:
        """Fetch one hand-picked Reddit post (e.g. https://www.reddit.com/r/x/comments/abc/title/)."""
        u = (url or "").strip().split("?", 1)[0].rstrip("/")
        m = re.search(r"/comments/([a-z0-9]+)", u)
        if not m:
            logger.error(f"Not a Reddit post URL: {url}")
            return None
        post = None
        try:
            r = requests.get(u + ".json", headers=self.headers, timeout=20)
            if r.status_code == 200:
                data = r.json()
                post = data[0]["data"]["children"][0]["data"]
        except Exception:
            post = None
        if post is None:
            try:
                r = requests.get(f"{ARCTIC_SHIFT_URL}/posts/ids", params={"ids": m.group(1)}, timeout=30)
                r.raise_for_status()
                posts = r.json().get("data") or []
                post = posts[0] if posts else None
            except Exception as e:
                logger.error(f"Could not fetch Reddit post {url}: {e}")
                return None
        if not post or not post.get("selftext") or post.get("selftext") in ("[removed]", "[deleted]"):
            logger.error(f"Reddit post has no story text: {url}")
            return None
        return self._to_trend_data(self._to_story(post, post.get("subreddit", "")))

    def _to_trend_data(self, selected_story: Dict) -> Dict:
        story_title = selected_story.get("title", "")
        story_text = selected_story.get("text", "")
        text_for_keywords = f"{story_title} {story_text[:500]}".lower()
        words = re.findall(r"\b\w{4,}\b", text_for_keywords)
        stop_words = {"that", "this", "with", "from", "have", "been", "were", "they", "what", "when", "where", "which",
                      "would", "could", "should", "about", "after", "before", "during", "until", "while"}
        keywords = [w for w in words if w not in stop_words][:10]
        return {
            "title": story_title,
            "description": story_text[:1000],
            "text": story_text,
            "keywords": keywords,
            "subreddit": selected_story.get("subreddit", ""),
            "score": selected_story.get("score", 0),
            "num_comments": selected_story.get("num_comments", 0),
            "url": selected_story.get("url", ""),
            "upvote_ratio": selected_story.get("upvote_ratio", 0),
            "_topic_title": story_title,
        }
