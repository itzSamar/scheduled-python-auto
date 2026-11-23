import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import HISTORY_DB_PATH


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def _json_loads(s: Optional[str]) -> Any:
    if not s:
        return None
    return json.loads(s)


@dataclass
class VideoRun:
    run_id: str
    created_at: str
    region: str
    subreddit: str
    topic_title: str
    trend_data: Dict[str, Any]
    script: str
    title: str
    description: str
    tags: List[str]
    hashtags: List[str]
    privacy_status: str
    category_id: str
    output_path: Optional[str] = None
    video_duration_seconds: Optional[float] = None
    voice_provider: Optional[str] = None
    voice_config: Optional[Dict[str, Any]] = None
    background_pot_url: Optional[str] = None
    background_source_type: Optional[str] = None
    background_source_id: Optional[str] = None
    background_start_seconds: Optional[float] = None
    background_duration_seconds: Optional[float] = None
    music_volume_multiplier: Optional[float] = None
    experiment_json: Optional[Dict[str, Any]] = None
    moderation_json: Optional[Dict[str, Any]] = None
    moderation_status: Optional[str] = None  # pass|fail
    upload_status: str = "pending"  # pending|skipped|success|failed
    upload_time: Optional[str] = None
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None
    stats_json: Optional[Dict[str, Any]] = None
    stats_fetched_at: Optional[str] = None


