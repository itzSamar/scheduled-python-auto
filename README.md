# Animated Reddit Story Shorts

Turns family-friendly Reddit stories (malicious compliance, petty revenge, TIFU, retail and serving tales) into
60-90 second vertical animated Shorts: a cast of cartoon characters acts the story out in 2D, 3D or mixed scenes,
each character speaks with their own ElevenLabs voice, captions follow the words, and music sits underneath.
The autoposter uploads 4-5 a day to the RedditReviews channel and A/B-tests hooks, endings and render styles.

## How a video is made

1. **Pick a story.** In order: `--story-url`, `--screenplay`, the next file in `screenplays/queue/`, and only then
   an automatic pick from Reddit (via the Arctic Shift archive when reddit.com blocks the request) ranked by Ollama.
2. **Write the screenplay.** Queued screenplays are already written. Otherwise the local writers' room
   (`pipeline/story_director.py`) runs on Ollama: outline, draft, then up to two table reads that score hook,
   clarity, logic, comedy, dialogue, payoff, ending and pacing and revise until it ships.
3. **Safety check** (`pipeline/safety_filter.py`) keeps it family-friendly.
4. **Voices** (`pipeline/voice_renderer.py`): ElevenLabs `eleven_v4` with word timings, cast from
   `config/voices.json` by gender, age and tone. Audio is cached in `data/voice_cache/`, so re-renders are free.
5. **Animate** with Remotion + three.js in `animator/`, mix music from `assets/music/<mood>/`.
6. **Upload** with optimized title, description and tags; results go to `data/video_history.db`.

## Layout

```
main.py                one video, end to end
autoposter.py          daemon: 4-5 uploads per rolling 24h (launched by RunAutoPoster.command)
pipeline/              Python package (config, fetcher, writers' room, voices, render, upload, A/B optimizer)
animator/              Remotion project (kit.json lists every location, emotion, action and look it can draw)
config/                generator_config.json (A/B experiments, word counts), voices.json (ElevenLabs cast)
screenplays/queue/     hand-written screenplays, used first, in filename order
screenplays/used/      queue files after upload/rejection, with a result record
screenplays/examples/  reference screenplay
assets/music/          background music by mood: funny/, wholesome/, dramatic/, tense/
data/                  runtime state: history DB, used/rejected topics, autoposter state, voice cache
generated_videos/      rendered MP4s
logs/                  launcher logs
```

Old Minecraft-background pipeline, clipper, tests and old renders were moved to `../Youtube auto archive/`.

## Setup

Requirements: macOS, Python 3.9+, ffmpeg, Node 20 (nvm), Ollama.

```bash
pip3 install -r requirements.txt
cd animator && npm ci && cd ..
```

**ElevenLabs** (voices). Run this from the project root and follow what it prints; it stores the key in `.env.local`:

```bash
npx -y @elevenlabs/cli@latest onboard init
npx -y @elevenlabs/cli@latest onboard check --answered --env-path .env.local
```

The free plan gives 10,000 characters a month, and one Short uses about 1,100-1,200, so plan on a paid tier for
daily posting (paid tiers also carry the commercial license YouTube monetization needs).

**Ollama** (the automatic writer, used only when the queue is empty). Install the app from ollama.com, then:

```bash
ollama pull hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q3_K_XL
```

It needs about 13 GB of free memory and a full-power charger; override with `OLLAMA_MODEL=...` in `.env.local`.
The model is unloaded before each render so Remotion gets the memory back.

**YouTube**: put the OAuth desktop client as `client_secrets.json` in the root. The first upload opens a browser
to sign in; delete `youtube-oauth2.json` to sign in again.

**Buffer** (posts the same video to YouTube and TikTok): put `BUFFER_API_KEY` in `.env.local`. The key is in
Buffer → Settings → API, and it can see every channel on the account. Buffer does not accept a file upload,
so the mp4 has to be at a public HTTPS address when the post is created. `pipeline/buffer_client.py` sends
one `shareNow` post per channel. YouTube gets the title, Entertainment category, and not-for-kids. TikTok
gets a shorter caption. Both are marked as AI-assisted because the voices are synthetic.

## Commands

```bash
python3 main.py                                  # next queued screenplay (or auto-pick), render, upload
python3 main.py --skip-upload                    # render only, video lands in generated_videos/
python3 main.py --screenplay screenplays/queue/001_clock_out_at_five.json --skip-upload
python3 main.py --story-url https://www.reddit.com/r/.../comments/...   # write and render a chosen post
python3 main.py --dry-run                        # pick a story and write metadata, no voices or render
python3 main.py --analyze-trends --sync-stats    # what's working, from the history DB

python3 -m pipeline.story_director --story-url URL --out draft.json      # writers' room only
python3 -m pipeline.voice_renderer --screenplay FILE --estimate          # ElevenLabs characters it will cost
python3 -m pipeline.voice_renderer --list-voices                         # voices on the account

python3 autoposter.py                            # or double-click RunAutoPoster.command
```

## Writing a queued screenplay

Copy a file from `screenplays/queue/` (or `screenplays/examples/`) and keep the format:
`source` (the Reddit post), `screenplay` (title, mood, characters, scenes of beats), `render_style`
(`"2d"`, `"3d"`, `"mixed"` or `null` to let the A/B test choose). Rules the writers' room also enforces:

- Beat 1 is a narrator hook of at most 12 words; the last beat is the narrator asking one specific question.
- 170-230 spoken words, at least 40% of beats spoken by characters, never three narrator beats in a row.
- Only locations, emotions, actions and looks listed in `animator/src/kit.json`; up to 4 characters with id `op`
  for the poster (the narrator uses the poster's voice).
- Voice tags such as `[sighs]`, `[deadpan]`, `[shouting]` from `kit.json`, 3-6 per video.
