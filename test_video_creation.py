#!/usr/bin/env python3
"""
Test script to test video creation without uploading.
"""
import sys
import os
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from youtube_uploader import YouTubeUploader
from trends_fetcher import TrendsFetcher
from video_generator import VideoGenerator
from content_optimizer import ContentOptimizer

def test_video_creation():
    """Test video creation workflow without uploading."""
    logger.info("="*60)
    logger.info("TESTING VIDEO CREATION (NO UPLOAD)")
    logger.info("="*60)
    
    try:
        # Initialize components
        logger.info("\n1. Initializing components...")
        youtube_uploader = YouTubeUploader()
        trends_fetcher = TrendsFetcher(youtube_service=youtube_uploader.youtube_service)
        video_generator = VideoGenerator(youtube_service=youtube_uploader.youtube_service)
        content_optimizer = ContentOptimizer()
        logger.info("✓ All components initialized")
        
        # Fetch Roblox trending topic
        logger.info("\n2. Fetching Roblox trending topic...")
        trend_data = trends_fetcher.get_trending_topic_for_video(region="US", roblox_only=True)
        
        if not trend_data:
            logger.error("Failed to fetch Roblox trending topic")
            return False
        
        topic_title = trend_data.get('title', 'N/A')
        logger.info(f"✓ Found topic: {topic_title}")
        logger.info(f"  Keywords: {', '.join(trend_data.get('keywords', [])[:5])}")
        
        # Generate script
        logger.info("\n3. Generating script...")
        script = video_generator._generate_script_from_trend(trend_data)
        logger.info(f"✓ Script generated: {len(script)} characters")
        logger.info(f"  Preview: {script[:200]}...")
        
        # Create output directory
        output_dir = "generated_videos"
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_filename = f"test_video_{timestamp}.mp4"
        video_path = os.path.join(output_dir, video_filename)
        
        # Generate video (this will actually create it with HeyGen)
        logger.info("\n4. Creating video with HeyGen...")
        logger.info("="*60)
        logger.info("NOTE: This will use HeyGen API credits!")
        logger.info("="*60)
        
        result_path = video_generator.generate_video_from_trend(
            trend_data,
            script=script,
            output_path=video_path
        )
        
        if result_path:
            logger.info("\n" + "="*60)
            logger.info("✓ VIDEO CREATION SUCCESSFUL!")
            logger.info("="*60)
            logger.info(f"Video saved to: {result_path}")
            logger.info(f"File size: {os.path.getsize(result_path) / 1024 / 1024:.2f} MB")
            logger.info("\nNote: Video was NOT uploaded (test mode)")
            return True
        else:
            logger.error("\n" + "="*60)
            logger.error("✗ VIDEO CREATION FAILED")
            logger.error("="*60)
            return False
            
    except Exception as e:
        logger.error(f"\nError during test: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_video_creation()
    sys.exit(0 if success else 1)

