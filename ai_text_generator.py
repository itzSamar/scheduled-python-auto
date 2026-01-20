"""
AI Text Generation using Hugging Face Inference API.
Generates YouTube-optimized titles, descriptions, and scripts.
"""
import requests
import logging
from typing import Dict, Optional
from config import HF_API_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hugging Face Inference API
HF_API_BASE_URL = "https://api-inference.huggingface.co/models"
HF_HEADERS = {
    "Authorization": f"Bearer {HF_API_KEY}",
    "Content-Type": "application/json"
}

# Free text generation models to try
TEXT_GENERATION_MODELS = [
    "microsoft/DialoGPT-medium",  # Conversational
    "gpt2",  # Basic text generation
    "distilgpt2",  # Faster GPT-2
    "google/flan-t5-base",  # Instruction following
]


def generate_text_with_hf(prompt: str, model: str = None, max_length: int = 200) -> Optional[str]:
    """
    Generate text using Hugging Face Inference API.
    
    Args:
        prompt: Input prompt for text generation
        model: Model to use (will try multiple if None)
        max_length: Maximum length of generated text
        
    Returns:
        Generated text or None if failed
    """
    models_to_try = [model] if model else TEXT_GENERATION_MODELS
    
    for model_name in models_to_try:
        try:
            url = f"{HF_API_BASE_URL}/{model_name}"
            
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_length": max_length,
                    "temperature": 0.7,
                    "do_sample": True
                }
            }
            
            response = requests.post(url, json=payload, headers=HF_HEADERS, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                # Handle different response formats
                if isinstance(result, list) and len(result) > 0:
                    generated_text = result[0].get("generated_text", "")
                elif isinstance(result, dict):
                    generated_text = result.get("generated_text", "") or result.get("text", "")
                else:
                    generated_text = str(result)
                
                if generated_text:
                    # Remove the original prompt if it's included
                    if prompt in generated_text:
                        generated_text = generated_text.replace(prompt, "").strip()
                    return generated_text.strip()
            elif response.status_code == 503:
                # Model is loading, try next
                logger.debug(f"Model {model_name} is loading, trying next...")
                continue
            else:
                logger.debug(f"Model {model_name} failed: {response.status_code}")
                continue
                
        except Exception as e:
            logger.debug(f"Error with model {model_name}: {e}")
            continue
    
    return None


def generate_youtube_title(topic: str, keywords: list = None) -> str:
    """
    Generate a YouTube-optimized title using AI that matches the actual content.
    
    Args:
        topic: Main topic of the video (e.g., "G Herbo - 1 Chance")
        keywords: List of trending keywords
        
    Returns:
        Optimized YouTube title that matches the topic
    """
    keywords_str = ", ".join(keywords[:5]) if keywords else ""
    
    # Extract the main subject from topic intelligently
    # If topic is "G Herbo - 1 Chance", use "G Herbo" not just "G"
    if '-' in topic:
        # Split on dash and take first part
        main_subject = topic.split('-')[0].strip()
    elif '(' in topic:
        # Split on parenthesis and take first part
        main_subject = topic.split('(')[0].strip()
    else:
        # For topics without separators, use FULL topic if reasonable (6 words or less)
        topic_words = topic.split()
        if len(topic_words) <= 6:
            main_subject = topic  # Use full topic
        else:
            # Only truncate if really long - take first 5 words max
            main_subject = ' '.join(topic_words[:5])
    
    # Use the full extracted subject (don't truncate further unless absolutely necessary)
    main_subject_clean = main_subject
    
    prompt = f"""Generate a catchy YouTube Shorts title (under 60 characters) specifically about: {topic}

CRITICAL RULES:
1. The title MUST mention "{main_subject_clean}" or key words from "{topic}"
2. Do NOT include random keywords like "{keywords_str.split(',')[0] if keywords_str else ''}" unless they're directly related to the topic
3. Keep it focused ONLY on the topic itself
4. Make it catchy and engaging

Examples:
- Topic: "G Herbo - 1 Chance" → Good: "G Herbo's New Track is FIRE!" or "G Herbo Drops 1 Chance" → Bad: "Why Music is Trending" or "G Herbo Doomsday" (doomsday not related)
- Topic: "Marvel Trailer" → Good: "Marvel Just Dropped This!" → Bad: "Trailers You Need to See" (too generic)

Topic: {topic}
Main subject: {main_subject_clean}
Keywords (DO NOT USE THESE unless directly related to topic): {keywords_str}

Title (under 60 chars, MUST mention "{main_subject_clean}", NO random keywords):"""
    
    generated = generate_text_with_hf(prompt, max_length=100)
    
    if generated:
        # Clean and format the title
        title = generated.strip().strip('"').strip("'")
        # Take first line if multiple lines
        title = title.split('\n')[0].strip()
        # Remove any "Title:" prefix
        if title.lower().startswith('title:'):
            title = title[6:].strip()
        # Limit to 60 characters
        if len(title) > 60:
            title = title[:57] + "..."
        
        # STRICT check: Ensure title mentions the main subject
        title_lower = title.lower()
        main_words = [w.lower() for w in main_subject_clean.split() if len(w) > 1]
        topic_key_words = [w.lower() for w in topic.split() if len(w) > 2 and w.lower() not in ['official', 'music', 'video']]
        
        # Check if title contains main subject words or key topic words
        matches_main = any(word in title_lower for word in main_words)
        matches_topic = any(word in title_lower for word in topic_key_words[:3])
        
        if not (matches_main or matches_topic):
            # Title doesn't match topic, use fallback that ensures match
            from content_optimizer import ContentOptimizer
            optimizer = ContentOptimizer()
            fallback_title = optimizer.generate_title(topic, keywords)
            # Ensure fallback also matches
            fallback_lower = fallback_title.lower()
            if not (any(word in fallback_lower for word in main_words) or any(word in fallback_lower for word in topic_key_words[:3])):
                # Even fallback doesn't match, create simple title with main subject
                return f"{main_subject_clean} - You Need to See This!"
            return fallback_title
        
        return title
    
    # Fallback to template-based generation
    from content_optimizer import ContentOptimizer
    optimizer = ContentOptimizer()
    fallback_title = optimizer.generate_title(topic, keywords)
    # Verify fallback matches topic
    title_lower = fallback_title.lower()
    main_words = [w.lower() for w in main_subject_clean.split() if len(w) > 1]
    if not any(word in title_lower for word in main_words):
        return f"{main_subject_clean} - You Need to See This!"
    return fallback_title


def generate_youtube_description(topic: str, title: str, keywords: list = None) -> str:
    """
    Generate a YouTube-optimized description using AI.
    
    Args:
        topic: Main topic of the video
        title: Video title
        keywords: List of trending keywords
        
    Returns:
        Optimized YouTube description
    """
    keywords_str = ", ".join(keywords[:10]) if keywords else ""
    
    prompt = f"""Write a YouTube Shorts video description (under 500 characters) for:
Title: {title}
Topic: {topic}
Keywords: {keywords_str}

Include:
- Engaging hook
- Brief explanation
- Call to action (like/subscribe)
- Relevant hashtags (3-5)
- Emojis for engagement

Description:"""
    
    generated = generate_text_with_hf(prompt, max_length=600)
    
    if generated:
        # Clean the description
        desc = generated.strip()
        # Remove quotes if wrapped
        if desc.startswith('"') and desc.endswith('"'):
            desc = desc[1:-1]
        if desc.startswith("'") and desc.endswith("'"):
            desc = desc[1:-1]
        # Limit to 500 characters
        if len(desc) > 500:
            desc = desc[:497] + "..."
        return desc
    
    # Fallback to template-based generation
    from content_optimizer import ContentOptimizer
    optimizer = ContentOptimizer()
    return optimizer.generate_description(title, topic, keywords)


def generate_content_script(topic: str, description: str = "", keywords: list = None) -> str:
    """
    Generate a YouTube-friendly script that actually discusses the content,
    not just reads the title. Creates meaningful discussion about the topic.
    
    Args:
        topic: Main topic/title
        description: Video description (if available)
        keywords: List of keywords
        
    Returns:
        YouTube-friendly script discussing the content
    """
    keywords_str = ", ".join(keywords[:5]) if keywords else ""
    
    # Clean description - remove URLs, links, and formatting
    import re
    if description:
        desc_preview = description[:400]
        # Remove URLs and links
        desc_preview = re.sub(r'http\S+|www\.\S+|https?://\S+', '', desc_preview)
        # Remove markdown formatting
        desc_preview = desc_preview.replace('\n', ' ').replace('#', '').replace('*', '')
        # Remove extra whitespace
        desc_preview = ' '.join(desc_preview.split())
    else:
        desc_preview = ""
    
    # Extract main subject from topic (e.g., "G Herbo" from "G Herbo - 1 Chance")
    main_subject = topic.split('-')[0].strip() if '-' in topic else topic.split('(')[0].strip()
    
    # YouTube hooks to use
    hooks = [
        "STOP SCROLLING!",
        "WAIT, you need to see this!",
        "HOLD UP!",
        "YO, check this out!",
        "BRO, you're missing out!",
        "LISTEN UP!",
        "PAUSE! This is important!"
    ]
    import random
    hook = random.choice(hooks)
    
    prompt = f"""Create a 20-second YouTube Shorts script (approximately 50 words MAX) that DEEPLY DISCUSSES and analyzes the content about "{main_subject}" or "{topic}":

Topic: {topic}
Main subject: {main_subject}
Description: {desc_preview}
Keywords: {keywords_str}

CRITICAL REQUIREMENTS:
- Start with a catchy YouTube hook like "{hook}" (use this exact hook or similar)
- The script MUST be specifically about "{main_subject}" or "{topic}" - same topic as the video title
- DON'T just scrape the surface - DIG DEEP! Talk about:
  * What makes it cool/interesting/special
  * Why people are obsessed with it
  * What's unique about it
  * Behind-the-scenes details or interesting facts
  * What's making it go viral
  * Why it matters or why it's trending
- Remove any URLs, links, or website references
- Be detailed and specific - give real insights
- Make it engaging and exciting
- End with a strong call to action
- Sound like a real YouTube creator who knows their stuff

Example GOOD script for "G Herbo - 1 Chance":
"{hook} G Herbo just dropped '1 Chance' and it's absolutely INSANE! The music video has these mind-blowing visuals that everyone's talking about - the cinematography is next level. Plus the beat is so catchy it's been stuck in my head all day. This is why it hit millions of views in just hours! The energy is unmatched. Drop a like if you're feeling this!"

Example BAD script (too surface level):
"Hey everyone! G Herbo dropped a new song. It's trending. Check it out."

Script that DEEPLY discusses the content (no links, same topic as title, use hook):"""
    
    generated = generate_text_with_hf(prompt, max_length=250)
    
    if generated:
        script = generated.strip()
        # Remove quotes if wrapped
        if script.startswith('"') and script.endswith('"'):
            script = script[1:-1]
        if script.startswith("'") and script.endswith("'"):
            script = script[1:-1]
        
        # Remove URLs/links (double check)
        script = re.sub(r'http\S+|www\.\S+|https?://\S+', '', script)
        script = re.sub(r'\S+\.com|\S+\.net|\S+\.org', '', script)
        
        # Ensure it's under 50 words (strict limit for 20 seconds - prevent scrolling)
        words = script.split()
        if len(words) > 50:
            # Trim to 45 words and add conclusion
            script = " ".join(words[:45])
            script += " Drop a like!"
        
        return script.strip()
    
    # Fallback: Create deep content discussion script (no links)
    import random
    hooks = ["STOP SCROLLING!", "WAIT, you need to see this!", "HOLD UP!", "YO, check this out!"]
    hook = random.choice(hooks)
    
    if desc_preview:
        # Use description to discuss actual content deeply
        desc_clean = desc_preview[:300]
        # Remove URLs again
        desc_clean = re.sub(r'http\S+|www\.\S+|https?://\S+', '', desc_clean)
        desc_clean = ' '.join(desc_clean.split())
        # Add depth and excitement
        return f"{hook} {main_subject} just dropped something INSANE and it's absolutely blowing up! {desc_clean} The visuals are mind-blowing, the energy is unmatched, and this is why everyone's obsessed with it right now! This is next level content! Drop a like if you're feeling this!"
    elif keywords:
        # Discuss deeply based on keywords but keep focus on main subject
        main_keywords = keywords[:2]  # Use fewer keywords, focus on depth
        return f"{hook} {main_subject} is absolutely FIRE right now! The {main_keywords[0] if main_keywords else 'content'} is insane and everyone's talking about it because it's so unique and captivating. This is why it's going viral everywhere - you need to check this out! Drop a like if you want more!"
    else:
        return f"{hook} {main_subject} is absolutely trending and here's why it's SO COOL! This is next level content that's blowing up everywhere because it's unique, exciting, and absolutely captivating. You need to see this! Drop a like if you're feeling this!"


def optimize_script_for_20_seconds(script: str, topic: str) -> str:
    """
    Optimize script to be exactly 20 seconds or less using AI.
    Makes it YouTube-friendly and natural like actual YouTube content.
    Average speaking rate is ~150 words per minute = 2.5 words per second.
    20 seconds = ~50 words maximum (prevents scrolling).
    
    Args:
        script: Original script
        topic: Main topic
        
    Returns:
        Optimized 20-second YouTube-friendly script (max 50 words)
    """
    # Get current year for context
    from datetime import datetime
    current_year = datetime.now().year
    
    prompt = f"""Rewrite this script to be exactly 20 seconds when spoken (approximately 50 words maximum) for a YouTube Shorts video:
Topic: {topic}
Original script: {script}
Current year: {current_year}

CRITICAL: Keep it SHORT - 20 seconds MAX to prevent viewers from scrolling away!

Make it:
- Sound like a real YouTube creator (natural, energetic, engaging)
- Start with a HOOK that grabs attention in first 2 seconds (don't let them scroll!)
- Use YouTube-friendly phrases like "STOP SCROLLING!", "WAIT!", "YO CHECK THIS!"
- SUPER CONCISE - get to the point immediately
- End with a strong call to action (like, subscribe)
- Keep it conversational and authentic
- Optimize for engagement and retention (prevent scrolling)
- VERY punchy and fast-paced
- Reference current year ({current_year}) if mentioning dates/years

20-second YouTube-friendly script (50 words MAX - prevent scrolling):"""
    
    generated = generate_text_with_hf(prompt, max_length=150)
    
    if generated:
        # Clean the script
        optimized = generated.strip()
        # Remove quotes if wrapped
        if optimized.startswith('"') and optimized.endswith('"'):
            optimized = optimized[1:-1]
        if optimized.startswith("'") and optimized.endswith("'"):
            optimized = optimized[1:-1]
        
        # Count words and ensure it's under 50 words (strict 20-second limit)
        words = optimized.split()
        if len(words) > 50:
            # Truncate to 45 words max and add quick conclusion
            truncated = " ".join(words[:45])
            optimized = f"{truncated} Drop a like!"
        
        # Final strict check - ensure exactly 50 or less
        final_words = optimized.split()
        if len(final_words) > 50:
            optimized = " ".join(final_words[:50])
        
        return optimized.strip()
    
    # Fallback: Manual optimization - STRICT 50 word limit
    words = script.split()
    if len(words) > 50:
        # Take first 45 words and add quick conclusion
        truncated = " ".join(words[:45])
        return f"{truncated} Drop a like!"
    
    return script

