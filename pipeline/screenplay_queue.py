"""
Screenplays written ahead of time (by hand or by the Cursor agent), used before the local LLM writes one.

Each file in screenplays/queue/ is JSON:
  {
    "source": {"title", "subreddit", "url", "score", "num_comments", "text"},   # the Reddit post
    "screenplay": {...},                                                         # same shape the director writes
    "render_style": "mixed" | "2d" | "3d" | null,                                # null = A/B experiment decides
    "written_by": "...", "notes": "..."
  }
Files are used in filename order and moved to screenplays/used/ once uploaded (or rejected).
"""
import json
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import SCREENPLAY_QUEUE_DIR, SCREENPLAY_USED_DIR

logger = logging.getLogger(__name__)


@dataclass
class QueuedScreenplay:
    path: str
    trend_data: Dict[str, Any]
    screenplay: Dict[str, Any]
    render_style: Optional[str]


def _trend_from_source(src: Dict[str, Any], path: str) -> Dict[str, Any]:
    title = str(src.get("title") or "")
    text = str(src.get("text") or "")
    return {
        "title": title,
        "description": text[:1000],
        "text": text,
        "keywords": list(src.get("keywords") or []),
        "subreddit": str(src.get("subreddit") or ""),
        "score": src.get("score", 0) or 0,
        "num_comments": src.get("num_comments", 0) or 0,
        "url": str(src.get("url") or f"queue:{os.path.basename(path)}"),
        "_topic_title": title,
        "_queue_path": path,
    }


def pending() -> List[str]:
    if not os.path.isdir(SCREENPLAY_QUEUE_DIR):
        return []
    return sorted(
        os.path.join(SCREENPLAY_QUEUE_DIR, f)
        for f in os.listdir(SCREENPLAY_QUEUE_DIR)
        if f.endswith(".json") and not f.startswith(".")
    )


def load(path: str) -> QueuedScreenplay:
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    return QueuedScreenplay(
        path=path,
        trend_data=_trend_from_source(doc.get("source") or {}, path),
        screenplay=doc["screenplay"],
        render_style=doc.get("render_style"),
    )


def entries(skip_titles: Optional[set] = None) -> List[QueuedScreenplay]:
    out = []
    for p in pending():
        try:
            q = load(p)
        except Exception as e:
            logger.warning(f"Skipping unreadable queued screenplay {os.path.basename(p)}: {e}")
            continue
        if skip_titles and q.trend_data["title"].lower().strip() in skip_titles:
            continue
        out.append(q)
    return out


def mark_done(path: str, status: str, info: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Move a queued screenplay to screenplays/used/ with a record of what happened to it."""
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        doc["result"] = {"status": status, "at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), **(info or {})}
        os.makedirs(SCREENPLAY_USED_DIR, exist_ok=True)
        dest = os.path.join(SCREENPLAY_USED_DIR, os.path.basename(path))
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1, ensure_ascii=False)
        os.remove(path)
        return dest
    except Exception as e:
        logger.warning(f"Could not move {path} to used/: {e}")
        try:
            shutil.move(path, os.path.join(SCREENPLAY_USED_DIR, os.path.basename(path)))
        except Exception:
            pass
        return None
