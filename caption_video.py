#!/usr/bin/env python3
"""
Standalone video captioning script.
Uses Whisper for transcription and MoviePy for video composition.
Can be called independently or from main.py.
"""
import sys
import os
import argparse
import logging
import subprocess

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if required dependencies are available."""
    missing = []
    
    # Check ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=5)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        missing.append("ffmpeg")
    
    # Check whisper
    try:
        import whisper
    except ImportError:
        missing.append("openai-whisper (pip install openai-whisper)")
    except Exception as e:
        error_msg = str(e).lower()
        if "incompatible architecture" in error_msg or ("dlopen" in error_msg and ("x86_64" in error_msg or "arm64" in error_msg)):
            missing.append("PyTorch architecture issue - try: pip uninstall torch && pip install torch")
        else:
            missing.append(f"whisper import error: {e}")
    
    # Check moviepy
    try:
        from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
    except ImportError:
        try:
            from moviepy import VideoFileClip, TextClip, CompositeVideoClip
        except ImportError:
            missing.append("moviepy (pip install moviepy)")
    
    return missing

def add_captions_to_video(video_path: str, script: str = None, output_path: str = None):
    """
    Add captions to video using Whisper timestamps + MoviePy styling.
    
    Args:
        video_path: Path to input video
        script: Optional script text to help Whisper
        output_path: Path to save captioned video (if None, creates _captioned version)
    
    Returns:
        Path to captioned video, or None if failed
    """
    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return None
    
    if not output_path:
        base, ext = os.path.splitext(video_path)
        output_path = f"{base}_captioned{ext}"
    
    logger.info(f"Adding captions to: {video_path}")
    logger.info(f"Output will be: {output_path}")
    
    # Import dependencies
    try:
        import whisper
    except ImportError as e:
        logger.error(f"Whisper not available: {e}")
        logger.error("Install with: pip install openai-whisper")
        return None
    except Exception as e:
        error_msg = str(e).lower()
        if "incompatible architecture" in error_msg or ("dlopen" in error_msg and ("x86_64" in error_msg or "arm64" in error_msg)):
            logger.error("PyTorch architecture mismatch detected")
            logger.error("This should have been fixed before calling this script.")
            logger.error("Manual fix required: pip uninstall torch && pip install torch")
            return None
        else:
            logger.error(f"Whisper import error: {e}")
            return None
    
    try:
        try:
            from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
        except ImportError:
            from moviepy import VideoFileClip, TextClip, CompositeVideoClip
        import ssl
        import certifi
    except ImportError as e:
        logger.error(f"MoviePy not available: {e}")
        logger.error("Install with: pip install moviepy certifi")
        return None
    
    try:
        # Step 1: Extract timestamps with Whisper
        logger.info("Extracting timestamps with Whisper...")
        
        # Handle SSL certificate issues
        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        except:
            ssl_context = ssl._create_unverified_context()
        
        import urllib.request
        original_ssl = ssl._create_default_https_context
        ssl._create_default_https_context = lambda: ssl_context
        
        try:
            model = whisper.load_model("base")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return None
        finally:
            ssl._create_default_https_context = original_ssl
        
        # Transcribe video
        result = model.transcribe(video_path, language="en", task="transcribe")
        segments = result.get("segments", [])
        
        if not segments:
            logger.warning("No segments found in transcription")
            return None
        
        logger.info(f"✓ Got {len(segments)} caption segments")
        
        # Step 2: Load video with MoviePy
        logger.info("Loading video with MoviePy...")
        video = VideoFileClip(video_path)
        video_duration = video.duration
        video_size = video.size
        
        logger.info(f"Video duration: {video_duration:.2f}s, size: {int(video_size[0])}x{int(video_size[1])}")
        
        # Step 3: Create text clips (max 5 words per segment)
        logger.info("Creating styled text clips (max 5 words per segment)...")
        text_clips = []
        
        for i, segment in enumerate(segments):
            start_time = float(segment["start"])
            end_time = float(segment["end"])
            text = segment["text"].strip()
            
            if not text:
                continue
            
            # Split text into chunks of max 5 words
            words = text.split()
            max_words_per_chunk = 5
            
            if len(words) <= max_words_per_chunk:
                # Single chunk, use original timing
                chunks = [(text, start_time, end_time)]
            else:
                # Split into multiple chunks
                chunks = []
                num_chunks = (len(words) + max_words_per_chunk - 1) // max_words_per_chunk
                time_per_chunk = (end_time - start_time) / num_chunks
                
                for chunk_idx in range(num_chunks):
                    chunk_start_idx = chunk_idx * max_words_per_chunk
                    chunk_end_idx = min(chunk_start_idx + max_words_per_chunk, len(words))
                    chunk_words = words[chunk_start_idx:chunk_end_idx]
                    chunk_text = " ".join(chunk_words)
                    
                    chunk_start_time = start_time + (chunk_idx * time_per_chunk)
                    chunk_end_time = start_time + ((chunk_idx + 1) * time_per_chunk)
                    
                    chunks.append((chunk_text, chunk_start_time, chunk_end_time))
            
            # Create text clip for each chunk
            for chunk_text, chunk_start_time, chunk_end_time in chunks:
                duration = chunk_end_time - chunk_start_time
                
                if duration <= 0:
                    continue
                
                # Create text clip with styling - ensure it fits within video bounds
                # Use method='caption' with explicit height constraint to prevent cutoff
                text_width = int(video_size[0] * 0.80)  # 80% width to leave safe margins
                max_text_height = int(video_size[1] * 0.25)  # Max 25% of video height for text
                
                try:
                    # Use method='caption' with explicit size to prevent text from being cut off
                    txt_clip = TextClip(
                        text=chunk_text,
                        font_size=48,
                        color='white',
                        stroke_color='black',
                        stroke_width=3,
                        method='caption',
                        size=(text_width, max_text_height),  # Constrain both width AND height
                        text_align='center'
                    )
                except (TypeError, ValueError):
                    try:
                        # Fallback without method='caption'
                        txt_clip = TextClip(
                            text=chunk_text,
                            font_size=48,
                            color='white',
                            stroke_color='black',
                            stroke_width=3,
                            size=(text_width, max_text_height),
                            text_align='center'
                        )
                    except (TypeError, ValueError):
                        # Final fallback - basic text clip
                        txt_clip = TextClip(
                            text=chunk_text,
                            font_size=48,
                            color='white',
                            size=(text_width, max_text_height)
                        )

                # Add padding so the stroke doesn't get clipped by the text clip's bounding box
                # (This is a common cause of "sliced" text in MoviePy TextClip)
                try:
                    txt_clip = txt_clip.with_margin(left=12, right=12, top=10, bottom=10, opacity=0)
                except Exception:
                    try:
                        txt_clip = txt_clip.margin(left=12, right=12, top=10, bottom=10, opacity=0)
                    except Exception:
                        pass
                
                # Position centered vertically and horizontally
                # MoviePy's 'center' positioning ensures text stays within bounds
                try:
                    txt_clip = txt_clip.with_position(('center', 'center')) \
                                       .with_start(chunk_start_time) \
                                       .with_duration(duration)
                except AttributeError:
                    txt_clip = txt_clip.set_position(('center', 'center')) \
                                       .set_start(chunk_start_time) \
                                       .set_duration(duration)
                
                text_clips.append(txt_clip)
            
            if (i + 1) % 5 == 0:
                logger.info(f"  Processed {i + 1}/{len(segments)} segments, created {len(text_clips)} text clips...")
        
        logger.info(f"✓ Created {len(text_clips)} text clips")
        
        # Step 4: Composite video with captions
        logger.info("Compositing video with captions...")
        try:
            final_video = CompositeVideoClip([video] + text_clips)
        except AttributeError:
            final_video = CompositeVideoClip([video] + text_clips)
        
        # Step 5: Render video
        logger.info("Rendering captioned video (this may take a minute)...")
        try:
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True
            )
        except Exception as e:
            logger.error(f"Failed to render video: {e}")
            return None
        
        # Cleanup
        video.close()
        final_video.close()
        for clip in text_clips:
            try:
                clip.close()
            except:
                pass
        
        logger.info(f"✓ Captioned video saved: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error during captioning: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Add captions to video using Whisper")
    parser.add_argument("video_path", help="Path to input video file")
    parser.add_argument("-o", "--output", help="Output path (default: input_captioned.mp4)")
    parser.add_argument("-s", "--script", help="Optional script text to help Whisper")
    parser.add_argument("--check-deps", action="store_true", help="Check dependencies and exit")
    
    args = parser.parse_args()
    
    if args.check_deps:
        missing = check_dependencies()
        if missing:
            logger.error("Missing dependencies:")
            for dep in missing:
                logger.error(f"  - {dep}")
            sys.exit(1)
        else:
            logger.info("✓ All dependencies available")
            sys.exit(0)
    
    try:
        result = add_captions_to_video(
            args.video_path,
            script=args.script,
            output_path=args.output
        )
        
        if result and os.path.exists(result):
            logger.info(f"SUCCESS: {result}")
            sys.exit(0)
        else:
            logger.error(f"FAILED: Captioning did not complete. Result: {result}")
            if args.output and os.path.exists(args.output):
                logger.info(f"Note: Output file exists at {args.output}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"FAILED: Exception during captioning: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()

