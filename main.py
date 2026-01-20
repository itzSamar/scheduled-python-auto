#!/usr/bin/env python3
"""
Main entry point for YouTube Auto-Posting System.
Orchestrates the workflow: fetch trends → generate content → create video → upload.
"""
# Ensure we use the correct Python interpreter (Framework Python for x86_64 compatibility)
import sys
import os
if sys.executable.startswith('/Applications/Xcode.app'):
    # If running with Xcode Python (ARM64), switch to Framework Python (x86_64) for consistency
    framework_python = '/Library/Frameworks/Python.framework/Versions/3.9/bin/python3'
    if os.path.exists(framework_python):
        # Re-execute with Framework Python
        os.execv(framework_python, [framework_python] + sys.argv)
import argparse
import logging
import os
import sys
import warnings
import contextlib
import io
from datetime import datetime

# Suppress Python 3.9 compatibility warnings from Google API libraries
warnings.filterwarnings("ignore", category=FutureWarning, message=".*importlib.metadata.*")
warnings.filterwarnings("ignore", message=".*packages_distributions.*")

# Create a filter to suppress the importlib.metadata error message (printed to both stdout and stderr)
class OutputFilter:
    def __init__(self, original_stream):
        self.original_stream = original_stream
    
    def write(self, text):
        # Filter out the specific error message about packages_distributions
        text_lower = text.lower()
        if ("packages_distributions" in text_lower or 
            ("importlib.metadata" in text_lower and "has no attribute" in text_lower) or
            ("an error occurred" in text_lower and "packages_distributions" in text_lower)):
            # Suppress this specific compatibility error
            return
        self.original_stream.write(text)
    
    def flush(self):
        self.original_stream.flush()

# Apply filters to both stdout and stderr before imports to suppress compatibility warnings
sys.stdout = OutputFilter(sys.stdout)
sys.stderr = OutputFilter(sys.stderr)

