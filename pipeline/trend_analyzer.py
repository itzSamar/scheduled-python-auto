import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .config import HISTORY_DB_PATH
from .history_db import HistoryDB, VideoRun
from .llm_client import LLMError, OllamaClient


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _chunked(xs: List[str], n: int) -> List[List[str]]:
    return [xs[i : i + n] for i in range(0, len(xs), n)]


def ollama_available() -> bool:
    return OllamaClient().available(timeout=1.5)


def ollama_pick_model(preferred: Optional[str] = None) -> Optional[str]:
    """
    Returns a model name available in local Ollama, or None if unreachable/empty.
    """
    client = OllamaClient()
    models = client.models()
    if not models:
        return None
    for candidate in (preferred, client.fast_model, client.model):
        if candidate and client.has_model(candidate):
            return candidate
    return models[0]


def ollama_chat(prompt: str, model: str, temperature: float = 0.2) -> Optional[str]:
    try:
        text = OllamaClient().chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a YouTube Shorts growth analyst. "
                        "Be brutally practical. Give concrete, testable changes. "
                        "No fluff."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            model=model,
            temperature=temperature,
            think=False,
            num_ctx=8192,
            num_predict=2048,
            timeout=300,
        )
        return text.strip() or None
    except LLMError:
        return None


def _has_hook(script: str) -> bool:
    s = (script or "").strip()
    if not s:
        return False
    first = s.split("\n", 1)[0]
    # Hook heuristics: question, strong verb, or "I ..." personal setup, or "AITA"/"TIFU"
    if "?" in first:
        return True
    if re.match(r"^(aita|tifu|wibta|am i)\b", first.strip().lower()):
        return True
    if first.strip().startswith(("I ", "My ", "We ", "He ", "She ")):
        return True
    if re.search(r"\b(stop scrolling|wait|listen|hold up)\b", first.lower()):
        return True
    return len(first.split()) <= 18


def _has_clean_ending(script: str) -> bool:
    s = (script or "").strip()
    if not s:
        return False
    # Clean ending: ends on punctuation and has an ending cue (question or "so/now/in the end")
    if not s.endswith((".", "!", "?")):
        return False
    tail = s[-220:].lower()
    return bool(
        ("what would you do" in tail)
        or ("was i wrong" in tail)
        or ("am i the" in tail)
        or ("in the end" in tail)
        or ("so now" in tail)
        or ("so" in tail and "?" in tail)
    )


def _basic_aggregate(runs: List[VideoRun]) -> Dict[str, Any]:
    wc = [len((r.script or "").split()) for r in runs if r.script]
    dur = [float(r.video_duration_seconds) for r in runs if r.video_duration_seconds]
    hooks = sum(1 for r in runs if _has_hook(r.script))
    clean_end = sum(1 for r in runs if _has_clean_ending(r.script))

    title_words = Counter()
    for r in runs:
        for w in re.findall(r"[a-zA-Z']{4,}", (r.title or "").lower()):
            if w in {"this", "that", "with", "from", "your", "have", "they", "what", "when", "here", "just"}:
                continue
            title_words[w] += 1

    return {
        "count": len(runs),
        "avg_word_count": (sum(wc) / len(wc)) if wc else None,
        "avg_duration_seconds": (sum(dur) / len(dur)) if dur else None,
        "hook_rate": (hooks / len(runs)) if runs else 0.0,
        "clean_ending_rate": (clean_end / len(runs)) if runs else 0.0,
        "common_title_words": title_words.most_common(12),
    }

def _parse_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(x)
    except Exception:
        return None


def _views_per_day(run: VideoRun) -> Optional[float]:
    stats = run.stats_json or {}
    views = _parse_int(stats.get("viewCount"))
    published_at = stats.get("publishedAt")
    if views is None or not published_at:
        return None
    try:
        published = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
        age_days = max(1.0, (datetime.now(timezone.utc) - published.astimezone(timezone.utc)).total_seconds() / 86400.0)
        return float(views) / age_days
    except Exception:
        return None


