"""
VoiceRenderer: casts an ElevenLabs voice per character, voices every screenplay beat,
stitches one dialogue track and writes a timeline with word timings + mouth shapes.

Without an ElevenLabs key it falls back to macOS `say` voices (for offline testing only; never uploaded).
With ELEVENLABS_API_KEY + ELEVENLABS_API_KEY_2 (etc.), keys rotate when one month's quota is empty and
snap back to the primary once it regenerates.
"""
import argparse
import base64
import hashlib
import json
import logging
import os
import random
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .config import (
    ELEVENLABS_KEY_STATE_PATH,
    ELEVENLABS_MODEL,
    VOICE_CACHE_DIR,
    VOICES_PATH,
    elevenlabs_api_keys,
)
from .story_director import TAG_RE, strip_speech_tags

logger = logging.getLogger(__name__)

SAMPLE_RATE = 48000
LEAD_IN = 0.35
GAP_IN_SCENE = 0.22
GAP_BETWEEN_SCENES = 0.55
TAIL = 1.2

# Delivery tag added to a beat when the writer didn't tag it (ElevenLabs v4 audio tags).
EMOTION_TAGS: Dict[str, str] = {
    "happy": "cheerful",
    "laughing": "laughs",
    "sad": "sad",
    "crying": "crying",
    "angry": "angry",
    "shocked": "gasps",
    "smug": "smug",
    "nervous": "nervous",
    "confused": "confused",
    "annoyed": "annoyed",
    "embarrassed": "embarrassed",
}
# Tags that make a sound rather than color the tone; never repeat them on back-to-back lines.
SOUND_TAGS = {"laughs", "chuckles", "giggles", "sighs", "gasps", "groans", "scoffs", "gulps", "crying"}

MOUTH_SHAPES = {
    **{c: "open" for c in "ah"},
    **{c: "wide" for c in "eiyszcxjgk"},
    **{c: "round" for c in "ouwq"},
    **{c: "closed" for c in "mbp"},
    **{c: "teeth" for c in "fvt"},
}


class VoiceError(RuntimeError):
    pass


def _sha(obj: Any) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()[:20]


def _ffmpeg_to_wav(src: str, dst: str) -> None:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ar", str(SAMPLE_RATE), "-ac", "1", "-sample_fmt", "s16", dst]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)


def _read_pcm(path: str) -> bytes:
    with wave.open(path, "rb") as w:
        if w.getframerate() != SAMPLE_RATE or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError(f"unexpected wav format in {path}")
        return w.readframes(w.getnframes())


def _write_pcm(path: str, pcm: bytes) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)


def _spoken_chars(chars: List[str], times: List[Tuple[float, float]]) -> List[Tuple[str, float, float]]:
    """Walk aligned characters in order, dropping [audio tags]."""
    out: List[Tuple[str, float, float]] = []
    skip = False
    for ch, (s, e) in zip(chars, times):
        if skip:
            skip = ch != "]"
            continue
        if ch == "[":
            skip = True
            continue
        out.append((ch, s, e))
    # Tag removal can leave a leading space or doubled spaces; captions split on whitespace anyway.
    while out and out[0][0].isspace():
        out.pop(0)
    return out


def _estimate_chars(text: str, duration: float) -> List[Tuple[str, float, float]]:
    """Fallback timing when the provider gives no timestamps: spread characters evenly."""
    clean = strip_speech_tags(text)
    if not clean:
        return []
    start, end = 0.05, max(0.2, duration - 0.1)
    step = (end - start) / len(clean)
    return [(c, start + i * step, start + (i + 1) * step) for i, c in enumerate(clean)]


def words_from_chars(chars: List[Tuple[str, float, float]], offset: float) -> List[Dict[str, Any]]:
    words: List[Dict[str, Any]] = []
    cur, ws, we = "", 0.0, 0.0
    for ch, s, e in chars:
        if ch.isspace():
            if cur:
                words.append({"text": cur, "start": round(ws + offset, 3), "end": round(we + offset, 3)})
            cur = ""
            continue
        if not cur:
            ws = s
        cur += ch
        we = e
    if cur:
        words.append({"text": cur, "start": round(ws + offset, 3), "end": round(we + offset, 3)})
    return words


