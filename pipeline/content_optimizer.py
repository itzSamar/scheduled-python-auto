"""
Optimizes video metadata (titles, descriptions, hashtags) for maximum engagement.
Uses trending keywords and SEO best practices.
"""
import logging
from typing import Dict, List, Optional
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ContentOptimizer:
    """Optimizes content metadata for YouTube SEO and engagement."""
    
    def __init__(self):
        """Initialize ContentOptimizer."""
        pass
    
    def generate_title(self, base_topic: str, keywords: List[str] = None, max_length: int = 100, script: str = None) -> str:
        """
        Generate an optimized YouTube title for Reddit stories.
        Uses story hooks or bold statements from the script.
        
        Args:
            base_topic: Main topic or inspiration for the video
            keywords: List of trending keywords to include
            max_length: Maximum title length (YouTube limit is 100)
            script: Optional script text to extract hook from
            
        Returns:
            Optimized title string
        """
        keywords = keywords or []
        
        # If script is provided, try to extract the bold hook statement
        if script:
            # Extract first sentence (usually the hook)
            import re
            first_sentence = script.split('.')[0].strip() if '.' in script else script.split('\n')[0].strip()

            # Prefer the hook as the title for Reddit stories (keeps title aligned with content).
            # Only reject obviously generic filler hooks.
            generic_hooks = {
                "this one is wild",
                "here’s what happened",
                "heres what happened",
                "listen to this",
                "wait for it",
            }
            cleaned = re.sub(r"[^a-zA-Z0-9' ]+", "", first_sentence).strip().lower()
            if cleaned and cleaned not in generic_hooks:
                title = first_sentence.strip()
                if not title.endswith(('.', '!', '?')):
                    title += '.'
                if len(title) <= max_length:
                    logger.info(f"✓ Using script hook as title: {title}")
                    return title
                # Truncate intelligently if too long
                words = title.split()
                title = ' '.join(words[:12]).rstrip('.') + '...'
                if len(title) <= max_length:
                    logger.info(f"✓ Using truncated script hook as title: {title}")
                    return title
        
        # Story-style title templates (for Reddit stories)
        story_templates = [
            "You'll Never Believe What Happened... 😱",
            "This Story Will Shock You 🤯",
            "I Can't Believe This Happened To Me 😳",
            "You Won't Believe What I Found Out... 😨",
            "This Changed Everything For Me 💥",
            "I Thought It Was Normal Until... 😰",
            "Wait Until You Hear This Story... 👂",
            "This Is The Craziest Thing That Ever Happened To Me 🤯",
            "You'll Never Guess What Happened Next... 😱",
            "I Still Can't Believe This Happened 😳",
            "This Story Will Make You Question Everything 🤔",
            "Wait... What?! 😱",
            "I Had No Idea This Was Happening... 😨",
            "This Story Is Too Crazy To Be True 🤯",
            "You Need To Hear This Story... 👂"
        ]
        
        # If we have a hook-like topic, use it directly
        if base_topic and base_topic.startswith('I ') and len(base_topic.split()) <= 15:
            title = base_topic
            if not title.endswith('.'):
                title += '.'
            if len(title) <= max_length:
                return title
        
        # Use story-style template
        import random
        template = random.choice(story_templates)
        
        # Don't use topic in story templates - they're standalone hooks
        title = template
        
        # Ensure title doesn't exceed max length
        if len(title) > max_length:
            title = title[:max_length-3] + "..."
        
        return title.strip()
    
    def generate_description(self, title: str, base_topic: str, keywords: List[str] = None,
                           video_info: Dict = None, script: str = None, music_credit: str = None) -> str:
        """
        YouTube description. The first lines are what Shorts shows under the video:
        the hook, then this story's own question, so comments are about the dilemma.
        """
        keywords = keywords or []
        video_info = video_info or {}

        subreddit = (video_info.get("subreddit") or "").strip() if isinstance(video_info, dict) else ""
        score = video_info.get("score") if isinstance(video_info, dict) else None
        reddit_url = (video_info.get("url") or "").strip() if isinstance(video_info, dict) else ""
        if reddit_url.startswith("queue:") or reddit_url.startswith("screenplay:"):
            reddit_url = ""

        hook = (title or base_topic or "").split("#")[0].strip()
        spoken = re.sub(r"\s+", " ", script or "").strip()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", spoken) if s.strip()]
        question = next((s for s in reversed(sentences) if s.endswith("?")), "What would you have done?")
        bits = []
        for s in sentences:
            if s.endswith("?") or s.lower().rstrip(".!") in hook.lower():
                continue
            bits.append(s)
            if len(" ".join(bits)) > 110 or len(bits) == 2:
                break
        setup = " ".join(bits)

        lines = [hook, ""]
        if setup:
            lines += [setup, ""]
        lines += [question, ""]

        if subreddit:
            meta = f"Animated Reddit story from r/{subreddit}"
            if isinstance(score, (int, float)) and score:
                meta += f" · {int(score):,} upvotes"
            lines.append(meta)
        else:
            lines.append("Animated Reddit story.")
        if reddit_url:
            lines.append(f"Original post: {reddit_url}")
        lines += ["", "New cartoon Reddit stories every day. Subscribe so you catch the next one."]
        if music_credit:
            lines += ["", music_credit.strip()]

        tags = ["shorts", "redditstories", "animatedstory", "storytime"]
        if subreddit:
            tags.append(re.sub(r"[^a-z0-9]", "", subreddit.lower()))
        lines += ["", " ".join(f"#{t}" for t in tags if t)]

        description = "\n".join(lines).strip()
        
        # Ensure description doesn't exceed YouTube's 5000 character limit
        if len(description) > 5000:
            description = description[:4997] + "..."
        
        return description.strip()
    
    def generate_tags(self, keywords: List[str], base_topic: str, max_tags: int = 15) -> List[str]:
        """
        Generate optimized tags for YouTube.
        
        Args:
            keywords: List of trending keywords
            base_topic: Main topic
            max_tags: Maximum number of tags (YouTube allows up to 500 characters total)
            
        Returns:
            List of tag strings
        """
        tags = []
        # Whole phrases from the story, not single leftover words like "exactly" or "5:00".
        tags.extend(keywords[:10])
        
        common_tags = [
            "reddit stories",
            "reddit storytime",
            "animated story",
            "animated reddit story",
            "storytime",
            "funny stories",
            "cartoon",
            "shorts",
            "malicious compliance",
        ]
        # Channel tags first so they survive the length cap; topic words fill the rest.
        tags = common_tags + tags

        seen = set()
        tags = [t.strip() for t in tags if t and len(t.strip()) > 2 and not (t.strip() in seen or seen.add(t.strip()))]
        
        # Limit total character count (YouTube limit is 500 chars)
        final_tags = []
        char_count = 0
        for tag in tags:
            tag_with_comma = tag + ","
            if char_count + len(tag_with_comma) <= 500 and len(final_tags) < max_tags:
                final_tags.append(tag)
                char_count += len(tag_with_comma)
            else:
                break
        
        return final_tags
    
    def generate_hashtags(self, keywords: List[str], base_topic: str, max_hashtags: int = 3) -> List[str]:
        """
        Generate hashtags for YouTube description - simple 3 hashtag strategy.
        Uses only the most important hashtags: #redditstories, #reddit, and #shorts.
        
        Args:
            keywords: List of keywords (not used, kept for compatibility)
            base_topic: Main topic (not used, kept for compatibility)
            max_hashtags: Maximum number of hashtags (default: 3)
            
        Returns:
            List of hashtag strings (without # symbol)
        """
        hashtags = []
        
        # Only 3 hashtags: redditstories, reddit, and shorts
        hashtags.append("redditstories")
        hashtags.append("reddit")
        hashtags.append("shorts")
        
        # Return only the 3 hashtags
        return hashtags[:max_hashtags]
    
    def optimize_metadata(self, trend_data: Dict, script: str = None, title: str = None,
                          music_credit: str = None) -> Dict[str, any]:
        """
        Generate complete optimized metadata for a video.
        
        Args:
            trend_data: Dictionary with story information from RedditFetcher
            script: Optional script text to extract hook from for title
            title: Title written with the screenplay; preferred over the script hook
            
        Returns:
            Dictionary with optimized title, description, tags, and hashtags
        """
        base_topic = trend_data.get("title", "Trending Topic")
        keywords = trend_data.get("keywords", [])
        
        title = (title or "").strip() or self.generate_title(base_topic, keywords, script=script)
        # The title is the hook on its own. Hashtags go at the bottom of the description,
        # where Shorts reads them, instead of eating the 100-character title.
        if len(title) > 100:
            title = title[:97].rsplit(" ", 1)[0].rstrip() + "..."

        description = self.generate_description(
            title, base_topic, keywords, trend_data, script=script, music_credit=music_credit,
        )

        tags = self.generate_tags(keywords, base_topic)
        hashtags = self.generate_hashtags(keywords, base_topic)
        
        return {
            "title": title,
            "description": description,
            "tags": tags,
            "hashtags": hashtags,
            "category_id": "22",  # People & Blogs (can be customized)
            "privacy_status": "public"  # Default to public for YouTube Shorts
        }

