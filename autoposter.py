#!/usr/bin/env python3
"""
Autonomous uploader daemon.

Runs forever, scheduling 4–5 uploads per rolling 24h window.
Keeps state on disk, sleeps most of the time, and calls main.py for real uploads.
"""

import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pipeline.config import AUTOPOSTER_LOCK_PATH, AUTOPOSTER_STATE_PATH, HISTORY_DB_PATH, ROOT
from pipeline.history_db import HistoryDB


STATE_PATH_DEFAULT = AUTOPOSTER_STATE_PATH
LOCK_PATH_DEFAULT = AUTOPOSTER_LOCK_PATH


def _now_local() -> datetime:
    return datetime.now().astimezone()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().replace(microsecond=0).isoformat()


def _parse_iso(dt: str) -> datetime:
    return datetime.fromisoformat(dt.replace("Z", "+00:00"))


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def _acquire_lock(lock_path: str) -> None:
    """
    Prevent multiple autoposter instances.
    Stores PID in lock file; if PID is alive, exit.
    """
    try:
        if os.path.exists(lock_path):
            try:
                with open(lock_path, "r", encoding="utf-8") as f:
                    pid_str = (f.read() or "").strip()
                pid = int(pid_str) if pid_str else None
            except Exception:
                pid = None
            if pid:
                try:
                    os.kill(pid, 0)  # type: ignore[arg-type]
                    print(f"autoposter already running (pid {pid}). Exiting.")
                    sys.exit(0)
                except Exception:
                    # stale lock
                    pass
        with open(lock_path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        # If we can't lock, we still run (best-effort).
        pass


def _load_json(path: str, default: Any) -> Any:
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, data: Any) -> None:
    _ensure_dir(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _pick_target_count() -> int:
    # Monetization-first default: maximize volume within your 4–5/day rule.
    return 5


def _schedule_times_for_day(
    start_local: datetime,
    *,
    count: int,
    window_start_hour: int = 10,
    window_end_hour: int = 22,
) -> List[str]:
    """
    Schedule `count` uploads over the next ~24h, but concentrated in a local-time window.
    Returns list of ISO datetimes (with tz offset).
    """
    if count <= 0:
        return []

    # Define window today + tomorrow to always fill next 24h.
    day0 = start_local.replace(minute=0, second=0, microsecond=0)
    win0_start = day0.replace(hour=window_start_hour)
    win0_end = day0.replace(hour=window_end_hour)
    if win0_end <= win0_start:
        win0_end = win0_start + timedelta(hours=12)

    # If we're already past today's window end, schedule in tomorrow's window.
    if start_local >= win0_end:
        win0_start = (win0_start + timedelta(days=1))
        win0_end = (win0_end + timedelta(days=1))
    # If we're before window start, start at window start.
    if start_local < win0_start:
        base_start = win0_start
    else:
        base_start = start_local

    span_seconds = max(60, int((win0_end - base_start).total_seconds()))
    step = span_seconds / count
    out: List[datetime] = []
    for i in range(count):
        # Even spacing + jitter
        t = base_start + timedelta(seconds=(step * i))
        jitter = random.randint(-20 * 60, 20 * 60)  # +/- 20 min
        t = t + timedelta(seconds=jitter)
        # Clamp to window
        if t < win0_start:
            t = win0_start + timedelta(minutes=random.randint(0, 15))
        if t > win0_end:
            t = win0_end - timedelta(minutes=random.randint(0, 15))
        out.append(t)

    # Sort and enforce minimum spacing ~90 minutes
    out.sort()
    spaced: List[datetime] = []
    for t in out:
        if not spaced:
            spaced.append(t)
            continue
        if (t - spaced[-1]).total_seconds() < 90 * 60:
            t = spaced[-1] + timedelta(minutes=95 + random.randint(0, 20))
        spaced.append(t)

    return [t.isoformat() for t in spaced]


def _framework_python_fallback() -> str:
    fw = "/Library/Frameworks/Python.framework/Versions/3.9/bin/python3"
    return fw if os.path.exists(fw) else sys.executable


def _run_one_upload(*, python: str, history_db: str) -> int:
    """
    Call main.py for a real default upload.
    """
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    cmd = [python, os.path.join(ROOT, "main.py"), "--history-db", history_db]
    p = subprocess.run(cmd, env=env, cwd=ROOT)
    return int(p.returncode)


def _sleep_seconds_until(next_iso: str) -> float:
    dt = _parse_iso(next_iso).astimezone()
    return max(0.0, (dt - _now_local()).total_seconds())


def run_daemon(
    *,
    history_db_path: str = HISTORY_DB_PATH,
    state_path: str = STATE_PATH_DEFAULT,
    python_path: Optional[str] = None,
    lock_path: str = LOCK_PATH_DEFAULT,
    uploads_per_24h: int = 5,
    check_interval_seconds: int = 30,
) -> None:
    python = python_path or _framework_python_fallback()
    history = HistoryDB(db_path=history_db_path)
    _acquire_lock(lock_path)

    state: Dict[str, Any] = _load_json(state_path, default={}) or {}
    if "plan" not in state:
        state["plan"] = {}

    while True:
        now = _now_local()
        plan = state.get("plan") or {}

        # Refresh plan if missing/empty/expired
        sched = plan.get("schedule_times") or []
        plan_start = plan.get("plan_start_local")
        if not sched:
            target = int(uploads_per_24h)
            if target < 1:
                target = 1
            if target > 8:
                target = 8
            times = _schedule_times_for_day(now, count=target)
            plan = {
                "plan_start_local": now.replace(microsecond=0).isoformat(),
                "target_uploads": target,
                "schedule_times": times,
                "completed": [],
                "last_error": None,
                "last_run_at": None,
            }
            state["plan"] = plan
            _save_json(state_path, state)

        # If we're already meeting target for last 24h, just wait until next check.
        since_utc = (_utc_now() - timedelta(hours=24)).replace(microsecond=0).isoformat()
        success_24h = history.count_success_uploads_since(since_utc)
        target_uploads = int((plan.get("target_uploads") or uploads_per_24h or 5))
        if success_24h >= target_uploads:
            time.sleep(check_interval_seconds)
            continue

        # Determine next scheduled time
        sched = plan.get("schedule_times") or []
        next_time = sched[0] if sched else None
        if not next_time:
            # Plan was consumed but we still need more uploads → re-plan.
            plan["schedule_times"] = []
            state["plan"] = plan
            _save_json(state_path, state)
            time.sleep(1)
            continue

        sleep_s = _sleep_seconds_until(next_time)
        if sleep_s > check_interval_seconds:
            time.sleep(check_interval_seconds)
            continue

        # It's time (or overdue) — attempt upload
        rc = _run_one_upload(python=python, history_db=history_db_path)
        plan["last_run_at"] = now.replace(microsecond=0).isoformat()

        if rc == 0:
            # Success: pop schedule
            plan["completed"] = (plan.get("completed") or []) + [next_time]
            plan["schedule_times"] = sched[1:]
            plan["last_error"] = None
            state["plan"] = plan
            _save_json(state_path, state)
            # Small cooldown to avoid double triggering
            time.sleep(60)
        else:
            # Failure: backoff and retry later, but keep schedule entry.
            plan["last_error"] = {"time": _utc_now_iso(), "return_code": rc}
            state["plan"] = plan
            _save_json(state_path, state)
            time.sleep(20 * 60)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Autonomous YouTube uploader daemon (4–5 uploads per 24h)")
    parser.add_argument("--history-db", default=HISTORY_DB_PATH)
    parser.add_argument("--state-path", default=STATE_PATH_DEFAULT)
    parser.add_argument("--python", dest="python_path", default=None, help="Python interpreter to run main.py")
    parser.add_argument("--check-interval", type=int, default=30)
    parser.add_argument("--lock-path", default=LOCK_PATH_DEFAULT)
    parser.add_argument(
        "--uploads-per-24h",
        type=int,
        default=5,
        help="Target uploads per rolling 24 hours (default: 5, allowed 4–5 recommended)",
    )
    args = parser.parse_args()

    run_daemon(
        history_db_path=args.history_db,
        state_path=args.state_path,
        python_path=args.python_path,
        lock_path=args.lock_path,
        uploads_per_24h=int(args.uploads_per_24h),
        check_interval_seconds=int(args.check_interval),
    )


if __name__ == "__main__":
    main()