def mouth_from_chars(chars: List[Tuple[str, float, float]], offset: float) -> List[List[Any]]:
    """Keyframes [time, shape] for lip-sync. Shapes: rest, closed, mid, open, wide, round, teeth."""
    raw: List[Tuple[float, str]] = []
    for ch, s, _e in chars:
        c = ch.lower()
        if c.isalpha():
            shape = MOUTH_SHAPES.get(c, "mid")
        else:
            shape = "rest"
        raw.append((s, shape))
    if chars:
        raw.append((chars[-1][2], "rest"))
    keys: List[List[Any]] = []
    for t, shape in raw:
        if keys and keys[-1][1] == shape:
            continue
        if keys and (t + offset) - keys[-1][0] < 0.045:
            keys[-1][1] = shape  # too fast to read on screen; keep the latest shape
            continue
        keys.append([round(t + offset, 3), shape])
    return keys


@dataclass
class VoiceTrack:
    dialogue_wav: str
    timeline: Dict[str, Any]
    cast: Dict[str, Dict[str, Any]]
    provider: str


def _key_label(key: str, index: int) -> str:
    """Safe log label: which slot + last 4 chars, never the full secret."""
    return f"key{index + 1}(…{key[-4:]})" if len(key) >= 4 else f"key{index + 1}"


def _quota_remaining(api_key: str, index: int = 0) -> Optional[int]:
    from elevenlabs import ElevenLabs

    try:
        sub = ElevenLabs(api_key=api_key).user.subscription.get()
        return int(sub.character_limit) - int(sub.character_count)
    except Exception as e:
        logger.warning(f"Could not read ElevenLabs quota for {_key_label(api_key, index)}: {e}")
        return None


def _is_quota_error(status_code: Optional[int], detail: str) -> bool:
    blob = (detail or "").lower()
    return status_code in (401, 402) or "quota" in blob or "credit" in blob or "limit" in blob


