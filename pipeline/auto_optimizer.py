import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .config import GENERATOR_CONFIG_PATH, HISTORY_DB_PATH
from .history_db import HistoryDB, VideoRun


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


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


def load_generator_config(path: str = GENERATOR_CONFIG_PATH) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f) or {}


def save_generator_config(cfg: Dict[str, Any], path: str = GENERATOR_CONFIG_PATH) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _softmax(xs: List[float], temperature: float = 1.0) -> List[float]:
    if not xs:
        return []
    t = max(1e-6, float(temperature))
    m = max(xs)
    exps = [math.exp((x - m) / t) for x in xs]
    s = sum(exps) or 1.0
    return [e / s for e in exps]


def _get_variant_id(run: VideoRun, exp_name: str) -> Optional[str]:
    exp = (run.experiment_json or {}) if hasattr(run, "experiment_json") else (run.stats_json or {})
    # Backward compatible: store experiment under last_generation_info as "experiment"
    # Expected shape:
    # { "variants": { "hook_tease_style": {"id": "..."}, "ending_question_style": {"id": "..."} } }
    if isinstance(exp, dict):
        variants = exp.get("variants") or exp.get("variant") or exp.get("experiments")
        if isinstance(variants, dict):
            v = variants.get(exp_name)
            if isinstance(v, dict) and v.get("id"):
                return str(v.get("id"))
            if isinstance(v, str):
                return v
        # Or flattened:
        key = f"{exp_name}.id"
        if key in exp:
            return str(exp.get(key))
    return None


def auto_optimize_generator_config(
    *,
    db_path: str = HISTORY_DB_PATH,
    config_path: str = GENERATOR_CONFIG_PATH,
    min_samples_per_variant: int = 2,
    lookback_runs: int = 200,
) -> Dict[str, Any]:
    """
    Update experiment weights in generator_config.json based on performance.
    Primary metric: views/day (requires stats sync).
    If stats are missing, it will NOT change weights (to avoid random drift).
    """
    db = HistoryDB(db_path=db_path)
    runs = db.get_recent_runs(limit=lookback_runs)
    cfg = load_generator_config(config_path) or {}
    exps = (cfg.get("experiments") or {})

    updated_any = False
    changes: Dict[str, Any] = {"updated_at": _utc_now_iso(), "updated": []}

    for exp_name, exp_def in exps.items():
        variants = exp_def.get("variants") or []
        if not variants:
            continue

        # Gather scores by variant id
        by_variant: Dict[str, List[float]] = {v.get("id"): [] for v in variants if v.get("id")}
        for r in runs:
            v_id = None
            # Experiment info is stored in HistoryDB experiment_json (we set it in main)
            exp_json = getattr(r, "experiment_json", None)
            if exp_json is None:
                exp_json = r.stats_json  # noop fallback
            if isinstance(exp_json, dict):
                variants_json = exp_json.get("variants")
                if isinstance(variants_json, dict):
                    v = variants_json.get(exp_name)
                    if isinstance(v, dict) and v.get("id"):
                        v_id = str(v.get("id"))
            if not v_id:
                continue

            vpd = _views_per_day(r)
            if vpd is None:
                continue
            if v_id in by_variant:
                by_variant[v_id].append(float(vpd))

        # Only update if we have enough stats to be meaningful.
        if all(len(scores) < min_samples_per_variant for scores in by_variant.values()):
            continue

        # Score each variant using median views/day (robust).
        scored: List[Tuple[str, float, int]] = []
        for v in variants:
            vid = v.get("id")
            if not vid:
                continue
            scores = sorted(by_variant.get(vid) or [])
            if len(scores) == 0:
                continue
            median = scores[len(scores) // 2]
            scored.append((vid, float(median), len(scores)))

        if len(scored) < 2:
            continue

        scored.sort(key=lambda t: t[1], reverse=True)
        vals = [s for _, s, _ in scored]
        weights = _softmax(vals, temperature=0.6)
        new_w = {vid: w for (vid, _, _), w in zip(scored, weights)}

        # Apply new weights back into cfg (keep small floor so exploration continues).
        floor = 0.05
        total = 0.0
        for v in variants:
            vid = v.get("id")
            if not vid:
                continue
            w = new_w.get(vid)
            if w is None:
                continue
            w = max(floor, float(w))
            v["weight"] = w
            total += w
        if total > 0:
            for v in variants:
                if v.get("id") and isinstance(v.get("weight"), (int, float)):
                    v["weight"] = float(v["weight"]) / total

        updated_any = True
        changes["updated"].append(
            {
                "experiment": exp_name,
                "variant_medians": [{"id": vid, "median_views_per_day": s, "n": n} for vid, s, n in scored],
                "new_weights": {k: round(v, 4) for k, v in new_w.items()},
            }
        )

    if updated_any:
        cfg["_auto_optimized_at"] = _utc_now_iso()
        cfg["_auto_optimization_notes"] = "Weights updated from median views/day across recent runs with synced stats."
        save_generator_config(cfg, config_path)
    return changes

