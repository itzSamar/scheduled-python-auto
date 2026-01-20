"""
Optimizes video metadata (titles, descriptions, hashtags) for maximum engagement.
Uses trending keywords and SEO best practices.
"""
import logging
from typing import Dict, List, Optional
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import AI text generator
try:
    from ai_text_generator import generate_youtube_title, generate_youtube_description
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logger.warning("AI text generator not available, using template-based generation")


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
            
            # Check if it's a bold hook statement (starts with "I")
            if first_sentence.startswith('I ') and len(first_sentence.split()) <= 15:
                # Use the hook directly as title
                title = first_sentence
                if not title.endswith('.'):
                    title += '.'
                # Ensure it's not too long
                if len(title) <= max_length:
                    logger.info(f"✓ Using bold hook statement as title: {title}")
                    return title
                else:
                    # Truncate if too long
                    words = title.split()
                    title = ' '.join(words[:12]) + '...'
                    if len(title) <= max_length:
                        logger.info(f"✓ Using truncated hook statement as title: {title}")
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
                           video_info: Dict = None) -> str:
        """
        Generate an optimized YouTube description.
        
        Args:
            title: Video title
            base_topic: Main topic
            keywords: List of keywords to include
            video_info: Additional video information
            
        Returns:
            Optimized description string
        """
        keywords = keywords or []
        video_info = video_info or {}
        
        description_parts = []
        
        # Opening hook with emoji
        description_parts.append(f"🎥 {title}\n")
        description_parts.append("\n")
        
        # ENGAGEMENT-FOCUSED description with questions
        import random
        question_templates = [
            f"Have you seen {base_topic} trending everywhere?",
            f"What do you think about {base_topic}?",
            f"Did you know {base_topic} is blowing up right now?",
            f"Are you following the {base_topic} trend?",
            f"What's your take on {base_topic}?"
        ]
        
        description_parts.append(f"{random.choice(question_templates)} In this video, we break down everything you need to know about {base_topic} and why it's going viral RIGHT NOW! 🔥\n")
        description_parts.append("\n")
        
        # Key points (if available)
        if video_info.get("trending_topics"):
            description_parts.append("📌 Topics Covered:\n")
            for topic in video_info.get("trending_topics", [])[:3]:
                description_parts.append(f"• {topic}\n")
            description_parts.append("\n")
        
        # STRONG CALL TO ACTION with engagement hooks
        description_parts.append("💬 COMMENT BELOW: What do you think about this? Drop your thoughts! 👇\n")
        description_parts.append("\n")
        description_parts.append("👍 LIKE if you agree! SUBSCRIBE for more viral content! 🔔\n")
        description_parts.append("\n")
        description_parts.append("🔥 SHARE this video if you found it interesting!\n")
        description_parts.append("\n")
        
        # Engagement questions
        engagement_questions = [
            "What's your opinion on this?",
            "Do you agree or disagree?",
            "Have you seen this trend before?",
            "What would you do in this situation?",
            "Who else thinks this is crazy?"
        ]
        description_parts.append(f"❓ {random.choice(engagement_questions)} Let me know in the comments! 💬\n")
        description_parts.append("\n")
        
        # Tags section (for SEO)
        if keywords:
            description_parts.append("🔖 Related Topics: ")
            description_parts.append(", ".join(keywords[:10]))
            description_parts.append("\n")
            description_parts.append("\n")
        
        # Additional engagement elements
        description_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        description_parts.append("📱 Follow for daily trending content! New videos every day! 🚀\n")
        description_parts.append("\n")
        description_parts.append("💡 Turn on notifications so you never miss a video! 🔔\n")
        
        description = "".join(description_parts)
        
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
        
        # Add base topic variations
        topic_words = base_topic.lower().split()
        tags.extend(topic_words)
        
        # Add keywords
        tags.extend([kw.lower() for kw in keywords[:10]])
        
        # Add common YouTube tags
        from datetime import datetime
        current_year = str(datetime.now().year)
        
        common_tags = [
            "trending",
            "viral",
            current_year,  # Dynamic year (2025)
            "latest",
            "news",
            "explained",
            "guide",
            "tips"
        ]
        tags.extend(common_tags)
        
        # Remove duplicates and clean
        tags = list(set([tag.strip() for tag in tags if tag and len(tag) > 2]))
        
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
    
    def optimize_metadata(self, trend_data: Dict, script: str = None) -> Dict[str, any]:
        """
        Generate complete optimized metadata for a video using AI.
        
        Args:
            trend_data: Dictionary with trend information from TrendsFetcher
            script: Optional script text to extract hook from for title
            
        Returns:
            Dictionary with optimized title, description, tags, and hashtags
        """
        base_topic = trend_data.get("title", "Trending Topic")
        keywords = trend_data.get("keywords", [])
        
        # Generate title using script hook if available, otherwise use templates
        title = self.generate_title(base_topic, keywords, script=script)
        
        # Use AI to generate description if available
        if AI_AVAILABLE:
            
            try:
                description = generate_youtube_description(base_topic, title, keywords)
                logger.info("✓ AI-generated description")
            except Exception as e:
                logger.warning(f"AI description generation failed: {e}, using template")
                description = self.generate_description(title, base_topic, keywords, trend_data)
        else:
            # Fallback to templates
            title = self.generate_title(base_topic, keywords, script=script)
        description = self.generate_description(title, base_topic, keywords, trend_data)
        
        tags = self.generate_tags(keywords, base_topic)
        hashtags = self.generate_hashtags(keywords, base_topic)
        
        # Add hashtags to description at the BOTTOM (algorithm prefers this placement)
        # Research shows hashtags at the end perform better than at the top
        if hashtags:
            hashtag_string = " ".join([f"#{h}" for h in hashtags])
            description = f"{description}\n\n{hashtag_string}"
        else:
            # Ensure #shorts is always present at the end
            description = f"{description}\n\n#shorts"
        
        return {
            "title": title,
            "description": description,
            "tags": tags,
            "hashtags": hashtags,
            "category_id": "22",  # People & Blogs (can be customized)
            "privacy_status": "public"  # Default to public for YouTube Shorts
        }