class VoiceRenderer:
    def __init__(self, voices_path: str = VOICES_PATH, cache_dir: str = VOICE_CACHE_DIR, provider: Optional[str] = None):
        with open(voices_path, "r", encoding="utf-8") as f:
            self.voices = json.load(f)
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.model = self.voices.get("model") or ELEVENLABS_MODEL
        self._keys = elevenlabs_api_keys()
        self._key_index = self._load_key_index()
        self._client = None
        self._exhausted: set = set()  # indexes that failed quota this process
        if provider:
            self.provider = provider
        elif self._keys:
            self.provider = "elevenlabs"
        elif sys.platform == "darwin":
            logger.warning("ELEVENLABS_API_KEY missing: using macOS voices (test fallback, not for uploads)")
            self.provider = "macos_say"
        else:
            raise VoiceError("ELEVENLABS_API_KEY is required for voices")

    def _load_key_index(self) -> int:
        try:
            with open(ELEVENLABS_KEY_STATE_PATH, "r", encoding="utf-8") as f:
                idx = int((json.load(f) or {}).get("active_index") or 0)
            return idx if 0 <= idx < max(1, len(self._keys)) else 0
        except (OSError, ValueError, TypeError):
            return 0

    def _save_key_index(self, index: int) -> None:
        self._key_index = index
        try:
            os.makedirs(os.path.dirname(ELEVENLABS_KEY_STATE_PATH), exist_ok=True)
            with open(ELEVENLABS_KEY_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "active_index": index,
                    "updated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    "keys": len(self._keys),
                }, f)
        except OSError as e:
            logger.warning(f"Could not save ElevenLabs key state: {e}")

    def _active_key(self) -> str:
        if not self._keys:
            raise VoiceError("No ElevenLabs API keys configured")
        return self._keys[self._key_index]

    def _eleven(self):
        if self._client is None:
            from elevenlabs import ElevenLabs

            self._client = ElevenLabs(api_key=self._active_key())
        return self._client

    def _use_key(self, index: int) -> None:
        if index == self._key_index and self._client is not None:
            return
        self._client = None
        self._save_key_index(index)
        logger.info(f"Using ElevenLabs {_key_label(self._keys[index], index)}")

    def ensure_key(self, needed: int = 0) -> int:
        """
        Pick an ElevenLabs key with enough remaining characters.
        Prefers the primary key whenever it has quota (so we snap back after regenerating).
        """
        if self.provider != "elevenlabs":
            return -1
        if not self._keys:
            raise VoiceError("No ElevenLabs API keys configured")

        order = list(range(len(self._keys)))
        # Try primary first, then the rest; still probe the remembered index early if it isn't 0.
        if self._key_index and self._key_index < len(self._keys):
            order = [0, self._key_index] + [i for i in order if i not in (0, self._key_index)]

        last_remaining: Dict[int, Optional[int]] = {}
        for index in order:
            if index in self._exhausted:
                continue
            remaining = _quota_remaining(self._keys[index], index)
            last_remaining[index] = remaining
            if remaining is None:
                # Can't read quota (transient); try this key if nothing better is proven.
                continue
            if remaining >= max(1, needed):
                if index != self._key_index:
                    logger.info(
                        f"ElevenLabs rotate -> {_key_label(self._keys[index], index)} "
                        f"({remaining} chars left; need ~{needed})"
                    )
                self._use_key(index)
                return remaining

        # No key reported enough quota. Fall back to any key we couldn't measure, else fail.
        for index in order:
            if index in self._exhausted:
                continue
            if last_remaining.get(index) is None:
                self._use_key(index)
                logger.warning(
                    f"ElevenLabs quota unknown for {_key_label(self._keys[index], index)}; trying it anyway"
                )
                return -1

        summary = ", ".join(
            f"{_key_label(self._keys[i], i)}={last_remaining.get(i)}" for i in range(len(self._keys))
        )
        raise VoiceError(
            f"All ElevenLabs keys are out of characters (need ~{needed}). Quotas: {summary}"
        )

    def _rotate_after_quota_error(self) -> bool:
        """Mark the current key exhausted and switch to the next one. Returns False if none left."""
        old = self._key_index
        self._exhausted.add(old)
        self._client = None
        for index in range(len(self._keys)):
            if index in self._exhausted:
                continue
            logger.warning(
                f"ElevenLabs {_key_label(self._keys[old], old)} hit quota; "
                f"rotating to {_key_label(self._keys[index], index)}"
            )
            self._use_key(index)
            return True
        return False

    # ----------------------------
    # Casting
    # ----------------------------
    def _narrator_voice(self, gender: str, age: str) -> str:
        options = self.voices["narrator"].get(gender) or self.voices["narrator"]["female"]
        for v in options:
            if age in v.get("ages", []):
                return v["id"]
        return options[min(1, len(options) - 1)]["id"]

    def cast(self, screenplay: Dict[str, Any], seed: int = 0) -> Dict[str, Dict[str, Any]]:
        """speaker id -> {voice, provider, role}. 'narrator' and 'op' share OP's voice."""
        rng = random.Random(seed)
        chars = {c["id"]: c for c in screenplay.get("characters", [])}
        op = chars.get("op") or {}
        op_gender = op.get("gender", "female")
        out: Dict[str, Dict[str, Any]] = {}

        if self.provider == "elevenlabs":
            narrator_voice = self._narrator_voice(op_gender, op.get("age", "20s"))
            used = {narrator_voice}
            for cid, c in chars.items():
                if cid == "op":
                    continue
                pool = [v for v in self.voices["voices"] if v["gender"] == c.get("gender") and v["id"] not in used]
                if not pool:
                    pool = [v for v in self.voices["voices"] if v["id"] not in used] or self.voices["voices"]

                def score(v: Dict[str, Any]) -> float:
                    s = 2.0 if c.get("age") in v.get("ages", []) else 0.0
                    s += 1.0 if c.get("voiceTone") in v.get("tones", []) else 0.0
                    s -= 0.4 if v.get("accent", "american") != "american" else 0.0
                    return s + rng.random() * 0.5

                pick = max(pool, key=score)
                used.add(pick["id"])
                out[cid] = {"voice": pick["id"], "name": pick.get("name"), "provider": "elevenlabs", "role": "character"}
        else:
            fb = self.voices["macos_fallback"]
            narrator_voice = fb["narrator"].get(op_gender, "Samantha")
            used = {narrator_voice}
            for cid, c in chars.items():
                if cid == "op":
                    continue
                pool = [v for v in fb.get(c.get("gender", "female"), []) if v not in used] or [narrator_voice]
                pick = pool[rng.randrange(len(pool))]
                used.add(pick)
                out[cid] = {"voice": pick, "provider": "macos_say", "role": "character"}

        out["narrator"] = {"voice": narrator_voice, "provider": self.provider, "role": "narrator"}
        out["op"] = {**out["narrator"], "role": "character"}
        return out

    # ----------------------------
    # Synthesis
    # ----------------------------
    def _delivery_text(self, beat: Dict[str, Any], last_tag: Dict[str, str]) -> str:
        text = beat.get("text", "")
        if self.provider != "elevenlabs":
            return strip_speech_tags(text)
        speaker = beat.get("speaker", "narrator")
        if TAG_RE.search(text):
            last_tag[speaker] = ""
            return text
        tag = EMOTION_TAGS.get(beat.get("emotion", ""), "")
        if tag in SOUND_TAGS and last_tag.get(speaker) == tag:
            tag = ""  # don't laugh/gasp on every consecutive line
        last_tag[speaker] = tag
        return f"[{tag}] {text}" if tag else text

    def _settings(self, role: str) -> Dict[str, float]:
        s = (self.voices.get("settings") or {}).get(role) or {}
        return {"stability": float(s.get("stability", 0.45)), "similarity_boost": float(s.get("similarity_boost", 0.8))}

    def _synthesize(self, text: str, voice: str, *, role: str = "character", previous_text: str = "",
                    next_text: str = "") -> Tuple[str, List[Tuple[str, float, float]], float]:
        """Returns (normalized wav path, spoken chars with times, duration). Cached on disk."""
        settings = self._settings(role) if self.provider == "elevenlabs" else {}
        key = _sha([self.provider, self.model, voice, text, settings, previous_text, next_text, SAMPLE_RATE])
        wav_path = os.path.join(self.cache_dir, f"{key}.wav")
        meta_path = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(wav_path) and os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            return wav_path, [tuple(x) for x in meta["chars"]], float(meta["duration"])

        tmp_dir = tempfile.mkdtemp(prefix="tts_")
        if self.provider == "elevenlabs":
            from elevenlabs import VoiceSettings
            from elevenlabs.core.api_error import ApiError

            res = None
            for attempt in range(max(1, len(self._keys))):
                try:
                    res = self._eleven().text_to_speech.convert_with_timestamps(
                        voice,
                        text=text,
                        model_id=self.model,
                        output_format="mp3_44100_128",
                        voice_settings=VoiceSettings(**settings),
                        previous_text=previous_text or None,
                        next_text=next_text or None,
                    )
                    break
                except ApiError as e:
                    detail = json.dumps(e.body)[:300] if e.body is not None else ""
                    if _is_quota_error(e.status_code, detail) and self._rotate_after_quota_error():
                        continue
                    if _is_quota_error(e.status_code, detail):
                        raise VoiceError(
                            f"ElevenLabs refused the request ({e.status_code}): {detail}. "
                            "Every configured key is out of characters."
                        ) from e
                    raise VoiceError(f"ElevenLabs TTS failed ({e.status_code}): {detail}") from e
            if res is None:
                raise VoiceError("ElevenLabs TTS failed after rotating every key")
            src = os.path.join(tmp_dir, "raw.mp3")
            with open(src, "wb") as f:
                f.write(base64.b64decode(res.audio_base_64))
            _ffmpeg_to_wav(src, wav_path)
            duration = len(_read_pcm(wav_path)) / 2 / SAMPLE_RATE
            al = res.alignment or res.normalized_alignment
            if al and al.characters:
                times = list(zip(al.character_start_times_seconds, al.character_end_times_seconds))
                chars = _spoken_chars(list(al.characters), times)
            else:
                chars = _estimate_chars(text, duration)
        else:
            txt = os.path.join(tmp_dir, "line.txt")
            aiff = os.path.join(tmp_dir, "line.aiff")
            with open(txt, "w", encoding="utf-8") as f:
                f.write(text)
            subprocess.run(["say", "-v", voice, "-r", "190", "-o", aiff, "-f", txt], check=True, capture_output=True, timeout=120)
            _ffmpeg_to_wav(aiff, wav_path)
            duration = len(_read_pcm(wav_path)) / 2 / SAMPLE_RATE
            chars = _estimate_chars(text, duration)

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"chars": chars, "duration": duration, "voice": voice, "provider": self.provider}, f)
        return wav_path, chars, duration

    def estimate_characters(self, screenplay: Dict[str, Any]) -> int:
        """Characters billed by ElevenLabs for a full voicing (tags included)."""
        last: Dict[str, str] = {}
        return sum(len(self._delivery_text(b, last)) for s in screenplay.get("scenes", []) for b in s.get("beats", []))

    def remaining_characters(self) -> Optional[int]:
        """Characters left on the active ElevenLabs key (None if unknown)."""
        if self.provider != "elevenlabs":
            return None
        return _quota_remaining(self._active_key(), self._key_index)

    def remaining_by_key(self) -> List[Dict[str, Any]]:
        """Quota snapshot for every configured key (safe labels only)."""
        out = []
        for i, key in enumerate(self._keys):
            out.append({
                "index": i,
                "label": _key_label(key, i),
                "remaining": _quota_remaining(key, i),
                "active": i == self._key_index,
            })
        return out

    def render(self, screenplay: Dict[str, Any], out_dir: str, *, seed: int = 0,
               cast: Optional[Dict[str, Dict[str, Any]]] = None) -> VoiceTrack:
        os.makedirs(out_dir, exist_ok=True)
        cast = cast or self.cast(screenplay, seed=seed)
        pcm = bytearray()

        def add_silence(seconds: float) -> None:
            pcm.extend(b"\x00\x00" * int(round(seconds * SAMPLE_RATE)))

        def now() -> float:
            return len(pcm) / 2 / SAMPLE_RATE

        add_silence(LEAD_IN)
        beats_out: List[Dict[str, Any]] = []
        scenes_out: List[Dict[str, Any]] = []
        last_tag: Dict[str, str] = {}
        index = 0
        for si, scene in enumerate(screenplay.get("scenes", [])):
            if si > 0:
                add_silence(GAP_BETWEEN_SCENES)
            scene_start = 0.0 if si == 0 else now() - GAP_BETWEEN_SCENES / 2
            beats = scene.get("beats", [])
            for bi, beat in enumerate(beats):
                if bi > 0:
                    add_silence(GAP_IN_SCENE)
                speaker = beat.get("speaker", "narrator")
                entry = cast.get(speaker) or cast["narrator"]
                tts_text = self._delivery_text(beat, last_tag)
                # Request stitching keeps one speaker's back-to-back lines sounding continuous.
                prev_text = strip_speech_tags(beats[bi - 1]["text"]) if bi > 0 and beats[bi - 1].get("speaker") == speaker else ""
                next_text = strip_speech_tags(beats[bi + 1]["text"]) if bi + 1 < len(beats) and beats[bi + 1].get("speaker") == speaker else ""
                wav_path, chars, _dur = self._synthesize(tts_text, entry["voice"], role=entry.get("role", "character"),
                                                         previous_text=prev_text, next_text=next_text)
                clip = _read_pcm(wav_path)

                # Trim leading/trailing silence using the character timings for snappy pacing.
                if chars:
                    cut_start = max(0.0, chars[0][1] - 0.06)
                    cut_end = min(len(clip) / 2 / SAMPLE_RATE, chars[-1][2] + 0.18)
                else:
                    cut_start, cut_end = 0.0, len(clip) / 2 / SAMPLE_RATE
                a = int(cut_start * SAMPLE_RATE) * 2
                b = max(a, int(cut_end * SAMPLE_RATE) * 2)
                start = now()
                pcm.extend(clip[a:b])
                offset = start - cut_start
                beats_out.append({
                    "index": index,
                    "scene": si,
                    "speaker": speaker,
                    "character": "op" if speaker == "narrator" else speaker,
                    "narration": speaker == "narrator",
                    "start": round(start, 3),
                    "end": round(now(), 3),
                    "text": strip_speech_tags(beat.get("text", "")),
                    "emotion": beat.get("emotion", "neutral"),
                    "action": beat.get("action", "talk"),
                    "camera": beat.get("camera", "wide"),
                    "words": words_from_chars(chars, offset),
                    "mouth": mouth_from_chars(chars, offset),
                })
                index += 1
            scenes_out.append({"index": si, "start": round(scene_start, 3), "end": None})

        add_silence(TAIL)
        total = now()
        for i, s in enumerate(scenes_out):
            s["end"] = round(scenes_out[i + 1]["start"] if i + 1 < len(scenes_out) else total, 3)

        wav_out = os.path.join(out_dir, "dialogue.wav")
        _write_pcm(wav_out, bytes(pcm))
        timeline = {"sampleRate": SAMPLE_RATE, "duration": round(total, 3), "scenes": scenes_out, "beats": beats_out}
        with open(os.path.join(out_dir, "timeline.json"), "w", encoding="utf-8") as f:
            json.dump(timeline, f, indent=1)
        return VoiceTrack(dialogue_wav=wav_out, timeline=timeline, cast=cast, provider=self.provider)


