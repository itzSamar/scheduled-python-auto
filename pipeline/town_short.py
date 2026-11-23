"""
Voice and render an "In this town" short.

The shot script is a JSON file of short first-person lines. Each line names the
set that should be on screen while it is spoken. Output is a 1080x1920 mp4.
"""
import argparse
import json
import os
import subprocess
import sys

from .config import MUSIC_DIR
from .music_mixer import mix
from .story_director import strip_speech_tags
from .video_generator import find_node
from .voice_renderer import SAMPLE_RATE, VoiceRenderer, _read_pcm, _write_pcm, words_from_chars

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANIMATOR = os.path.join(ROOT, "animator")
GAP = 0.16
SHOT_GAP = 0.32
LEAD = 0.28
TAIL = 0.85


def _silence(seconds: float) -> bytes:
    return b"\x00" * int(seconds * SAMPLE_RATE) * 2


def build(script_path: str, work: str) -> dict:
    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)
    os.makedirs(work, exist_ok=True)
    renderer = VoiceRenderer()
    if renderer.provider != "elevenlabs":
        raise SystemExit("ElevenLabs is required for a posted short")
    lines = script["lines"]
    spoken = [strip_speech_tags(line["text"]) for line in lines]
    pieces = []
    cursor = LEAD
    pcm = _silence(LEAD)
    words = []
    shot_bounds = []
    current = None
    for i, line in enumerate(lines):
        wav, chars, _dur = renderer._synthesize(
            line["text"],
            script["voice_id"],
            role="narrator",
            previous_text=spoken[i - 1] if i else "",
            next_text=spoken[i + 1] if i + 1 < len(lines) else "",
        )
        line_pcm = _read_pcm(wav)
        dur = len(line_pcm) / 2 / SAMPLE_RATE
        if current and current["set"] != line["shot"]:
            pcm += _silence(SHOT_GAP)
            cursor += SHOT_GAP
            shot_bounds.append(current)
            current = None
        elif i:
            pcm += _silence(GAP)
            cursor += GAP
        start = cursor
        words.extend(words_from_chars(chars, start))
        pcm += line_pcm
        cursor += dur
        if current is None:
            current = {"set": line["shot"], "start": round(start, 3), "end": round(cursor, 3)}
        else:
            current["end"] = round(cursor, 3)
    if current:
        shot_bounds.append(current)
    pcm += _silence(TAIL)
    duration = len(pcm) / 2 / SAMPLE_RATE
    shot_bounds[-1]["end"] = round(duration, 3)
    dialogue = os.path.join(work, "dialogue.wav")
    _write_pcm(dialogue, pcm)
    track = os.path.join(MUSIC_DIR, "wholesome", "officialbg.mp3")
    mix_path = os.path.join(work, "mix.wav")
    mix(dialogue, mix_path, track=track, duration=duration, music_volume=0.28)
    props = {"shots": shot_bounds, "words": words}
    props_path = os.path.join(work, "props.json")
    with open(props_path, "w", encoding="utf-8") as f:
        json.dump(props, f)
    return {"props": props_path, "mix": mix_path, "duration": duration, "title": script["title"], "script": script}


def render(props_path: str, silent_path: str) -> None:
    node = find_node()
    if not node:
        raise SystemExit("Node 20 not found")
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(node) + os.pathsep + env.get("PATH", "")
    cli = os.path.join(ANIMATOR, "node_modules", "@remotion", "cli", "remotion-cli.js")
    cmd = [node, cli, "render", "InThisTown", silent_path, f"--props={props_path}", "--gl=angle", "--muted", "--log=error"]
    r = subprocess.run(cmd, cwd=ANIMATOR, env=env)
    if r.returncode != 0 or not os.path.exists(silent_path):
        raise SystemExit(f"render failed ({r.returncode})")


def mux(silent: str, audio: str, out_path: str) -> None:
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", silent, "-i", audio,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        out_path,
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("script")
    parser.add_argument("--work", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    script_path = args.script if os.path.isabs(args.script) else os.path.join(ROOT, args.script)
    work = args.work or os.path.join(ROOT, "generated_videos", "town_gta6_work")
    built = build(script_path, work)
    print(f"VOICED {built['duration']:.1f}s")
    if not args.render:
        print(f"PROPS {built['props']}")
        return
    silent = os.path.join(work, "silent.mp4")
    render(built["props"], silent)
    out = args.out or os.path.join(ROOT, "generated_videos", "in_this_town_gta6.mp4")
    mux(silent, built["mix"], out)
    print(f"VIDEO {out}")


if __name__ == "__main__":
    sys.exit(main() or 0)
