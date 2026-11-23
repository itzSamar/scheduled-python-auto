"""
Synthetic episode covering every location, emotion, action and shot, for visual QA of the kit.

  python3 animator/scripts/make_gallery.py out.json [2d|3d|mixed] [a|b]   # b = alternate cast
  node animator/scripts/stills.mjs out_dir --props=out.json <frames...>  # frames are printed by this script
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from pipeline.story_director import load_kit  # noqa: E402

kit = load_kit()
style = sys.argv[2] if len(sys.argv) > 2 else "2d"
out = sys.argv[1]

characters = [
    {"id": "op", "name": "Sam", "gender": "female", "age": "20s", "voiceTone": "bright",
     "look": {"hair": "ponytail", "hairColor": "#3b2417", "skin": "#e9b48f", "outfit": "hoodie", "outfitColor": "#3a7bd5", "accessory": "none"}},
    {"id": "grandpa", "name": "Grandpa Joe", "gender": "male", "age": "elderly", "voiceTone": "raspy",
     "look": {"hair": "bald", "hairColor": "#d9d9d9", "skin": "#f1c7a5", "outfit": "sweater", "outfitColor": "#2a9d8f", "accessory": "glasses"}},
    {"id": "kid", "name": "Mia", "gender": "female", "age": "kid", "voiceTone": "sweet",
     "look": {"hair": "curly", "hairColor": "#1d1720", "skin": "#8d5a3b", "outfit": "tshirt", "outfitColor": "#f2b134", "accessory": "none"}},
    {"id": "boss", "name": "Mr. Kent", "gender": "male", "age": "40s", "voiceTone": "stern",
     "look": {"hair": "spiky", "hairColor": "#c4622d", "skin": "#f3d2b8", "outfit": "suit", "outfitColor": "#3d3d5c", "accessory": "cap"}},
]
if len(sys.argv) > 3 and sys.argv[3] == "b":
    characters = [
        {"id": "op", "name": "Leo", "gender": "male", "age": "30s", "voiceTone": "warm",
         "look": {"hair": "short", "hairColor": "#2b1a10", "skin": "#c68a63", "outfit": "uniform", "outfitColor": "#d9534f", "accessory": "beard"}},
        {"id": "grandpa", "name": "Linda", "gender": "female", "age": "50s", "voiceTone": "stern",
         "look": {"hair": "bun", "hairColor": "#9a9a9a", "skin": "#f1c7a5", "outfit": "dress", "outfitColor": "#8e5bd6", "accessory": "glasses"}},
        {"id": "kid", "name": "Zoe", "gender": "female", "age": "teen", "voiceTone": "energetic",
         "look": {"hair": "long", "hairColor": "#e0b04a", "skin": "#f3d2b8", "outfit": "apron", "outfitColor": "#2a9d8f", "accessory": "none"}},
        {"id": "boss", "name": "Ava", "gender": "female", "age": "20s", "voiceTone": "bright",
         "look": {"hair": "bob", "hairColor": "#b8442e", "skin": "#5c3a26", "outfit": "suit", "outfitColor": "#1f2937", "accessory": "none"}},
    ]
ids = [c["id"] for c in characters]
emotions = kit["emotions"]
actions = kit["actions"]
shots = kit["shots"]
mouth_cycle = ["closed", "mid", "open", "wide", "round", "teeth", "mid", "open"]

scenes, beats = [], []
t = 0.0
tl_scenes = []
bi = 0
for si, loc in enumerate(kit["locations"]):
    tod = kit["timesOfDay"][si % 3]
    onscreen = ["op"] if loc == "car" else ids[: 2 + si % 3]
    if loc == "car":
        onscreen = ["op", "grandpa"]
    sc_beats = []
    start = t
    for k in range(4):
        speaker = onscreen[k % len(onscreen)]
        emo = emotions[bi % len(emotions)]
        act = actions[bi % len(actions)]
        if act == "walk_in" and k == 0:
            act = "wave"
        shot = shots[bi % len(shots)]
        camera = shot if shot == "wide" else f"{shot}:{speaker}"
        text = f"{emo} {act} {shot} line number {bi}"
        b0 = t + 0.2
        b1 = b0 + 1.8
        words = []
        ws = text.split()
        for wi, w in enumerate(ws):
            ws0 = b0 + wi * (b1 - b0) / len(ws)
            words.append({"text": w, "start": round(ws0, 3), "end": round(ws0 + (b1 - b0) / len(ws), 3)})
        mouth = [[round(b0 + j * 0.09, 3), mouth_cycle[j % len(mouth_cycle)]] for j in range(int((b1 - b0) / 0.09))]
        beats.append({"index": bi, "scene": si, "speaker": speaker, "character": speaker, "narration": False,
                      "start": round(b0, 3), "end": round(b1, 3), "text": text, "emotion": emo, "action": act,
                      "camera": camera, "words": words, "mouth": mouth})
        sc_beats.append({"speaker": speaker, "text": text, "emotion": emo, "action": act, "camera": camera})
        t = b1 + 0.2
        bi += 1
    scenes.append({"location": loc, "timeOfDay": tod, "onscreen": onscreen, "beats": sc_beats})
    tl_scenes.append({"index": si, "start": round(start, 3), "end": round(t, 3)})

episode = {
    "screenplay": {"title": "Kit gallery", "mood": "funny", "characters": characters, "scenes": scenes},
    "timeline": {"sampleRate": 48000, "duration": round(t, 3), "scenes": tl_scenes, "beats": beats},
    "style": style,
    "audioSrc": None,
    "subreddit": "test",
    "seed": 3,
}
json.dump(episode, open(out, "w"), indent=1)
# Print a frame in the middle of each beat (30 fps) for stills.
print(" ".join(str(int(((b["start"] + b["end"]) / 2) * 30)) for b in beats))
