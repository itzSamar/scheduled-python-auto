"""
MusicMixer: picks a background track by screenplay mood and ducks it under the dialogue.

Drop tracks into assets/music/<mood>/:
  funny/      goofy, comedy (Scheming Weasel is also the catch-all when a mood has nothing)
  wholesome/  warm or a little sad (officialbg)
  dramatic/   phonk, revenge, come-up
  tense/      borrows wholesome, then dramatic
"""
import logging
import os
import random
import subprocess
from typing import List, Optional

from .config import MUSIC_DIR

logger = logging.getLogger(__name__)

AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac")

# Dialogue sits a little under full level so the voice doesn't crowd the music.
# YouTube normalizes the whole mix to about -14 LUFS, so this is a balance change, not just a quieter file.
VOICE_VOLUME = 0.75

# If a mood folder is empty, borrow from these moods (in order).
MOOD_FALLBACKS = {
    "funny": ["wholesome"],
    "wholesome": ["funny"],
    "dramatic": ["tense", "funny"],
    "tense": ["wholesome", "dramatic"],
}

# License lines appended to the YouTube description. Key is a lowercase substring of the filename.
ATTRIBUTION = {
    "scheming weasel": (
        'Music: "Scheming Weasel (faster version)" by Kevin MacLeod (incompetech.com)\n'
        "Licensed under Creative Commons: By Attribution 4.0 License\n"
        "https://creativecommons.org/licenses/by/4.0/"
    ),
}


def _tracks(mood: str) -> List[str]:
    d = os.path.join(MUSIC_DIR, mood)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(AUDIO_EXTS))


def pick_track(mood: str, seed: Optional[int] = None) -> Optional[str]:
    rng = random.Random(seed)
    order = [mood] + MOOD_FALLBACKS.get(mood, []) + ["funny", "wholesome"]
    seen = set()
    for m in order:
        if m in seen:
            continue
        seen.add(m)
        tracks = _tracks(m)
        if tracks:
            return tracks[rng.randrange(len(tracks))]
    return None


def attribution(track: Optional[str]) -> Optional[str]:
    """Description credit for tracks that require it. None when the file has no recorded license line."""
    if not track:
        return None
    name = os.path.basename(track).lower()
    for key, text in ATTRIBUTION.items():
        if key in name:
            return text
    return None


def mix(dialogue_wav: str, out_path: str, *, track: Optional[str], duration: float,
        music_volume: float = 0.36, fade_out: float = 1.5) -> str:
    """Dialogue + looped music ducked under the voice. The mix lands at -16.5 LUFS, a little under YouTube's -14."""
    voice = f"volume={VOICE_VOLUME},"
    if not track:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", dialogue_wav,
               "-af", f"{voice}loudnorm=I=-16.5:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "2", out_path]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        return out_path

    fade_start = max(0.0, duration - fade_out)
    graph = (
        f"[0:a]aformat=sample_rates=48000:channel_layouts=mono,{voice}asplit=2[voice][key];"
        f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:{duration:.3f},asetpts=PTS-STARTPTS,"
        f"volume={music_volume},afade=t=in:d=0.6,afade=t=out:st={fade_start:.3f}:d={fade_out}[music];"
        "[music][key]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=350:makeup=1[ducked];"
        "[voice]pan=stereo|c0=c0|c1=c0[voice_st];"
        "[voice_st][ducked]amix=inputs=2:duration=first:normalize=0,"
        "loudnorm=I=-16.5:TP=-1.5:LRA=11[out]"
    )
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", dialogue_wav,
        "-stream_loop", "-1", "-i", track,
        "-filter_complex", graph,
        "-map", "[out]", "-t", f"{duration:.3f}", "-ar", "48000", "-ac", "2",
        out_path,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"music mix failed: {r.stderr[-800:]}")
    return out_path
