#!/usr/bin/env python3
"""
Test script for adding captions to videos using Whisper + MoviePy.
Tests the captioning functionality before integrating into main flow.
"""
import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_captions_to_video(video_path: str, output_path: str = None, script_text: str = None) -> str:
    """
    Add captions to video using Whisper timestamps + MoviePy styling.
    
    Args:
        video_path: Path to input video
        script_text: Optional script text to help Whisper (if available)
        output_path: Path to save captioned video (if None, uses attempt.mp4)
    
    Returns:
        Path to captioned video
    """
    try:
        import whisper
        try:
            from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
        except ImportError:
            # Try alternative import path
            from moviepy import VideoFileClip, TextClip, CompositeVideoClip
        import subprocess
        
        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=5)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            logger.error("ffmpeg not found - required for captioning")
            raise
        
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        if not output_path:
            output_dir = os.path.dirname(video_path) or "generated_videos"
            output_path = os.path.join(output_dir, "attempt.mp4")
        
        logger.info(f"Input video: {video_path}")
        logger.info(f"Output video: {output_path}")
        
        # Step 1: Extract timestamps with Whisper
        logger.info("="*60)
        logger.info("Step 1: Extracting timestamps with Whisper...")
        logger.info("="*60)
        
        logger.info("Loading Whisper model (base)...")
        # Handle SSL certificate issues for model download
        import ssl
        import certifi
        
        # Try to use certifi certificates
        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        except:
            # Fallback: disable SSL verification (for testing only)
            logger.warning("SSL certificate issue detected, using unverified context (testing only)")
            ssl_context = ssl._create_unverified_context()
        
        # Set SSL context for urllib
        import urllib.request
        original_ssl = ssl._create_default_https_context
        ssl._create_default_https_context = lambda: ssl_context
        
        try:
            model = whisper.load_model("base")  # Fast, good enough for timing
        finally:
            # Restore original SSL context
            ssl._create_default_https_context = original_ssl
        
        logger.info("Transcribing audio (this may take a minute)...")
        transcribe_options = {
            "word_timestamps": True,
            "verbose": False,
        }
        
        # If we have script text, use it to help Whisper
        if script_text:
            transcribe_options["initial_prompt"] = script_text[:200]  # First 200 chars
            logger.info("Using provided script text to help Whisper")
        
        result = model.transcribe(video_path, **transcribe_options)
        
        segments = result["segments"]
        logger.info(f"✓ Got {len(segments)} caption segments")
        
        if not segments:
            raise ValueError("No segments found in transcription")
        
        # Log first few segments for debugging
        logger.info("Sample segments:")
        for i, seg in enumerate(segments[:3]):
            logger.info(f"  [{seg['start']:.2f}s - {seg['end']:.2f}s]: {seg['text'][:50]}")
        
        # Step 2: Load video with MoviePy
        logger.info("="*60)
        logger.info("Step 2: Loading video with MoviePy...")
        logger.info("="*60)
        
        video = VideoFileClip(video_path)
        logger.info(f"Video duration: {video.duration:.2f}s")
        logger.info(f"Video size: {video.w}x{video.h}")
        logger.info(f"Video fps: {video.fps}")
        
        # Step 3: Create text clips
        logger.info("="*60)
        logger.info("Step 3: Creating styled text clips...")
        logger.info("="*60)
        
        text_clips = []
        for i, seg in enumerate(segments):
            text = seg["text"].strip()
            start_time = seg["start"]
            end_time = seg["end"]
            duration = end_time - start_time
            
            if not text or duration <= 0:
                continue
            
            # Style for YouTube Shorts (bottom center, readable)
            # Use 90% width to avoid edges, auto height
            # MoviePy 2.x API - text must be a keyword argument
            try:
                # Try MoviePy 2.x style with text as keyword
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
            except (TypeError, ValueError) as e1:
                try:
                    # Fallback: try without method='caption'
                    txt_clip = TextClip(
                        text=text,
                        font_size=48,
                        color='white',
                        stroke_color='black',
                        stroke_width=3,
                        size=(int(video.w * 0.9), None),
                        text_align='center'
                    )
                except (TypeError, ValueError) as e2:
                    # Last resort: minimal parameters
                    txt_clip = TextClip(
                        text=text,
                        font_size=48,
                        color='white',
                        size=(int(video.w * 0.9), None)
                    )
            
            # MoviePy 2.x uses with_position instead of set_position
            # Position captions in the middle of the screen
            try:
                txt_clip = txt_clip.with_position(('center', 'center')) \
                                   .with_start(start_time) \
                                   .with_duration(duration)
            except AttributeError:
                # Fallback to old API
                txt_clip = txt_clip.set_position(('center', 'center')) \
                                   .set_start(start_time) \
                                   .set_duration(duration)
            
            text_clips.append(txt_clip)
            
            if (i + 1) % 10 == 0:
                logger.info(f"  Created {i + 1}/{len(segments)} text clips...")
        
        logger.info(f"✓ Created {len(text_clips)} text clips")
        
        # Step 4: Composite video + captions
        logger.info("="*60)
        logger.info("Step 4: Compositing video with captions...")
        logger.info("="*60)
        
        final = CompositeVideoClip([video] + text_clips)
        
        # Step 5: Write output
        logger.info("="*60)
        logger.info("Step 5: Rendering captioned video...")
        logger.info("="*60)
        logger.info(f"Output: {output_path}")
        logger.info("This may take a minute...")
        
        final.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            fps=video.fps,
            preset='medium',  # Balance speed/quality
            threads=4,
            logger=None  # Suppress MoviePy's verbose logging
        )
        
        # Cleanup
        video.close()
        final.close()
        
        logger.info("="*60)
        logger.info("✓ SUCCESS! Captioned video saved")
        logger.info(f"  File: {output_path}")
        logger.info(f"  Size: {os.path.getsize(output_path) / 1024 / 1024:.2f} MB")
        logger.info("="*60)
        
        return output_path
        
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Install with: pip install openai-whisper moviepy")
        raise
    except Exception as e:
        logger.error(f"Captioning failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        raise


def main():
    """Test captioning on an existing video."""
    # Find a recent video to test with
    generated_videos_dir = Path("generated_videos")
    
    if not generated_videos_dir.exists():
        logger.error("generated_videos directory not found")
        sys.exit(1)
    
    # Get most recent video
    video_files = sorted(
        generated_videos_dir.glob("video_*.mp4"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if not video_files:
        logger.error("No video files found in generated_videos/")
        sys.exit(1)
    
    test_video = str(video_files[0])
    logger.info(f"Testing with: {test_video}")
    
    # Try to find script text from metadata (if available)
    script_text = None
    video_name = Path(test_video).stem
    metadata_file = generated_videos_dir / f"{video_name}_metadata.json"
    
    if metadata_file.exists():
        try:
            import json
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                script_text = metadata.get('script') or metadata.get('script_text')
                if script_text:
                    logger.info("Found script text in metadata")
        except:
            pass
    
    # Run captioning
    try:
        output_path = add_captions_to_video(
            test_video,
            output_path=str(generated_videos_dir / "attempt.mp4"),
            script_text=script_text
        )
        logger.info(f"\n✓ Test completed successfully!")
        logger.info(f"Check the result: {output_path}")
    except Exception as e:
        logger.error(f"\n✗ Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

