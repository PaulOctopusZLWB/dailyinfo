import json
import sqlite3
from pathlib import Path

from info_radar.dedupe import item_identity_key_from_values


class RadarStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)

    def initialize(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS run_metadata (
                    report_date TEXT PRIMARY KEY,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS radar_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_date TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    published_at TEXT,
                    content_or_excerpt TEXT,
                    direction_hints_json TEXT NOT NULL,
                    primary_direction TEXT,
                    score REAL,
                    evidence_type TEXT,
                    ad_risk TEXT,
                    core_argument TEXT,
                    recommendation_reason TEXT,
                    cluster_id TEXT,
                    duplicate_count INTEGER
                );
                """
            )
            self._ensure_column(connection, "radar_items", "core_argument", "TEXT")

    def record_run(self, report_date, metadata):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO run_metadata (report_date, metadata_json)
                VALUES (?, ?)
                ON CONFLICT(report_date) DO UPDATE SET
                    metadata_json = excluded.metadata_json,
                    created_at = CURRENT_TIMESTAMP
                """,
                (report_date, json.dumps(metadata, ensure_ascii=False, sort_keys=True)),
            )

    def get_run(self, report_date):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT metadata_json FROM run_metadata WHERE report_date = ?",
                (report_date,),
            ).fetchone()
        if row is None:
            return {}
        return json.loads(row[0])

    def save_items(self, report_date, items):
        with self._connect() as connection:
            connection.execute("DELETE FROM radar_items WHERE report_date = ?", (report_date,))
            connection.executemany(
                """
                INSERT INTO radar_items (
                    report_date, source_id, source_name, source_type, title, url,
                    published_at, content_or_excerpt, direction_hints_json,
                    primary_direction, score, evidence_type, ad_risk,
                    core_argument, recommendation_reason, cluster_id, duplicate_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        report_date,
                        item.source_id,
                        item.source_name,
                        item.source_type,
                        item.title,
                        item.url,
                        item.published_at,
                        item.content_or_excerpt,
                        json.dumps(list(item.direction_hints), ensure_ascii=False),
                        getattr(item, "primary_direction", ""),
                        getattr(item, "score", 0),
                        getattr(item, "evidence_type", ""),
                        getattr(item, "ad_risk", ""),
                        getattr(item, "core_argument", ""),
                        getattr(item, "recommendation_reason", ""),
                        item.cluster_id,
                        item.duplicate_count,
                    )
                    for item in items
                ],
            )

    def get_item_identity_keys_before(self, report_date: str, since_date: str | None = None) -> set[str]:
        query = "SELECT url, title FROM radar_items WHERE report_date < ?"
        params: list[str] = [report_date]
        if since_date:
            query += " AND report_date >= ?"
            params.append(since_date)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return {item_identity_key_from_values(url, title) for url, title in rows}

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _ensure_column(self, connection, table_name: str, column_name: str, column_type: str) -> None:
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()]
        if column_name not in columns:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
