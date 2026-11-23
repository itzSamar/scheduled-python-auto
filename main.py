#!/usr/bin/env python3
"""
One run of the channel: pick a story -> screenplay -> voices -> animation -> upload.

Story order: pre-written screenplays in screenplays/queue/ first, then Reddit posts triaged and written
by the local LLM writers' room (Ollama).
"""
# Ensure we use the correct Python interpreter (Framework Python for x86_64 compatibility)
import sys
import os
if sys.executable.startswith('/Applications/Xcode.app'):
    framework_python = '/Library/Frameworks/Python.framework/Versions/3.9/bin/python3'
    if os.path.exists(framework_python):
        os.execv(framework_python, [framework_python] + sys.argv)
import argparse
import logging
import warnings
from datetime import datetime
import json
from typing import Any, Dict, Iterator, List, Optional, Tuple

# Suppress Python 3.9 compatibility warnings from Google API libraries
warnings.filterwarnings("ignore", category=FutureWarning, message=".*importlib.metadata.*")
warnings.filterwarnings("ignore", message=".*packages_distributions.*")


class OutputFilter:
    """Drops the harmless importlib.metadata/packages_distributions noise printed by Google libraries on 3.9."""

    def __init__(self, original_stream):
        self.original_stream = original_stream

    def write(self, text):
        text_lower = text.lower()
        if ("packages_distributions" in text_lower or
            ("importlib.metadata" in text_lower and "has no attribute" in text_lower) or
            ("an error occurred" in text_lower and "packages_distributions" in text_lower)):
            return
        self.original_stream.write(text)

    def flush(self):
        self.original_stream.flush()


sys.stdout = OutputFilter(sys.stdout)
sys.stderr = OutputFilter(sys.stderr)

from pipeline import screenplay_queue
from pipeline.auto_optimizer import auto_optimize_generator_config
from pipeline.config import (
    DEFAULT_CATEGORY_ID,
    DEFAULT_PRIVACY_STATUS,
    GENERATOR_CONFIG_PATH,
    HISTORY_DB_PATH,
    OUTPUT_DIR,
    REQUIRED_CHANNEL_NAME,
    SCREENPLAY_QUEUE_DIR,
    validate_config,
)
from pipeline.content_optimizer import ContentOptimizer
from pipeline.music_mixer import attribution, pick_track
from pipeline.history_db import HistoryDB
from pipeline.reddit_fetcher import RedditFetcher
from pipeline.safety_filter import evaluate_safety
from pipeline.trend_analyzer import render_trend_report
from pipeline.video_generator import VideoGenerator
from pipeline.youtube_uploader import YouTubeUploader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _utc_now_iso():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sync_missing_stats(history: HistoryDB, youtube_uploader: YouTubeUploader, limit: int = 200) -> int:
    """
    Pull basic public stats (views/likes/comments) for logged videoIds and store in history.
    """
    missing = history.get_video_ids_missing_stats(limit=limit)
    if not missing:
        return 0
    ids = [vid for _, vid in missing]
    details = youtube_uploader.get_videos_details(ids)
    updated = 0
    for run_id, vid in missing:
        item = details.get(vid)
        if not item:
            continue
        stats = item.get("statistics") or {}
        snippet = item.get("snippet") or {}
        content = item.get("contentDetails") or {}
        history.update_run(
            run_id,
            stats={
                "viewCount": stats.get("viewCount"),
                "likeCount": stats.get("likeCount"),
                "commentCount": stats.get("commentCount"),
                "favoriteCount": stats.get("favoriteCount"),
                "publishedAt": snippet.get("publishedAt"),
                "channelTitle": snippet.get("channelTitle"),
                "duration": content.get("duration"),
            },
            stats_fetched_at=_utc_now_iso(),
        )
        updated += 1
    return updated