def list_elevenlabs_voices() -> List[Dict[str, Any]]:
    from elevenlabs import ElevenLabs

    keys = elevenlabs_api_keys()
    res = ElevenLabs(api_key=keys[0] if keys else None).voices.search(page_size=100)
    out = []
    for v in res.voices:
        labels = v.labels or {}
        out.append({"id": v.voice_id, "name": v.name, "category": v.category, "gender": labels.get("gender"),
                    "age": labels.get("age"), "accent": labels.get("accent"), "use_case": labels.get("use_case")})
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    p = argparse.ArgumentParser(description="Voice a screenplay (or list ElevenLabs voices)")
    p.add_argument("--list-voices", action="store_true", help="Print the ElevenLabs voices on your account")
    p.add_argument("--screenplay", help="screenplay.json to voice")
    p.add_argument("--out", default="voice_test", help="Output directory")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--estimate", action="store_true", help="Only print the cast and the characters it would bill")
    args = p.parse_args()

    if args.list_voices:
        for v in list_elevenlabs_voices():
            print(json.dumps(v))
        return
    if not args.screenplay:
        p.error("--screenplay is required")
    with open(args.screenplay, "r", encoding="utf-8") as f:
        sp = json.load(f)
    sp = sp.get("screenplay", sp)
    renderer = VoiceRenderer()
    if args.estimate:
        print(json.dumps(renderer.cast(sp, seed=args.seed), indent=1))
        print(f"~{renderer.estimate_characters(sp)} characters")
        return
    track = renderer.render(sp, args.out, seed=args.seed)
    print(json.dumps(track.cast, indent=1))
    print(f"{track.dialogue_wav} ({track.timeline['duration']:.1f}s, {len(track.timeline['beats'])} beats, provider={track.provider})")


if __name__ == "__main__":
    main()
