"""Local SQLite persistent storage for duplicate prevention and message tracking."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("scrapx.database")


class DatabaseManager:
    """Manages SQLite database connection, table schemas, and message tracking."""

    def __init__(self, db_path: str = "data/scrapx_media.db"):
        self.db_path = Path(db_path)
        self._ensure_dir()
        self._init_db()

    def _ensure_dir(self) -> None:
        """Ensures the directory containing the database exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a connection with sqlite3 row factory and WAL mode enabled."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _init_db(self) -> None:
        """Initializes tables and indexes."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_channel TEXT NOT NULL,
                    source_message_id INTEGER NOT NULL,
                    grouped_id INTEGER,
                    dest_channel TEXT,
                    dest_message_id INTEGER,
                    status TEXT NOT NULL,  -- 'published', 'failed', 'dry_run'
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_channel, source_message_id)
                );
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS channel_watermarks (
                    source_channel TEXT PRIMARY KEY,
                    last_message_id INTEGER NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_source_msg 
                ON processed_messages (source_channel, source_message_id);
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_grouped_id 
                ON processed_messages (grouped_id);
            """)
            conn.commit()
            logger.info("Database initialized successfully at %s", self.db_path)

    def is_message_processed(self, source_channel: str, source_msg_id: int) -> bool:
        """
        Checks if a message has already been processed (either published or recorded as dry_run).
        Returns True if already processed, False otherwise.
        """
        source_channel = str(source_channel).lower()
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, status FROM processed_messages 
                WHERE source_channel = ? AND source_message_id = ?
                """,
                (source_channel, source_msg_id),
            )
            row = cursor.fetchone()
            if row is not None:
                # If marked as 'published' or 'dry_run', treat as processed
                return row["status"] in ("published", "dry_run")
            return False

    def mark_published(
        self,
        source_channel: str,
        source_msg_id: int,
        dest_channel: str,
        dest_msg_id: Optional[int] = None,
        grouped_id: Optional[int] = None,
    ) -> None:
        """
        Atomically records a message as successfully published and updates the channel watermark.
        """
        source_channel = str(source_channel).lower()
        dest_channel = str(dest_channel).lower()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO processed_messages (
                    source_channel, source_message_id, grouped_id, 
                    dest_channel, dest_message_id, status
                )
                VALUES (?, ?, ?, ?, ?, 'published')
                ON CONFLICT(source_channel, source_message_id) DO UPDATE SET
                    status = 'published',
                    dest_channel = excluded.dest_channel,
                    dest_message_id = excluded.dest_message_id,
                    grouped_id = excluded.grouped_id,
                    error_message = NULL,
                    created_at = CURRENT_TIMESTAMP;
                """,
                (source_channel, source_msg_id, grouped_id, dest_channel, dest_msg_id),
            )

            # Update channel watermark
            conn.execute(
                """
                INSERT INTO channel_watermarks (source_channel, last_message_id, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(source_channel) DO UPDATE SET
                    last_message_id = MAX(last_message_id, excluded.last_message_id),
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (source_channel, source_msg_id),
            )
            conn.commit()
            logger.debug(
                "Marked message %s from %s as published (dest_id: %s)",
                source_msg_id,
                source_channel,
                dest_msg_id,
            )

    def mark_dry_run(
        self,
        source_channel: str,
        source_msg_id: int,
        grouped_id: Optional[int] = None,
    ) -> None:
        """Records a message in dry-run mode."""
        source_channel = str(source_channel).lower()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO processed_messages (
                    source_channel, source_message_id, grouped_id, status
                )
                VALUES (?, ?, ?, 'dry_run')
                ON CONFLICT(source_channel, source_message_id) DO NOTHING;
                """,
                (source_channel, source_msg_id, grouped_id),
            )
            conn.commit()

    def mark_failed(
        self,
        source_channel: str,
        source_msg_id: int,
        error_message: str,
        grouped_id: Optional[int] = None,
    ) -> None:
        """
        Records a failed attempt. Note: This does NOT prevent retry unless explicitly intended.
        """
        source_channel = str(source_channel).lower()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO processed_messages (
                    source_channel, source_message_id, grouped_id, status, error_message
                )
                VALUES (?, ?, ?, 'failed', ?)
                ON CONFLICT(source_channel, source_message_id) DO UPDATE SET
                    status = 'failed',
                    error_message = excluded.error_message,
                    created_at = CURRENT_TIMESTAMP;
                """,
                (source_channel, source_msg_id, grouped_id, error_message),
            )
            conn.commit()
            logger.warning(
                "Recorded failed processing for msg %s from %s: %s",
                source_msg_id,
                source_channel,
                error_message,
            )

    def get_last_processed_id(self, source_channel: str) -> Optional[int]:
        """Returns the highest message ID recorded for a source channel."""
        source_channel = str(source_channel).lower()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT last_message_id FROM channel_watermarks WHERE source_channel = ?",
                (source_channel,),
            )
            row = cursor.fetchone()
            if row:
                return row["last_message_id"]
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """Returns diagnostic statistics about recorded messages."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT source_channel, status, COUNT(*) as count 
                FROM processed_messages 
                GROUP BY source_channel, status
            """)
            breakdown: Dict[str, Dict[str, int]] = {}
            for row in cursor.fetchall():
                src = row["source_channel"]
                st = row["status"]
                cnt = row["count"]
                if src not in breakdown:
                    breakdown[src] = {}
                breakdown[src][st] = cnt

            watermarks_cur = conn.execute("SELECT source_channel, last_message_id FROM channel_watermarks")
            watermarks = {r["source_channel"]: r["last_message_id"] for r in watermarks_cur.fetchall()}

            return {"breakdown": breakdown, "watermarks": watermarks}