def render_trend_report(
    db_path: str = HISTORY_DB_PATH,
    limit: int = 50,
    use_ollama: bool = True,
    ollama_model: Optional[str] = None,
) -> str:
    db = HistoryDB(db_path=db_path)
    runs = db.get_recent_runs(limit=limit)
    if not runs:
        return "No history yet. Run `python3 main.py` at least once to start collecting data."

    agg = _basic_aggregate(runs)
    lines: List[str] = []
    lines.append("## Trend analysis (local history)")
    lines.append(f"- Runs analyzed: **{agg['count']}**")
    if agg["avg_word_count"] is not None:
        lines.append(f"- Avg script length: **{agg['avg_word_count']:.0f} words**")
    if agg["avg_duration_seconds"] is not None:
        lines.append(f"- Avg final duration: **{agg['avg_duration_seconds']:.1f}s**")
    lines.append(f"- Hook coverage: **{agg['hook_rate']*100:.0f}%**")
    lines.append(f"- Clean ending coverage: **{agg['clean_ending_rate']*100:.0f}%**")
    if agg["common_title_words"]:
        lines.append("- Common title words: " + ", ".join([f"`{w}`({c})" for w, c in agg["common_title_words"]]))

    # Performance ranking if stats exist
    scored: List[Tuple[float, VideoRun]] = []
    for r in runs:
        vpd = _views_per_day(r)
        if vpd is not None:
            scored.append((vpd, r))
    scored.sort(key=lambda t: t[0], reverse=True)

    if scored:
        lines.append("\n## Performance (views/day from synced stats)")
        lines.append("Top 5:")
        for vpd, r in scored[:5]:
            lines.append(f"- **{vpd:.0f}/day** `{r.run_id}`: {r.title[:80]}")
        lines.append("Bottom 5:")
        for vpd, r in scored[-5:]:
            lines.append(f"- **{vpd:.0f}/day** `{r.run_id}`: {r.title[:80]}")

        # Compare hook/ending presence against performance
        top = [r for _, r in scored[: max(1, len(scored)//3)]]
        bottom = [r for _, r in scored[-max(1, len(scored)//3):]]
        top_hook = sum(1 for r in top if _has_hook(r.script)) / max(1, len(top))
        bot_hook = sum(1 for r in bottom if _has_hook(r.script)) / max(1, len(bottom))
        top_end = sum(1 for r in top if _has_clean_ending(r.script)) / max(1, len(top))
        bot_end = sum(1 for r in bottom if _has_clean_ending(r.script)) / max(1, len(bottom))
        lines.append("\nHook/ending quality vs performance (heuristic):")
        lines.append(f"- Top third hook rate: **{top_hook*100:.0f}%** vs bottom third: **{bot_hook*100:.0f}%**")
        lines.append(f"- Top third clean-ending rate: **{top_end*100:.0f}%** vs bottom third: **{bot_end*100:.0f}%**")

    # Show a few concrete examples (worst offenders)
    no_hook = [r for r in runs if not _has_hook(r.script)]
    abrupt = [r for r in runs if not _has_clean_ending(r.script)]
    if no_hook:
        lines.append("\n## Scripts missing hooks (examples)")
        for r in no_hook[:5]:
            lines.append(f"- `{r.run_id}`: {r.topic_title[:90]}")
    if abrupt:
        lines.append("\n## Scripts with abrupt endings (examples)")
        for r in abrupt[:5]:
            lines.append(f"- `{r.run_id}`: {r.topic_title[:90]}")

    if use_ollama and ollama_available():
        model = ollama_pick_model(ollama_model)
        if model:
            # Keep prompt size under control: summarize only a handful of runs.
            sample = runs[: min(12, len(runs))]
            sample_blocks: List[str] = []
            for r in sample:
                stats = r.stats_json or {}
                sample_blocks.append(
                    "\n".join(
                        [
                            f"RUN {r.run_id}",
                            f"topic: {r.topic_title}",
                            f"title: {r.title}",
                            f"hashtags: {', '.join(r.hashtags or [])}",
                            f"duration_s: {r.video_duration_seconds}",
                            f"views: {stats.get('viewCount')}",
                            f"likes: {stats.get('likeCount')}",
                            f"comments: {stats.get('commentCount')}",
                            f"script: {r.script[:650]}",
                        ]
                    )
                )
            prompt = (
                "We are running a Reddit-stories YouTube Shorts channel.\n"
                "Analyze these recent runs. Identify patterns of what seems better/worse.\n"
                "Focus on: hook quality, pacing, clarity, endings, titles, and hashtags.\n"
                "Output:\n"
                "1) 5 specific problems you see (with examples by RUN id)\n"
                "2) 8 concrete changes to the generator (rules/templates) to improve retention\n"
                "3) A/b tests: 5 experiments we should run next week\n"
                "Keep it concise.\n\n"
                + "\n\n".join(sample_blocks)
            )
            ai = ollama_chat(prompt, model=model, temperature=0.2)
            if ai:
                lines.append("\n## Ollama recommendations")
                lines.append(f"- Model: `{model}`")
                lines.append(ai)
            else:
                lines.append("\n## Ollama recommendations")
                lines.append("- Ollama reachable, but the model call failed. Falling back to heuristic suggestions below.")
        else:
            lines.append("\n## Ollama recommendations")
            lines.append("- Ollama reachable, but no models were found (`ollama pull qwen3.8:27b`).")
    else:
        lines.append("\n## Ollama recommendations")
        lines.append("- Ollama not detected. If you want AI analysis: install + run Ollama, then `ollama pull qwen3.8:27b`.")

    # Always include deterministic changes (so this works even without AI).
    lines.append("\n## Generator improvements to implement now")
    lines.append("- **Hook rule**: First 2 sentences must be (1) story premise + (2) retention tease (no generic filler).")
    lines.append("- **Ending rule**: Last 2 sentences must be (1) what happened / outcome + (2) a single direct question for comments.")
    lines.append("- **Trim rule**: Never trim off the ending—trim the middle first, then re-attach a short ending.")
    lines.append("- **Pacing rule**: Keep sentences short (8–16 words); avoid big copy-paste paragraphs from Reddit.")

    return "\n".join(lines).strip() + "\n"