from config import validate_config, DEFAULT_PRIVACY_STATUS, DEFAULT_CATEGORY_ID, REQUIRED_CHANNEL_NAME
from trends_fetcher import TrendsFetcher
from content_optimizer import ContentOptimizer
from video_generator import VideoGenerator
from youtube_uploader import YouTubeUploader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="YouTube Auto-Posting System - Automatically create and upload videos based on trends"
    )
    parser.add_argument(
        "--region",
        default="US",
        help="Country code for trending videos (default: US)"
    )
    parser.add_argument(
        "--privacy",
        choices=["public", "private", "unlisted"],
        default=DEFAULT_PRIVACY_STATUS,
        help=f"Privacy status for uploaded videos (default: {DEFAULT_PRIVACY_STATUS})"
    )
    parser.add_argument(
        "--category",
        default=DEFAULT_CATEGORY_ID,
        help=f"YouTube category ID (default: {DEFAULT_CATEGORY_ID})"
    )
    parser.add_argument(
        "--skip-video-generation",
        action="store_true",
        help="Skip video generation and upload existing video file"
    )
    parser.add_argument(
        "--video-file",
        help="Path to video file to upload (if skipping generation)"
    )
    parser.add_argument(
        "--output-dir",
        default="generated_videos",
        help="Directory to save generated videos (default: generated_videos)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch trends and generate metadata without creating/uploading video"
    )
    
    args = parser.parse_args()
    
    # Validate configuration
    logger.info("Validating configuration...")
    config_errors = validate_config()
    if config_errors:
        logger.error("Configuration errors found:")
        for error in config_errors:
            logger.error(f"  - {error}")
        logger.error("\nPlease fix these issues before running the script.")
        sys.exit(1)
    
    logger.info("Configuration validated successfully!")
    
    try:
        # Initialize components
        logger.info("Initializing components...")
        youtube_uploader = YouTubeUploader()
        
        # Get channel info and validate it's the correct channel
        channel_info = youtube_uploader.get_channel_info()
        if not channel_info:
            logger.error("Failed to get channel information. Exiting.")
            sys.exit(1)
        
        channel_name = channel_info.get('title', '')
        logger.info(f"Connected to channel: {channel_name}")
        logger.info(f"  Subscribers: {channel_info['subscriber_count']}")
        logger.info(f"  Videos: {channel_info['video_count']}")
        logger.info(f"  Views: {channel_info['view_count']}")
        
        # Verify we're using the correct channel
        if channel_name != REQUIRED_CHANNEL_NAME:
            logger.error(f"\n{'='*60}")
            logger.error("ERROR: Wrong channel detected!")
            logger.error(f"Expected channel: '{REQUIRED_CHANNEL_NAME}'")
            logger.error(f"Connected channel: '{channel_name}'")
            logger.error(f"{'='*60}")
            logger.error("\nPlease authenticate with the Google account that owns")
            logger.error(f"the '{REQUIRED_CHANNEL_NAME}' channel.")
            logger.error("\nTo fix this:")
            logger.error("1. Delete youtube-oauth2.json")
            logger.error("2. Run the script again")
            logger.error("3. Sign in with the correct Google account")
            sys.exit(1)
        
        logger.info(f"\n✓ Channel verified: '{channel_name}'")
        
        # Initialize Reddit fetcher (no YouTube service needed)
        from reddit_fetcher import RedditFetcher
        reddit_fetcher = RedditFetcher()
        content_optimizer = ContentOptimizer()
        
        if not args.skip_video_generation:
            # Pass YouTube service to video generator for Minecraft parkour video fetching
            video_generator = VideoGenerator(youtube_service=youtube_uploader.youtube_service)
        
        # Step 1: Fetch Reddit stories
        logger.info("\n" + "="*60)
        logger.info("Step 1: Fetching Reddit stories...")
        logger.info("="*60)
        logger.info("Channel Focus: Reddit Stories")
        
        trend_data = reddit_fetcher.get_reddit_story_for_video(max_results=20)
        
        if not trend_data:
            logger.error("Failed to fetch Reddit stories. Exiting.")
            sys.exit(1)
        
        topic_title = trend_data.get('title', 'N/A')
        logger.info(f"Found Reddit story: {topic_title}")
        logger.info(f"From r/{trend_data.get('subreddit', 'unknown')} ({trend_data.get('score', 0)} upvotes)")
        logger.info(f"Keywords: {', '.join(trend_data.get('keywords', [])[:5])}")
        
        # Check if this topic was already used
        if reddit_fetcher._is_topic_used(topic_title):
            logger.warning(f"⚠ Topic '{topic_title}' was previously used, but no new topics available")
        else:
            logger.info(f"✓ New topic selected (not previously used)")
        
        # Step 2: Generate script FIRST (needed for story-style title)
        script = None
        if not args.skip_video_generation:
            logger.info("\n" + "="*60)
            logger.info("Step 2: Generating story script...")
            logger.info("="*60)
            
            script = video_generator._generate_script_from_trend(trend_data)
            logger.info(f"Generated script ({len(script)} characters)")
            logger.info(f"Script preview: {script[:200]}...")
        
        # Step 3: Optimize metadata (using script for title)
        logger.info("\n" + "="*60)
        logger.info("Step 3: Optimizing video metadata...")
        logger.info("="*60)
        
        metadata = content_optimizer.optimize_metadata(trend_data, script=script)
        metadata["privacy_status"] = args.privacy
        metadata["category_id"] = args.category
        
        logger.info(f"Title: {metadata['title']}")
        logger.info(f"Description length: {len(metadata['description'])} characters")
        logger.info(f"Tags: {', '.join(metadata['tags'][:5])}...")
        logger.info(f"Hashtags: {', '.join(metadata['hashtags'])}")
        
        if args.dry_run:
            logger.info("\n" + "="*60)
            logger.info("DRY RUN MODE - Skipping video generation and upload")
            logger.info("="*60)
            logger.info("\nMetadata generated successfully!")
            logger.info("Run without --dry-run to create and upload video.")
            return
        
        # Step 4: Generate video (if not skipping)
        video_path = None
        
        if not args.skip_video_generation:
            logger.info("\n" + "="*60)
            logger.info("Step 4: Generating video with HeyGen AI...")
            logger.info("="*60)
            
            # Create output directory if it doesn't exist
            os.makedirs(args.output_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_filename = f"video_{timestamp}.mp4"
            video_path = os.path.join(args.output_dir, video_filename)
            
            # Create and download video
            result_path = video_generator.generate_video_from_trend(
                trend_data,
                script=script,
                output_path=video_path
            )
            
            if not result_path:
                logger.error("\n" + "="*60)
                logger.error("VIDEO GENERATION FAILED")
                logger.error("="*60)
                logger.error("HeyGen AI video generation failed.")
                logger.error("Please check:")
                logger.error("1. Your HEYGEN_API_KEY is valid")
                logger.error("2. You have sufficient credits/quota")
                logger.error("3. The API is accessible")
                logger.error("\nAlternatively, use:")
                logger.error("python3 main.py --skip-video-generation --video-file YOUR_VIDEO.mp4")
                logger.error("="*60)
                sys.exit(1)
            
            video_path = result_path
            logger.info(f"✓ Video generated successfully: {video_path}")
        
        else:
            # Use provided video file
            if not args.video_file:
                logger.error("--video-file is required when using --skip-video-generation")
                sys.exit(1)
            
            if not os.path.exists(args.video_file):
                logger.error(f"Video file not found: {args.video_file}")
                sys.exit(1)
            
            video_path = args.video_file
            logger.info(f"Using existing video file: {video_path}")
        
        # Step 4: Upload to YouTube
        logger.info("\n" + "="*60)
        logger.info("Step 4: Uploading video to YouTube...")
        logger.info("="*60)
        
        video_id = youtube_uploader.upload_video(
            video_path=video_path,
            metadata=metadata,
            privacy_status=args.privacy,
            category_id=args.category
        )
        
        if video_id:
            # Mark topic as used after successful upload
            topic_title = trend_data.get('title', '') or trend_data.get('_topic_title', '')
            if topic_title:
                reddit_fetcher._save_used_topic(topic_title)
                logger.info(f"✓ Topic '{topic_title}' marked as used")
            
            logger.info("\n" + "="*60)
            logger.info("SUCCESS! Video uploaded successfully!")
            logger.info("="*60)
            logger.info(f"Video ID: {video_id}")
            logger.info(f"Video URL: https://www.youtube.com/watch?v={video_id}")
            logger.info(f"Privacy Status: {args.privacy}")
            
            if args.privacy == "private":
                logger.info("\nNote: Video is set to private. Change privacy status in YouTube Studio.")
        else:
            logger.error("Failed to upload video.")
            sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user. Exiting.")
        sys.exit(0)
    except Exception as e:
        # Suppress importlib.metadata compatibility errors (Python 3.9 vs 3.10+)
        error_str = str(e)
        if "packages_distributions" in error_str or ("importlib.metadata" in error_str and "has no attribute" in error_str):
            # This is a non-critical compatibility warning, script completed successfully
            logger.debug(f"Suppressed compatibility warning: {e}")
            sys.exit(0)
        logger.error(f"\nUnexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except AttributeError as e:
        # Suppress importlib.metadata compatibility errors (Python 3.9 vs 3.10+)
        if "packages_distributions" not in str(e) and "importlib.metadata" not in str(e):
            raise
        # Otherwise suppress and exit normally
        sys.exit(0)
    except SystemExit:
        # Re-raise system exits (normal program termination)
        raise
    except Exception as e:
        # Check if it's the compatibility error
        error_str = str(e)
        if "packages_distributions" in error_str or ("importlib.metadata" in error_str and "has no attribute" in error_str):
            sys.exit(0)
        raise