def _load_generator_config(path: str = GENERATOR_CONFIG_PATH) -> Dict[str, Any]:
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _generator_weights_snapshot(cfg: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """
    Returns {experiment_name: {variant_id: weight}}
    """
    out: Dict[str, Dict[str, float]] = {}
    exps = cfg.get("experiments") or {}
    if not isinstance(exps, dict):
        return out
    for exp_name, exp_def in exps.items():
        if not isinstance(exp_def, dict):
            continue
        variants = exp_def.get("variants") or []
        if not isinstance(variants, list):
            continue
        weights: Dict[str, float] = {}
        for v in variants:
            if not isinstance(v, dict):
                continue
            vid = v.get("id")
            if not vid:
                continue
            try:
                weights[str(vid)] = float(v.get("weight", 0.0))
            except Exception:
                weights[str(vid)] = 0.0
        if weights:
            out[str(exp_name)] = weights
    return out


def _views_per_day_from_stats(stats: Dict[str, Any]) -> Optional[float]:
    from datetime import timezone, datetime as dt

    try:
        view_count = stats.get("viewCount")
        published_at = stats.get("publishedAt")
        if view_count is None or not published_at:
            return None
        views = int(view_count)
        published = dt.fromisoformat(str(published_at).replace("Z", "+00:00")).astimezone(timezone.utc)
        age_days = max(1.0, (dt.now(timezone.utc) - published).total_seconds() / 86400.0)
        return float(views) / age_days
    except Exception:
        return None


def _log_self_improvement_step(
    *,
    history: HistoryDB,
    youtube_uploader: Optional[YouTubeUploader],
    history_db_path: str,
    no_auto_optimize: bool,
) -> None:
    from datetime import timedelta, timezone, datetime as dt

    logger.info("\n" + "=" * 60)
    logger.info("Step 0: Self-improvement + analysis (auto)")
    logger.info("=" * 60)

    since_utc = (dt.now(timezone.utc) - timedelta(hours=24)).replace(microsecond=0).isoformat()
    uploads_24h = history.count_success_uploads_since(since_utc)
    logger.info(f"Uploads in last 24h (from history): {uploads_24h}")

    cfg_before = _load_generator_config()
    weights_before = _generator_weights_snapshot(cfg_before)
    if weights_before:
        logger.info(f"Current A/B weights: {weights_before}")
    else:
        logger.info("Current A/B weights: (none found) — using defaults")

    recent = history.get_recent_runs(limit=60)
    scored: List[Tuple[float, str]] = []
    for r in recent:
        if not r.stats_json:
            continue
        vpd = _views_per_day_from_stats(r.stats_json)  # type: ignore[arg-type]
        if vpd is None:
            continue
        scored.append((vpd, f"{r.title[:80]} ({r.run_id})"))
    scored.sort(key=lambda t: t[0], reverse=True)
    if scored:
        logger.info(f"Top recent (views/day): {scored[0][0]:.0f}/day — {scored[0][1]}")

    if no_auto_optimize:
        logger.info("Auto-optimize: disabled for this run (--no-auto-optimize)")
        return

    if not youtube_uploader:
        logger.info("Auto-optimize: YouTube disabled (--skip-upload), so no stats sync this run.")
        return

    try:
        synced = _sync_missing_stats(history, youtube_uploader, limit=60)
        if synced:
            logger.info(f"Synced missing YouTube stats for {synced} video(s).")
        changes = auto_optimize_generator_config(
            db_path=history_db_path,
            config_path=GENERATOR_CONFIG_PATH,
            min_samples_per_variant=2,
            lookback_runs=200,
        )
        if changes.get("updated"):
            updated_exps = [u.get("experiment") for u in (changes.get("updated") or []) if isinstance(u, dict)]
            logger.info(f"Auto-optimized experiments: {updated_exps}")
            weights_after = _generator_weights_snapshot(_load_generator_config())
            if weights_after and weights_after != weights_before:
                logger.info(f"New A/B weights: {weights_after}")
        else:
            logger.info("Auto-optimization: no weight changes yet (need more stats per variant).")
    except Exception as e:
        logger.warning(f"Self-improvement step failed (continuing): {e}")


def _trend_from_screenplay_file(path: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    src = doc.get("source") or {}
    sp = doc.get("screenplay", doc)
    title = src.get("title") or sp.get("title", "")
    return {
        "title": title,
        "description": (src.get("text") or "")[:1000],
        "text": src.get("text") or "",
        "keywords": [],
        "subreddit": src.get("subreddit") or doc.get("subreddit", ""),
        "score": src.get("score", 0) or 0,
        "num_comments": src.get("num_comments", 0) or 0,
        "url": src.get("url") or f"screenplay:{os.path.abspath(path)}",
        "_topic_title": title,
    }


def _story_sources(args, reddit_fetcher: RedditFetcher, video_generator) -> Iterator[Tuple[Dict[str, Any], Optional[Dict[str, Any]], Optional[str]]]:
    """Yields (trend_data, prewritten screenplay or None, queue file path or None) in the order to try them."""
    if args.story_url:
        trend = reddit_fetcher.fetch_story_by_url(args.story_url)
        if trend:
            yield trend, None, None
        return
    if args.screenplay:
        with open(args.screenplay, "r", encoding="utf-8") as f:
            doc = json.load(f)
        sp_path = os.path.abspath(args.screenplay)
        in_queue = os.path.dirname(sp_path) == os.path.abspath(SCREENPLAY_QUEUE_DIR)
        yield _trend_from_screenplay_file(args.screenplay, doc), doc.get("screenplay", doc), sp_path if in_queue else None
        return

    used = reddit_fetcher._load_used_topics() | reddit_fetcher._load_rejected_topics()
    queued = screenplay_queue.entries(skip_titles=used)
    if queued:
        logger.info(f"{len(queued)} pre-written screenplay(s) in the queue")
    for q in queued:
        yield q.trend_data, q.screenplay, q.path

    if not video_generator.writer_ready():
        logger.error(f"Queue is empty and the Ollama writer isn't available "
                     f"(start Ollama and run `ollama pull {video_generator.llm.model}`).")
        return
    candidates = reddit_fetcher.get_story_candidates(max_results=20, limit=8)
    logger.info(f"Triaging {len(candidates)} Reddit candidates with the writers' room...")
    for trend in video_generator.rank_stories(candidates):
        yield trend, None, None


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Animated Reddit Stories - pick a story, animate it and upload it to YouTube"
    )
    parser.add_argument("--region", default="US", help="Region tag stored in history (default: US)")
    parser.add_argument(
        "--privacy",
        choices=["public", "private", "unlisted"],
        default=DEFAULT_PRIVACY_STATUS,
        help=f"Privacy status for uploaded videos (default: {DEFAULT_PRIVACY_STATUS})"
    )
    parser.add_argument("--category", default=DEFAULT_CATEGORY_ID, help=f"YouTube category ID (default: {DEFAULT_CATEGORY_ID})")
    parser.add_argument("--skip-video-generation", action="store_true", help="Upload an existing video file instead of generating one")
    parser.add_argument("--video-file", help="Path to video file to upload (with --skip-video-generation)")
    parser.add_argument("--output-dir", default=OUTPUT_DIR, help="Directory to save generated videos")
    parser.add_argument("--dry-run", action="store_true", help="Pick a story and write metadata without rendering/uploading")
    parser.add_argument("--skip-upload", action="store_true", help="Generate the video but do NOT upload it (end-to-end testing)")
    parser.add_argument("--history-db", default=HISTORY_DB_PATH, help="SQLite DB path for per-video history")
    parser.add_argument("--analyze-trends", action="store_true", help="Analyze history (and optional stats) instead of generating a new video")
    parser.add_argument("--analysis-limit", type=int, default=50, help="How many recent runs to analyze (default: 50)")
    parser.add_argument("--sync-stats", action="store_true", help="When analyzing trends, sync missing YouTube stats into the history DB first")
    parser.add_argument("--ollama-model", default=None, help="Ollama model to use for --analyze-trends")
    parser.add_argument("--no-auto-optimize", action="store_true", help="Disable automatic self-improvement (A/B weights) for this run")
    parser.add_argument("--max-story-attempts", type=int, default=6, help="Max different stories to try before giving up (default: 6)")
    parser.add_argument("--story-url", default=None, help="Hand-pick a Reddit post URL instead of the queue/auto-selection")
    parser.add_argument("--screenplay", default=None, help="Use this screenplay JSON (raw or queue format) instead of writing one")
    parser.add_argument("--render-style", choices=["2d", "3d", "mixed"], default=None, help="Force the animation style instead of the A/B experiment")

    args = parser.parse_args()

    history = HistoryDB(db_path=args.history_db)
    if args.analyze_trends:
        if args.sync_stats:
            try:
                youtube_uploader = YouTubeUploader()
                updated = _sync_missing_stats(history, youtube_uploader, limit=500)
                logger.info(f"✓ Synced stats for {updated} video(s)")
            except Exception as e:
                logger.warning(f"Stats sync failed (continuing without stats): {e}")

        report = render_trend_report(
            db_path=args.history_db,
            limit=args.analysis_limit,
            use_ollama=True,
            ollama_model=args.ollama_model,
        )
        print(report)
        return

    logger.info("Validating configuration...")
    # Local test renders (--skip-upload) may use the macOS voice fallback instead of ElevenLabs.
    config_errors = validate_config(need_voices=not (args.skip_upload or args.dry_run))
    if config_errors:
        logger.error("Configuration errors found:")
        for error in config_errors:
            logger.error(f"  - {error}")
        logger.error("\nPlease fix these issues before running the script.")
        sys.exit(1)
    logger.info("Configuration validated successfully!")

    try:
        logger.info("Initializing components...")
        youtube_uploader = None
        if args.skip_upload or args.dry_run:
            logger.info("Skip-upload/dry-run: skipping YouTube authentication + channel verification")
        else:
            youtube_uploader = YouTubeUploader()

            channel_info = youtube_uploader.get_channel_info()
            if not channel_info:
                logger.error("Failed to get channel information. Exiting.")
                sys.exit(1)

            channel_name = channel_info.get('title', '')
            logger.info(f"Connected to channel: {channel_name}")
            logger.info(f"  Subscribers: {channel_info['subscriber_count']}")
            logger.info(f"  Videos: {channel_info['video_count']}")
            logger.info(f"  Views: {channel_info['view_count']}")

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

        _log_self_improvement_step(
            history=history,
            youtube_uploader=youtube_uploader,
            history_db_path=args.history_db,
            no_auto_optimize=args.no_auto_optimize,
        )

        reddit_fetcher = RedditFetcher()
        content_optimizer = ContentOptimizer()
        youtube_service = youtube_uploader.youtube_service if youtube_uploader else None
        video_generator = VideoGenerator(youtube_service=youtube_service)
        if args.render_style:
            video_generator.render_style_override = args.render_style

        # Steps 1–3: pick a story that passes the writers' room + moderation, then prepare metadata
        logger.info("\n" + "="*60)
        logger.info("Step 1: Choosing a story...")
        logger.info("="*60)

        trend_data = None
        topic_title = ""
        script = None
        metadata = None
        run_id = None
        queue_path = None

        max_attempts = 1 if (args.story_url or args.screenplay) else max(1, int(args.max_story_attempts))
        sources = _story_sources(args, reddit_fetcher, video_generator)
        for attempt in range(1, max_attempts + 1):
            nxt = next(sources, None)
            if nxt is None:
                break
            trend_data, prewritten, queue_path = nxt
            topic_title = trend_data.get("title", "N/A")
            origin = "queued screenplay" if queue_path else ("screenplay file" if prewritten else "Reddit")
            logger.info(f"[Attempt {attempt}/{max_attempts}] Candidate story ({origin}): {topic_title}")
            logger.info(f"From r/{trend_data.get('subreddit', 'unknown')} ({trend_data.get('score', 0)} upvotes)")

            script = None
            # A pre-written screenplay still has to load when we're only uploading, so the title comes from it.
            if prewritten is not None or not args.skip_video_generation:
                logger.info("\n" + "="*60)
                logger.info("Step 2: Writing the screenplay...")
                logger.info("="*60)
                try:
                    if prewritten is not None:
                        style = args.render_style or (screenplay_queue.load(queue_path).render_style if queue_path else None)
                        script = video_generator.use_screenplay(trend_data, prewritten, style,
                                                                writer="queue" if queue_path else "manual")
                    else:
                        script = video_generator._generate_script_from_trend(trend_data)
                except ValueError as e:
                    logger.error(f"Pre-written screenplay is invalid: {e}")
                    if queue_path:
                        screenplay_queue.mark_done(queue_path, "invalid", {"error": str(e)})
                    script = None
                if not script:
                    logger.warning("No usable screenplay for this story. Trying the next one...")
                    if not prewritten:
                        reason = (video_generator.last_generation_info or {}).get("script_rejected_reason", "rejected")
                        try:
                            reddit_fetcher._save_rejected_topic(topic_title, reason=f"director:{reason}")
                        except Exception:
                            pass
                    trend_data = None
                    continue
                logger.info(f"Screenplay ready ({len(script.split())} spoken words)")
                logger.info(f"Script preview: {script[:200]}...")

            logger.info("\n" + "="*60)
            logger.info("Step 3: Optimizing video metadata...")
            logger.info("="*60)
            gen = getattr(video_generator, "last_generation_info", {}) or {}
            credit = attribution(gen.get("music_track")) if gen.get("music_track") else None
            if credit is None and gen.get("mood"):
                credit = attribution(pick_track(gen.get("mood")))
            metadata = content_optimizer.optimize_metadata(
                trend_data, script=script, title=gen.get("screenplay_title"), music_credit=credit,
            )
            metadata["privacy_status"] = args.privacy
            metadata["category_id"] = args.category

            logger.info(f"Title: {metadata['title']}")
            logger.info(f"Description length: {len(metadata['description'])} characters")
            logger.info(f"Tags: {', '.join(metadata['tags'][:5])}...")
            logger.info(f"Hashtags: {', '.join(metadata['hashtags'])}")

            run_id = history.create_run(
                region=args.region,
                subreddit=trend_data.get("subreddit", "") or "",
                topic_title=topic_title or "",
                trend_data=trend_data or {},
                script=script or "",
                metadata=metadata or {},
                privacy_status=args.privacy,
                category_id=args.category,
            )
            logger.info(f"History run_id: {run_id}")
            if gen.get("experiment"):
                history.update_run(run_id, experiment=gen.get("experiment"))

            safety = evaluate_safety(trend_data=trend_data, script=script or "", metadata=metadata or {})
            history.update_run(
                run_id,
                moderation=safety.to_json(),
                moderation_status="pass" if safety.ok else "fail",
            )
            if safety.ok:
                logger.info(f"✓ Moderation PASS ({safety.method})")
                break

            logger.warning(f"✗ Moderation FAIL ({safety.method}): {', '.join(safety.reasons) if safety.reasons else safety.category}")
            history.update_run(run_id, upload_status="skipped")
            if queue_path:
                screenplay_queue.mark_done(queue_path, "rejected_moderation", {"reasons": safety.reasons})
            try:
                reddit_fetcher._save_rejected_topic(topic_title, reason=";".join(safety.reasons) if safety.reasons else safety.category)
            except Exception:
                pass
            trend_data = None
            metadata = None
            run_id = None

        if not trend_data or not metadata:
            logger.error("Could not find an appropriate story. Exiting.")
            sys.exit(1)

        if args.dry_run:
            history.update_run(run_id, upload_status="skipped")
            logger.info("\n" + "="*60)
            logger.info("DRY RUN MODE - Skipping video generation and upload")
            logger.info("="*60)
            return

        # Step 4: Generate video (if not skipping)
        video_path = None
        if not args.skip_video_generation:
            logger.info("\n" + "="*60)
            logger.info("Step 4: Generating animated video (ElevenLabs voices + Remotion/three.js)...")
            logger.info("="*60)

            os.makedirs(args.output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_path = os.path.join(args.output_dir, f"video_{timestamp}.mp4")

            result_path = video_generator.generate_video_from_trend(trend_data, script=script, output_path=video_path)
            if not result_path:
                history.update_run(run_id, upload_status="failed")
                gen = getattr(video_generator, "last_generation_info", {}) or {}
                logger.error("\n" + "="*60)
                logger.error("VIDEO GENERATION FAILED")
                logger.error("="*60)
                if gen.get("error"):
                    logger.error(f"Reason: {gen.get('error')}")
                logger.error("="*60)
                sys.exit(1)

            video_path = result_path
            try:
                final_dur = video_generator._ffprobe_duration(video_path)
            except Exception:
                final_dur = None

            gen = getattr(video_generator, "last_generation_info", {}) or {}
            if gen.get("final_script"):
                script = str(gen.get("final_script"))

            history.update_run(
                run_id,
                script=script,
                output_path=video_path,
                video_duration_seconds=final_dur,
                voice_provider=gen.get("voice_provider"),
                voice_config=gen.get("voice_config"),
                experiment=gen.get("experiment"),
            )
            logger.info(f"✓ Video generated successfully: {video_path}")
        else:
            if not args.video_file:
                logger.error("--video-file is required when using --skip-video-generation")
                sys.exit(1)
            if not os.path.exists(args.video_file):
                logger.error(f"Video file not found: {args.video_file}")
                sys.exit(1)
            video_path = args.video_file
            logger.info(f"Using existing video file: {video_path}")
            history.update_run(run_id, output_path=video_path)

        if args.skip_upload:
            history.update_run(run_id, upload_status="skipped")
            logger.info("\n" + "="*60)
            logger.info("SKIP UPLOAD MODE - Video generated but not uploaded")
            logger.info("="*60)
            logger.info(f"Final video path: {video_path}")
            return

        gen = getattr(video_generator, "last_generation_info", {}) if not args.skip_video_generation else {}
        if (gen or {}).get("voice_provider") == "macos_say":
            history.update_run(run_id, upload_status="skipped")
            logger.error("Refusing to upload: voiced with the macOS test fallback (ElevenLabs key missing).")
            logger.info(f"Final video path: {video_path}")
            sys.exit(1)

        logger.info("\n" + "="*60)
        logger.info("Step 5: Uploading video to YouTube...")
        logger.info("="*60)

        video_id = youtube_uploader.upload_video(
            video_path=video_path,
            metadata=metadata,
            privacy_status=args.privacy,
            category_id=args.category
        )

        if video_id:
            topic_title = trend_data.get('title', '') or trend_data.get('_topic_title', '')
            if topic_title:
                reddit_fetcher._save_used_topic(topic_title)
                logger.info(f"✓ Topic '{topic_title}' marked as used")
            if queue_path:
                screenplay_queue.mark_done(queue_path, "uploaded", {"youtube_video_id": video_id, "run_id": run_id})

            logger.info("\n" + "="*60)
            logger.info("SUCCESS! Video uploaded successfully!")
            logger.info("="*60)
            logger.info(f"Video ID: {video_id}")
            logger.info(f"Video URL: https://www.youtube.com/watch?v={video_id}")
            logger.info(f"Privacy Status: {args.privacy}")

            history.update_run(
                run_id,
                upload_status="success",
                upload_time=_utc_now_iso(),
                youtube_video_id=video_id,
                youtube_url=f"https://www.youtube.com/watch?v={video_id}",
            )

            if not args.no_auto_optimize:
                try:
                    changes = auto_optimize_generator_config(
                        db_path=args.history_db,
                        config_path=GENERATOR_CONFIG_PATH,
                        min_samples_per_variant=2,
                        lookback_runs=200,
                    )
                    if changes.get("updated"):
                        logger.info("✓ Auto-optimized generator_config.json weights after upload")
                except Exception as e:
                    logger.warning(f"Post-upload auto-optimization skipped: {e}")

            if args.privacy == "private":
                logger.info("\nNote: Video is set to private. Change privacy status in YouTube Studio.")
        else:
            history.update_run(run_id, upload_status="failed")
            logger.error("Failed to upload video.")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user. Exiting.")
        sys.exit(0)
    except Exception as e:
        error_str = str(e)
        if "packages_distributions" in error_str or ("importlib.metadata" in error_str and "has no attribute" in error_str):
            logger.debug(f"Suppressed compatibility warning: {e}")
            sys.exit(0)
        logger.error(f"\nUnexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except AttributeError as e:
        if "packages_distributions" not in str(e) and "importlib.metadata" not in str(e):
            raise
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        error_str = str(e)
        if "packages_distributions" in error_str or ("importlib.metadata" in error_str and "has no attribute" in error_str):
            sys.exit(0)
        raise