class HistoryDB:
    """
    SQLite-backed history store for every run.
    Keeps enough detail to later correlate scripts/metadata/settings with performance.
    """

    def __init__(self, db_path: str = HISTORY_DB_PATH):
        self.db_path = db_path
        self._ensure_parent_dir()
        self._init_db()

    def _ensure_parent_dir(self) -> None:
        parent = os.path.dirname(os.path.abspath(self.db_path))
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS video_runs (
                  run_id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL,
                  region TEXT,
                  subreddit TEXT,
                  topic_title TEXT,
                  trend_data_json TEXT,
                  script TEXT,
                  script_word_count INTEGER,
                  title TEXT,
                  description TEXT,
                  tags_json TEXT,
                  hashtags_json TEXT,
                  privacy_status TEXT,
                  category_id TEXT,
                  output_path TEXT,
                  video_duration_seconds REAL,
                  voice_provider TEXT,
                  voice_config_json TEXT,
                  background_pot_url TEXT,
                  background_source_type TEXT,
                  background_source_id TEXT,
                  background_start_seconds REAL,
                  background_duration_seconds REAL,
                  music_volume_multiplier REAL,
                  experiment_json TEXT,
                  moderation_json TEXT,
                  moderation_status TEXT,
                  upload_status TEXT,
                  upload_time TEXT,
                  youtube_video_id TEXT,
                  youtube_url TEXT,
                  stats_json TEXT,
                  stats_fetched_at TEXT
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_video_runs_created_at ON video_runs(created_at)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_video_runs_youtube_video_id ON video_runs(youtube_video_id)"
            )

            # ----------------------------
            # Clipper-bot tables (OpusClip)
            # ----------------------------
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS source_videos (
                  source_video_id TEXT PRIMARY KEY,
                  source_channel TEXT NOT NULL,
                  youtube_video_id TEXT NOT NULL UNIQUE,
                  youtube_url TEXT,
                  title TEXT,
                  published_at TEXT,
                  duration_seconds REAL,
                  status TEXT NOT NULL, -- discovered|queued|processing|complete|failed|skipped
                  discovered_at TEXT NOT NULL,
                  updated_at TEXT
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_source_videos_status ON source_videos(status)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_source_videos_channel ON source_videos(source_channel)"
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS opus_projects (
                  project_id TEXT PRIMARY KEY,
                  org_id TEXT,
                  source_video_id TEXT NOT NULL,
                  stage TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT,
                  raw_json TEXT,
                  FOREIGN KEY(source_video_id) REFERENCES source_videos(source_video_id)
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_opus_projects_source_video_id ON opus_projects(source_video_id)"
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS opus_clips (
                  clip_id TEXT PRIMARY KEY,
                  project_id TEXT NOT NULL,
                  quality_score REAL,
                  duration_ms INTEGER,
                  uri_for_export TEXT NOT NULL,
                  uri_for_preview TEXT,
                  time_ranges_json TEXT,
                  title TEXT,
                  description TEXT,
                  hashtags TEXT,
                  created_at TEXT NOT NULL,
                  downloaded_path TEXT,
                  downloaded_at TEXT,
                  selected_status TEXT, -- candidate|selected|rejected
                  posted_status TEXT,   -- pending|success|failed|skipped
                  raw_json TEXT,
                  FOREIGN KEY(project_id) REFERENCES opus_projects(project_id)
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_opus_clips_project_id ON opus_clips(project_id)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_opus_clips_selected_status ON opus_clips(selected_status)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_opus_clips_posted_status ON opus_clips(posted_status)"
            )

            con.execute(
                """
                CREATE TABLE IF NOT EXISTS posted_clips (
                  clip_id TEXT PRIMARY KEY,
                  youtube_video_id TEXT,
                  youtube_url TEXT,
                  upload_status TEXT NOT NULL, -- pending|success|failed|skipped
                  upload_time TEXT,
                  publish_time TEXT,
                  stats_json TEXT,
                  stats_fetched_at TEXT,
                  FOREIGN KEY(clip_id) REFERENCES opus_clips(clip_id)
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_posted_clips_upload_status ON posted_clips(upload_status)"
            )
            # Compilation tracking (long-form posts made from shorts)
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS compilations (
                  compilation_id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL,
                  number INTEGER NOT NULL,
                  title TEXT,
                  description TEXT,
                  output_path TEXT,
                  thumbnail_path TEXT,
                  upload_status TEXT,
                  upload_time TEXT,
                  youtube_video_id TEXT,
                  youtube_url TEXT
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_compilations_number ON compilations(number)"
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS compilation_items (
                  compilation_id TEXT NOT NULL,
                  run_id TEXT NOT NULL UNIQUE,
                  position INTEGER,
                  created_at TEXT NOT NULL,
                  PRIMARY KEY (compilation_id, run_id)
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_compilation_items_compilation_id ON compilation_items(compilation_id)"
            )
            self._migrate_schema(con)

    def _migrate_schema(self, con: sqlite3.Connection) -> None:
        """
        Lightweight migrations for existing DBs.
        """
        try:
            cols = [r["name"] for r in con.execute("PRAGMA table_info(video_runs)").fetchall()]
        except Exception:
            cols = []

        if "experiment_json" not in cols:
            try:
                con.execute("ALTER TABLE video_runs ADD COLUMN experiment_json TEXT")
            except Exception:
                pass
        if "background_source_type" not in cols:
            try:
                con.execute("ALTER TABLE video_runs ADD COLUMN background_source_type TEXT")
            except Exception:
                pass
        if "background_source_id" not in cols:
            try:
                con.execute("ALTER TABLE video_runs ADD COLUMN background_source_id TEXT")
            except Exception:
                pass
        if "moderation_json" not in cols:
            try:
                con.execute("ALTER TABLE video_runs ADD COLUMN moderation_json TEXT")
            except Exception:
                pass
        if "moderation_status" not in cols:
            try:
                con.execute("ALTER TABLE video_runs ADD COLUMN moderation_status TEXT")
            except Exception:
                pass

        # ---- Clipper migrations (safe/no-op if table missing) ----
        try:
            clip_cols = [r["name"] for r in con.execute("PRAGMA table_info(opus_clips)").fetchall()]
        except Exception:
            clip_cols = []
        if clip_cols and "quality_score" not in clip_cols:
            try:
                con.execute("ALTER TABLE opus_clips ADD COLUMN quality_score REAL")
            except Exception:
                pass

    def new_run_id(self) -> str:
        # Short, filesystem-safe id.
        return uuid.uuid4().hex[:12]

    def new_compilation_id(self) -> str:
        return "comp_" + uuid.uuid4().hex[:12]

    # ----------------------------
    # Clipper-bot helpers
    # ----------------------------
    def upsert_source_video(
        self,
        *,
        source_channel: str,
        youtube_video_id: str,
        youtube_url: str,
        title: str,
        published_at: Optional[str],
        duration_seconds: Optional[float],
        status: str = "discovered",
    ) -> str:
        source_video_id = f"src_{uuid.uuid4().hex[:12]}"
        now = _utc_now_iso()
        with self._connect() as con:
            # If video already exists, just update metadata/status.
            row = con.execute(
                "SELECT source_video_id FROM source_videos WHERE youtube_video_id=?",
                (youtube_video_id,),
            ).fetchone()
            if row and row["source_video_id"]:
                sid = row["source_video_id"]
                con.execute(
                    """
                    UPDATE source_videos
                    SET source_channel=?, youtube_url=?, title=?, published_at=?,
                        duration_seconds=?, status=?, updated_at=?
                    WHERE source_video_id=?
                    """,
                    (
                        source_channel,
                        youtube_url,
                        title,
                        published_at,
                        duration_seconds,
                        status,
                        now,
                        sid,
                    ),
                )
                return str(sid)

            con.execute(
                """
                INSERT INTO source_videos (
                  source_video_id, source_channel, youtube_video_id, youtube_url,
                  title, published_at, duration_seconds, status, discovered_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    source_video_id,
                    source_channel,
                    youtube_video_id,
                    youtube_url,
                    title,
                    published_at,
                    duration_seconds,
                    status,
                    now,
                    now,
                ),
            )
        return source_video_id

    def set_source_video_status(self, source_video_id: str, status: str) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE source_videos SET status=?, updated_at=? WHERE source_video_id=?",
                (status, _utc_now_iso(), source_video_id),
            )

    def get_source_videos_by_status(self, status: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT * FROM source_videos
                WHERE status=?
                ORDER BY published_at DESC, discovered_at DESC
                LIMIT ?
                """,
                (status, int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    def upsert_opus_project(
        self,
        *,
        project_id: str,
        org_id: Optional[str],
        source_video_id: str,
        stage: Optional[str],
        raw: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = _utc_now_iso()
        raw_json = _json_dumps(raw) if raw is not None else None
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO opus_projects (project_id, org_id, source_video_id, stage, created_at, updated_at, raw_json)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(project_id) DO UPDATE SET
                  org_id=excluded.org_id,
                  source_video_id=excluded.source_video_id,
                  stage=excluded.stage,
                  updated_at=excluded.updated_at,
                  raw_json=COALESCE(excluded.raw_json, opus_projects.raw_json)
                """,
                (project_id, org_id, source_video_id, stage, now, now, raw_json),
            )

    def get_opus_project_id_for_source_video(self, source_video_id: str) -> Optional[str]:
        with self._connect() as con:
            row = con.execute(
                "SELECT project_id FROM opus_projects WHERE source_video_id=? ORDER BY created_at DESC LIMIT 1",
                (source_video_id,),
            ).fetchone()
        if not row:
            return None
        try:
            pid = row["project_id"]
        except Exception:
            pid = None
        return str(pid) if pid else None

    def get_ready_selected_opus_clips(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Clips that have been selected and downloaded, but not posted yet.
        """
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT oc.*
                FROM opus_clips oc
                WHERE oc.selected_status='selected'
                  AND oc.downloaded_path IS NOT NULL
                  AND oc.downloaded_path != ''
                  AND (oc.posted_status IS NULL OR oc.posted_status='pending')
                ORDER BY COALESCE(oc.quality_score, 0) DESC, oc.created_at DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]

    def count_ready_selected_opus_clips(self) -> int:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT COUNT(*) AS c
                FROM opus_clips oc
                WHERE oc.selected_status='selected'
                  AND oc.downloaded_path IS NOT NULL
                  AND oc.downloaded_path != ''
                  AND (oc.posted_status IS NULL OR oc.posted_status='pending')
                """
            ).fetchone()
        return int(row["c"] if row else 0)

    def set_opus_clip_posted_status(self, clip_id: str, status: str) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE opus_clips SET posted_status=? WHERE clip_id=?",
                (status, clip_id),
            )

    def upsert_opus_clip(
        self,
        *,
        clip_id: str,
        project_id: str,
        quality_score: Optional[float],
        duration_ms: Optional[int],
        uri_for_export: str,
        uri_for_preview: Optional[str],
        time_ranges: Optional[Any],
        title: Optional[str],
        description: Optional[str],
        hashtags: Optional[str],
        raw: Optional[Dict[str, Any]] = None,
        selected_status: str = "candidate",
    ) -> None:
        now = _utc_now_iso()
        raw_json = _json_dumps(raw) if raw is not None else None
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO opus_clips (
                  clip_id, project_id, quality_score, duration_ms, uri_for_export, uri_for_preview,
                  time_ranges_json, title, description, hashtags, created_at,
                  selected_status, posted_status, raw_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(clip_id) DO UPDATE SET
                  project_id=excluded.project_id,
                  quality_score=COALESCE(excluded.quality_score, opus_clips.quality_score),
                  duration_ms=excluded.duration_ms,
                  uri_for_export=excluded.uri_for_export,
                  uri_for_preview=excluded.uri_for_preview,
                  time_ranges_json=excluded.time_ranges_json,
                  title=COALESCE(excluded.title, opus_clips.title),
                  description=COALESCE(excluded.description, opus_clips.description),
                  hashtags=COALESCE(excluded.hashtags, opus_clips.hashtags),
                  selected_status=COALESCE(opus_clips.selected_status, excluded.selected_status),
                  raw_json=COALESCE(excluded.raw_json, opus_clips.raw_json)
                """,
                (
                    clip_id,
                    project_id,
                    quality_score,
                    duration_ms,
                    uri_for_export,
                    uri_for_preview,
                    _json_dumps(time_ranges) if time_ranges is not None else None,
                    title,
                    description,
                    hashtags,
                    now,
                    selected_status,
                    "pending",
                    raw_json,
                ),
            )

    def mark_opus_clip_downloaded(self, clip_id: str, downloaded_path: str) -> None:
        with self._connect() as con:
            con.execute(
                """
                UPDATE opus_clips
                SET downloaded_path=?, downloaded_at=?
                WHERE clip_id=?
                """,
                (downloaded_path, _utc_now_iso(), clip_id),
            )

    def set_opus_clip_selected_status(self, clip_id: str, status: str) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE opus_clips SET selected_status=? WHERE clip_id=?",
                (status, clip_id),
            )

    def get_candidate_opus_clips(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT * FROM opus_clips
                WHERE selected_status='candidate'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_posted_clip(
        self,
        *,
        clip_id: str,
        youtube_video_id: Optional[str],
        youtube_url: Optional[str],
        upload_status: str,
        upload_time: Optional[str],
        publish_time: Optional[str],
    ) -> None:
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO posted_clips (
                  clip_id, youtube_video_id, youtube_url, upload_status, upload_time, publish_time
                ) VALUES (?,?,?,?,?,?)
                ON CONFLICT(clip_id) DO UPDATE SET
                  youtube_video_id=excluded.youtube_video_id,
                  youtube_url=excluded.youtube_url,
                  upload_status=excluded.upload_status,
                  upload_time=excluded.upload_time,
                  publish_time=excluded.publish_time
                """,
                (clip_id, youtube_video_id, youtube_url, upload_status, upload_time, publish_time),
            )

    def get_source_context_for_clip(self, clip_id: str) -> Optional[Dict[str, Any]]:
        """
        Returns source video info and clip timerange for attribution.
        """
        with self._connect() as con:
            row = con.execute(
                """
                SELECT
                  oc.clip_id,
                  oc.time_ranges_json,
                  oc.project_id,
                  sv.youtube_url AS source_youtube_url,
                  sv.title AS source_title,
                  sv.source_channel AS source_channel
                FROM opus_clips oc
                LEFT JOIN opus_projects op ON op.project_id = oc.project_id
                LEFT JOIN source_videos sv ON sv.source_video_id = op.source_video_id
                WHERE oc.clip_id = ?
                """,
                (clip_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_next_compilation_number(self) -> int:
        with self._connect() as con:
            row = con.execute("SELECT MAX(number) AS m FROM compilations").fetchone()
        try:
            m = int(row["m"]) if row and row["m"] is not None else 0
        except Exception:
            m = 0
        return m + 1

    def create_compilation(
        self,
        *,
        title: str,
        description: str,
        output_path: str,
        thumbnail_path: str,
        upload_status: str = "pending",
    ) -> Tuple[str, int]:
        cid = self.new_compilation_id()
        number = self.get_next_compilation_number()
        created_at = _utc_now_iso()
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO compilations (
                  compilation_id, created_at, number, title, description,
                  output_path, thumbnail_path, upload_status
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (cid, created_at, int(number), title, description, output_path, thumbnail_path, upload_status),
            )
        return cid, number

    def update_compilation(self, compilation_id: str, **fields: Any) -> None:
        if not fields:
            return
        set_parts: List[str] = []
        params: List[Any] = []
        for k, v in fields.items():
            set_parts.append(f"{k}=?")
            params.append(v)
        params.append(compilation_id)
        sql = f"UPDATE compilations SET {', '.join(set_parts)} WHERE compilation_id=?"
        with self._connect() as con:
            con.execute(sql, params)

    def add_compilation_item(self, compilation_id: str, run_id: str, position: int) -> None:
        with self._connect() as con:
            con.execute(
                """
                INSERT OR IGNORE INTO compilation_items (compilation_id, run_id, position, created_at)
                VALUES (?,?,?,?)
                """,
                (compilation_id, run_id, int(position), _utc_now_iso()),
            )

    def is_run_used_in_compilation(self, run_id: str) -> bool:
        with self._connect() as con:
            row = con.execute(
                "SELECT 1 FROM compilation_items WHERE run_id=? LIMIT 1",
                (run_id,),
            ).fetchone()
        return bool(row)

    def get_recent_unused_short_runs(
        self,
        *,
        limit: int = 15,
        max_age_days: int = 14,
    ) -> List[VideoRun]:
        """
        Return recent shorts that:
        - have an output_path that looks like our modern pipeline (video_20YYYY...)
        - passed moderation
        - are not already used in a compilation
        """
        # We filter by output filename to exclude older/test artifacts like video_1767....
        pattern = "generated_videos/video_20%"
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT *
                FROM video_runs vr
                WHERE vr.output_path IS NOT NULL
                  AND vr.output_path != ''
                  AND vr.output_path LIKE ?
                  AND (vr.moderation_status IS NULL OR vr.moderation_status='pass')
                  AND vr.created_at >= datetime('now', ?)
                  AND NOT EXISTS (
                    SELECT 1 FROM compilation_items ci WHERE ci.run_id = vr.run_id
                  )
                ORDER BY vr.created_at DESC
                LIMIT ?
                """,
                (pattern, f"-{int(max_age_days)} days", int(limit)),
            ).fetchall()
        return [self._row_to_run(r) for r in rows]

    def create_run(
        self,
        *,
        region: str,
        subreddit: str,
        topic_title: str,
        trend_data: Dict[str, Any],
        script: str,
        metadata: Dict[str, Any],
        privacy_status: str,
        category_id: str,
        run_id: Optional[str] = None,
    ) -> str:
        rid = run_id or self.new_run_id()
        created_at = _utc_now_iso()
        title = (metadata.get("title") or "").strip()
        description = (metadata.get("description") or "").strip()
        tags = metadata.get("tags") or []
        hashtags = metadata.get("hashtags") or []
        script_wc = len((script or "").split())

        with self._connect() as con:
            con.execute(
                """
                INSERT INTO video_runs (
                  run_id, created_at, region, subreddit, topic_title,
                  trend_data_json, script, script_word_count,
                  title, description, tags_json, hashtags_json,
                  privacy_status, category_id,
                  upload_status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    rid,
                    created_at,
                    region,
                    subreddit,
                    topic_title,
                    _json_dumps(trend_data or {}),
                    script or "",
                    script_wc,
                    title,
                    description,
                    _json_dumps(tags),
                    _json_dumps(hashtags),
                    privacy_status,
                    category_id,
                    "pending",
                ),
            )
        return rid

    def update_run(self, run_id: str, **fields: Any) -> None:
        if not fields:
            return
        # Convert *_json helpers to stored json automatically.
        json_fields = {
            "trend_data": "trend_data_json",
            "tags": "tags_json",
            "hashtags": "hashtags_json",
            "voice_config": "voice_config_json",
            "experiment": "experiment_json",
            "moderation": "moderation_json",
            "stats": "stats_json",
        }

        set_parts: List[str] = []
        params: List[Any] = []
        for k, v in fields.items():
            if k in json_fields:
                col = json_fields[k]
                set_parts.append(f"{col}=?")
                params.append(_json_dumps(v))
            elif k == "script":
                set_parts.append("script=?")
                params.append(v or "")
                set_parts.append("script_word_count=?")
                params.append(len((v or "").split()))
            else:
                set_parts.append(f"{k}=?")
                params.append(v)
        params.append(run_id)

        sql = f"UPDATE video_runs SET {', '.join(set_parts)} WHERE run_id=?"
        with self._connect() as con:
            con.execute(sql, params)

    def get_recent_runs(self, limit: int = 50) -> List[VideoRun]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM video_runs ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [self._row_to_run(r) for r in rows]

    def count_success_uploads_since(self, since_iso: str) -> int:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT COUNT(1) AS c
                FROM video_runs
                WHERE upload_status='success'
                  AND upload_time IS NOT NULL
                  AND upload_time >= ?
                """,
                (since_iso,),
            ).fetchone()
        try:
            return int(row["c"] or 0) if row else 0
        except Exception:
            return 0

    def get_success_upload_times_since(self, since_iso: str, limit: int = 200) -> List[str]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT upload_time
                FROM video_runs
                WHERE upload_status='success'
                  AND upload_time IS NOT NULL
                  AND upload_time >= ?
                ORDER BY upload_time ASC
                LIMIT ?
                """,
                (since_iso, int(limit)),
            ).fetchall()
        return [r["upload_time"] for r in rows if r and r["upload_time"]]

    def get_runs_with_video_ids(self, limit: int = 500) -> List[VideoRun]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT * FROM video_runs
                WHERE youtube_video_id IS NOT NULL AND youtube_video_id != ''
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [self._row_to_run(r) for r in rows]

    def get_video_ids_missing_stats(self, limit: int = 200) -> List[Tuple[str, str]]:
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT run_id, youtube_video_id
                FROM video_runs
                WHERE youtube_video_id IS NOT NULL AND youtube_video_id != ''
                  AND (stats_json IS NULL OR stats_json = '')
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return [(r["run_id"], r["youtube_video_id"]) for r in rows]

    def _row_to_run(self, r: sqlite3.Row) -> VideoRun:
        return VideoRun(
            run_id=r["run_id"],
            created_at=r["created_at"],
            region=r["region"] or "",
            subreddit=r["subreddit"] or "",
            topic_title=r["topic_title"] or "",
            trend_data=_json_loads(r["trend_data_json"]) or {},
            script=r["script"] or "",
            title=r["title"] or "",
            description=r["description"] or "",
            tags=_json_loads(r["tags_json"]) or [],
            hashtags=_json_loads(r["hashtags_json"]) or [],
            privacy_status=r["privacy_status"] or "",
            category_id=r["category_id"] or "",
            output_path=r["output_path"],
            video_duration_seconds=r["video_duration_seconds"],
            voice_provider=r["voice_provider"],
            voice_config=_json_loads(r["voice_config_json"]) or None,
            background_pot_url=r["background_pot_url"],
            background_source_type=r["background_source_type"],
            background_source_id=r["background_source_id"],
            background_start_seconds=r["background_start_seconds"],
            background_duration_seconds=r["background_duration_seconds"],
            music_volume_multiplier=r["music_volume_multiplier"],
            experiment_json=_json_loads(r["experiment_json"]) or None,
            moderation_json=_json_loads(r["moderation_json"]) or None,
            moderation_status=r["moderation_status"],
            upload_status=r["upload_status"] or "pending",
            upload_time=r["upload_time"],
            youtube_video_id=r["youtube_video_id"],
            youtube_url=r["youtube_url"],
            stats_json=_json_loads(r["stats_json"]) or None,
            stats_fetched_at=r["stats_fetched_at"],
        )

