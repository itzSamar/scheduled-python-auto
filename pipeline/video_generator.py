"""
Animated Reddit story generator.

Pipeline:
1) screenplay: a queued (pre-written) screenplay, or the local LLM writers' room (story_director)
2) voice_renderer voices every beat with a per-character ElevenLabs voice -> dialogue.wav + timeline.json
3) music_mixer ducks mood music under the dialogue (-14 LUFS)
4) animator/ (Remotion + three.js) renders the 1080x1920 2D/3D cartoon from screenplay + timeline
5) ffmpeg muxes the rendered video with the final mix
"""

import glob
import hashlib
import json
import logging
import os
import platform
import random
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from .config import ANIMATOR_DIR, GENERATOR_CONFIG_PATH, NODE_BINARY, OUTPUT_DIR
from .llm_client import OllamaClient
from .music_mixer import mix, pick_track
from .story_director import StoryDirector, load_kit, screenplay_to_script, screenplay_word_count
from .voice_renderer import VoiceRenderer

logger = logging.getLogger(__name__)

RENDER_STYLES = ("2d", "3d", "mixed")


def _native_arch() -> str:
    # Under Rosetta (x86_64 Python on Apple Silicon) platform.machine() lies, so ask the kernel.
    if sys.platform == "darwin":
        try:
            r = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True, timeout=5)
            if r.stdout.strip() == "1":
                return "arm64"
        except Exception:
            pass
    m = platform.machine().lower()
    return {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64"}.get(m, m)


def _pinned_node_major() -> Optional[int]:
    try:
        with open(os.path.join(ANIMATOR_DIR, ".nvmrc"), "r", encoding="utf-8") as f:
            return int(f.read().strip().lstrip("v").split(".")[0])
    except Exception:
        return None


def find_node() -> Optional[str]:
    """
    Node >= 18 for Remotion. NODE_BINARY wins; otherwise prefer a build matching the native CPU
    (animator/node_modules holds native esbuild/compositor binaries), then the .nvmrc major, then newest.
    """
    paths: List[str] = []
    if NODE_BINARY:
        paths.append(NODE_BINARY)
    paths += glob.glob(os.path.expanduser("~/.nvm/versions/node/v*/bin/node"))
    for p in (shutil.which("node"), "/opt/homebrew/bin/node", "/usr/local/bin/node"):
        if p and p not in paths:
            paths.append(p)

    native, pinned = _native_arch(), _pinned_node_major()
    found = []
    for i, p in enumerate(paths):
        try:
            out = subprocess.run([p, "-p", "process.arch + ' ' + process.versions.node"],
                                 capture_output=True, text=True, timeout=10).stdout.split()
            arch, version = out[0], [int(x) for x in out[1].split(".")]
        except Exception:
            continue
        if version[0] < 18:
            continue
        if NODE_BINARY and p == NODE_BINARY:
            return p
        found.append(((arch == native, version[0] == pinned, version, -i), p))
    return max(found)[1] if found else None


class AnimatedVideoGenerator:
    def __init__(self, youtube_service=None):
        self.youtube_service = youtube_service
        self.last_generation_info: Dict[str, Any] = {}
        self.llm = OllamaClient()
        self.director = StoryDirector(self.llm, load_kit())
        self._screenplay: Optional[Dict[str, Any]] = None
        self._screenplay_key: Optional[str] = None
        self._config: Optional[Dict[str, Any]] = None
        # Set by --render-style to bypass the render_style A/B experiment.
        self.render_style_override: Optional[str] = None

    # ----------------------------
    # Config / experiments
    # ----------------------------
    def _load_generator_config(self) -> Dict[str, Any]:
        if self._config is None:
            try:
                with open(GENERATOR_CONFIG_PATH, "r", encoding="utf-8") as f:
                    self._config = json.load(f) or {}
            except Exception:
                self._config = {}
        return self._config

    def _pick_variant(self, exp_name: str) -> Optional[Dict[str, Any]]:
        exp = ((self._load_generator_config().get("experiments") or {}).get(exp_name)) or {}
        variants = [v for v in (exp.get("variants") or []) if isinstance(v, dict) and v.get("id")]
        if not variants:
            return None
        weights = []
        for v in variants:
            try:
                weights.append(max(0.0, float(v.get("weight", 1.0))))
            except (TypeError, ValueError):
                weights.append(1.0)
        if sum(weights) <= 0:
            weights = [1.0] * len(variants)
        return random.choices(variants, weights=weights, k=1)[0]

    def _limits(self):
        cfg = self._load_generator_config()
        video = cfg.get("video") or {}
        words = cfg.get("target_word_count") or {}
        max_seconds = float(video.get("short_max_seconds", 90) or 90)
        return max_seconds, int(words.get("min", 170)), int(words.get("max", 230))

    def _pick_render_style(self, variants: Dict[str, Dict[str, str]], preferred: Optional[str] = None) -> str:
        if self.render_style_override in RENDER_STYLES:
            return self.render_style_override
        if preferred in RENDER_STYLES:
            return preferred
        style = self._pick_variant("render_style")
        render_style = style["id"] if style and style["id"] in RENDER_STYLES else "mixed"
        variants["render_style"] = {"id": render_style}
        return render_style

    @staticmethod
    def _trend_key(trend_data: Dict[str, Any]) -> str:
        return str(trend_data.get("url") or trend_data.get("title") or "")

    # ----------------------------
    # Step 1: screenplay
    # ----------------------------
    def writer_ready(self) -> bool:
        return self.llm.ready()

    def rank_stories(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Best-first candidates according to the writers' room triage (falls back to engagement order)."""
        try:
            ranked = self.director.pick_stories(candidates)
        except Exception as e:
            logger.warning(f"Story triage failed ({e}); using engagement order")
            return candidates
        for trend, score, reason in ranked:
            logger.info(f"  triage {score}/10: {trend.get('title', '')[:70]} - {reason[:100]}")
        return [t for t, score, _ in ranked if score >= 7]

    def _generate_script_from_trend(self, trend_data: Dict[str, Any]) -> str:
        """Directs the screenplay and returns its flattened narration (used for title/moderation)."""
        self.last_generation_info = {}
        self._screenplay = None
        max_seconds, min_words, max_words = self._limits()

        variants: Dict[str, Dict[str, str]] = {}
        tease = question = None
        hook = self._pick_variant("hook_tease_style")
        if hook:
            variants["hook_tease_style"] = {"id": hook["id"]}
            tease = hook.get("guidance")
        ending = self._pick_variant("ending_question_style")
        if ending:
            variants["ending_question_style"] = {"id": ending["id"]}
            question = ending.get("guidance")
        render_style = self._pick_render_style(variants)

        self.last_generation_info.update({
            "experiment": {"variants": variants},
            "render_style": render_style,
            "script_mode": "animated_short",
            "writer": f"ollama:{self.llm.model}",
            "max_duration_seconds": max_seconds,
        })

        t0 = time.time()
        result = self.director.direct(trend_data, min_words=min_words, max_words=max_words, tease=tease, question=question)
        logger.info(f"Writers' room finished in {time.time() - t0:.0f}s")
        if not result.suitable or not result.screenplay:
            self.last_generation_info["script_rejected_reason"] = result.reason or "unsuitable"
            logger.warning(f"Story rejected by director: {result.reason}")
            return ""
        self.last_generation_info["director"] = {"table_reads": result.notes.get("table_reads")}
        return self._accept_screenplay(trend_data, result.screenplay, result.warnings)

    def use_screenplay(self, trend_data: Dict[str, Any], screenplay: Dict[str, Any], render_style: Optional[str] = None,
                       *, writer: str = "manual") -> str:
        """Use a pre-written screenplay (queue file or --screenplay) instead of the LLM writers' room."""
        fixed, problems, warnings = self.director.validate(screenplay)
        if not fixed or problems:
            raise ValueError(f"Invalid screenplay: {problems}")
        max_seconds, min_words, max_words = self._limits()
        for problem in self.director.rule_problems(fixed, min_words, max_words):
            logger.warning(f"Screenplay rule: {problem}")
            warnings.append(problem)
        variants: Dict[str, Dict[str, str]] = {}
        style = self._pick_render_style(variants, render_style)
        self.last_generation_info = {
            "experiment": {"variants": variants},
            "render_style": style,
            "script_mode": "animated_short_prewritten",
            "writer": writer,
            "max_duration_seconds": max_seconds,
        }
        return self._accept_screenplay(trend_data, fixed, warnings)

    def _accept_screenplay(self, trend_data: Dict[str, Any], screenplay: Dict[str, Any], warnings: List[str]) -> str:
        self._screenplay = screenplay
        self._screenplay_key = self._trend_key(trend_data)
        script = screenplay_to_script(screenplay)
        self.last_generation_info.update({
            "screenplay_title": screenplay.get("title"),
            "mood": screenplay.get("mood"),
            "screenplay_words": screenplay_word_count(screenplay),
            "screenplay_warnings": warnings,
            "final_script": script,
        })
        return script

    # ----------------------------
    # Step 2-5: voice, music, render, mux
    # ----------------------------
    def _voice(self, renderer: VoiceRenderer, screenplay: Dict[str, Any], work: str, seed: int, max_seconds: float):
        track = renderer.render(screenplay, os.path.join(work, "voice"), seed=seed)
        for attempt in range(2):
            duration = float(track.timeline["duration"])
            if duration <= max_seconds:
                return screenplay, track
            words = screenplay_word_count(screenplay)
            target = max(60, int(words * (max_seconds - 2.0) / duration))
            logger.info(f"Voiced cut is {duration:.1f}s (> {max_seconds:.0f}s cap); tightening {words} -> ~{target} words")
            shorter = self.director.shorten(screenplay, target) if self.llm.ready() else None
            if not shorter:
                break
            screenplay = shorter
            track = renderer.render(screenplay, os.path.join(work, "voice"), seed=seed, cast=track.cast)
        if float(track.timeline["duration"]) > max_seconds:
            raise RuntimeError(f"voiced duration {track.timeline['duration']:.1f}s exceeds the {max_seconds:.0f}s cap")
        return screenplay, track

    def _render(self, props_path: str, out_path: str) -> None:
        node = find_node()
        if not node:
            raise RuntimeError("Node >= 18 not found (set NODE_BINARY or install Node 20 via nvm)")
        env = dict(os.environ)
        env["PATH"] = os.path.dirname(node) + os.pathsep + env.get("PATH", "")
        if not os.path.isdir(os.path.join(ANIMATOR_DIR, "node_modules")):
            logger.info("Installing animator dependencies (npm ci)...")
            npm = os.path.join(os.path.dirname(node), "npm")
            subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=ANIMATOR_DIR, env=env, check=True, timeout=900)
        cli = os.path.join(ANIMATOR_DIR, "node_modules", "@remotion", "cli", "remotion-cli.js")
        # angle uses the GPU. Cloud agents have no GPU, so a WebGL failure retries on swangle
        # (SwiftShader). Machines with a GPU still take the angle path.
        errors = []
        t0 = time.time()
        for gl in ("angle", "swangle"):
            try:
                if os.path.exists(out_path):
                    os.remove(out_path)
            except OSError:
                pass
            cmd = [
                node, cli, "render", "StoryShort", out_path,
                f"--props={props_path}",
                f"--gl={gl}",
                "--muted",
                "--log=error",
            ]
            r = subprocess.run(cmd, cwd=ANIMATOR_DIR, env=env, capture_output=True, text=True, timeout=3600)
            if r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                logger.info(f"Rendered animation in {time.time() - t0:.0f}s (gl={gl})")
                return
            tail = (r.stderr or r.stdout or "")[-2000:]
            errors.append(f"gl={gl} ({r.returncode}): {tail}")
            webgl_down = "webgl" in tail.lower()
            if gl == "angle" and webgl_down:
                logger.warning("Remotion could not create a GPU WebGL context; retrying with software GL (swangle)")
                continue
            break
        raise RuntimeError("Remotion render failed: " + " | ".join(errors))

    @staticmethod
    def _mux(video: str, audio: str, out_path: str) -> None:
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", video, "-i", audio,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
            out_path,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise RuntimeError(f"mux failed: {r.stderr[-800:]}")

    def generate_video_from_trend(self, trend_data: Dict[str, Any], script: str = None, output_path: str = None) -> Optional[str]:
        if self._screenplay is None or self._screenplay_key != self._trend_key(trend_data):
            if not self._generate_script_from_trend(trend_data):
                return None
        screenplay = self._screenplay
        assert screenplay is not None
        max_seconds, _, _ = self._limits()
        render_style = self.last_generation_info.get("render_style", "mixed")

        if not output_path:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            output_path = os.path.join(OUTPUT_DIR, f"animated_{time.strftime('%Y%m%d_%H%M%S')}.mp4")
        output_path = os.path.abspath(output_path)
        work = os.path.splitext(output_path)[0] + "_work"
        os.makedirs(work, exist_ok=True)
        seed = int(hashlib.sha1(self._trend_key(trend_data).encode("utf-8")).hexdigest()[:8], 16) % 100000

        try:
            renderer = VoiceRenderer()
            if renderer.provider == "elevenlabs":
                needed = renderer.estimate_characters(screenplay)
                left = renderer.ensure_key(needed)
                if left is not None and left >= 0:
                    logger.info(f"ElevenLabs quota for this key: {left} chars (need ~{needed})")
            logger.info(f"Voicing {sum(len(s['beats']) for s in screenplay['scenes'])} beats ({renderer.provider})...")
            screenplay, track = self._voice(renderer, screenplay, work, seed, max_seconds)
            duration = float(track.timeline["duration"])

            music = pick_track(screenplay.get("mood", "funny"), seed=seed)
            mix_path = os.path.join(work, "mix.wav")
            mix(track.dialogue_wav, mix_path, track=music, duration=duration)

            props = {
                "screenplay": screenplay,
                "timeline": track.timeline,
                "style": render_style,
                "audioSrc": None,
                "subreddit": trend_data.get("subreddit") or "",
                "seed": seed,
            }
            props_path = os.path.join(work, "props.json")
            with open(props_path, "w", encoding="utf-8") as f:
                json.dump(props, f)
            with open(os.path.join(work, "screenplay.json"), "w", encoding="utf-8") as f:
                json.dump(screenplay, f, indent=1)

            # The writer model holds ~18 GB; give the renderer that memory back.
            self.llm.unload()
            silent = os.path.join(work, "video_silent.mp4")
            logger.info(f"Rendering {duration:.1f}s animation (style={render_style})...")
            self._render(props_path, silent)
            self._mux(silent, mix_path, output_path)
        except Exception as e:
            logger.error(f"Animated video generation failed: {e}")
            self.last_generation_info["error"] = str(e)
            return None

        for p in (silent, mix_path, track.dialogue_wav):
            try:
                os.remove(p)
            except OSError:
                pass

        self._screenplay = screenplay
        script_text = screenplay_to_script(screenplay)
        self.last_generation_info.update({
            "final_script": script_text,
            "screenplay_words": screenplay_word_count(screenplay),
            "voice_provider": track.provider,
            "voice_config": {
                "cast": track.cast,
                "render_style": render_style,
                "music_track": os.path.basename(music) if music else None,
                "model": renderer.model if track.provider == "elevenlabs" else None,
            },
            "music_track": os.path.basename(music) if music else None,
            "video_duration_seconds": duration,
            "work_dir": work,
        })
        return output_path

    def _ffprobe_duration(self, path: str) -> Optional[float]:
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
                capture_output=True, text=True, timeout=30,
            ).stdout.strip()
            return float(out) if out else None
        except Exception:
            return None


VideoGenerator = AnimatedVideoGenerator
