"""SQLite-backed download repository.

SQLite ships with Python, needs no server and is transactional, which makes it a safer
choice than a JSON file for data that is rewritten while downloads are running. The
schema is versioned through ``PRAGMA user_version`` so later releases can add migrations
without touching existing databases by hand.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Protocol

from omni_download_manager.core.errors import PersistenceError
from omni_download_manager.core.models import DownloadItem, DownloadStatus

logger = logging.getLogger(__name__)

# Append new migrations; never edit an existing entry.
MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE downloads (
        id                TEXT PRIMARY KEY,
        url               TEXT NOT NULL,
        directory         TEXT NOT NULL,
        filename          TEXT NOT NULL,
        filename_resolved INTEGER NOT NULL DEFAULT 0,
        status            TEXT NOT NULL,
        total_bytes       INTEGER,
        downloaded_bytes  INTEGER NOT NULL DEFAULT 0,
        resumable         INTEGER,
        etag              TEXT,
        last_modified     TEXT,
        error_message     TEXT,
        created_at        REAL NOT NULL,
        completed_at      REAL
    );
    CREATE INDEX idx_downloads_created ON downloads (created_at);
    """,
    """
    ALTER TABLE downloads ADD COLUMN scheduled_at REAL;
    """,
    """
    ALTER TABLE downloads ADD COLUMN transfer_mode TEXT;
    ALTER TABLE downloads ADD COLUMN multipart_segments_json TEXT;
    """,
)


class DownloadRepository(Protocol):
    def load_all(self) -> list[DownloadItem]: ...

    def save(self, item: DownloadItem) -> None: ...

    def delete(self, item_id: str) -> None: ...

    def close(self) -> None: ...


class SqliteDownloadRepository:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        # The manager calls from several worker threads; access is serialised by _lock.
        self._connection = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
        try:
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._migrate()
        except BaseException:
            self._connection.close()
            raise

    def _migrate(self) -> None:
        with self._lock:
            version = self._connection.execute("PRAGMA user_version").fetchone()[0]
            for number in range(version, len(MIGRATIONS)):
                with self._connection:
                    self._connection.executescript(MIGRATIONS[number])
                    self._connection.execute(f"PRAGMA user_version = {number + 1}")
                logger.info("Applied database migration %d", number + 1)

    def load_all(self) -> list[DownloadItem]:
        try:
            with self._lock:
                rows = self._connection.execute(
                    "SELECT * FROM downloads ORDER BY created_at DESC"
                ).fetchall()
        except sqlite3.Error as exc:
            raise PersistenceError("The download list couldn't be loaded.", detail=repr(exc)) from exc

        items: list[DownloadItem] = []
        for row in rows:
            try:
                items.append(_row_to_item(row))
            except (ValueError, KeyError):
                logger.warning("Skipping unreadable download record %s", row["id"], exc_info=True)
        return items

    def save(self, item: DownloadItem) -> None:
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    """
                    INSERT INTO downloads (
                        id, url, directory, filename, filename_resolved, status, total_bytes,
                        downloaded_bytes, resumable, etag, last_modified, error_message,
                        created_at, scheduled_at, completed_at, transfer_mode,
                        multipart_segments_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        url=excluded.url, directory=excluded.directory,
                        filename=excluded.filename,
                        filename_resolved=excluded.filename_resolved,
                        status=excluded.status, total_bytes=excluded.total_bytes,
                        downloaded_bytes=excluded.downloaded_bytes,
                        resumable=excluded.resumable, etag=excluded.etag,
                        last_modified=excluded.last_modified,
                        error_message=excluded.error_message,
                        scheduled_at=excluded.scheduled_at,
                        completed_at=excluded.completed_at,
                        transfer_mode=excluded.transfer_mode,
                        multipart_segments_json=excluded.multipart_segments_json
                    """,
                    (
                        item.id,
                        item.url,
                        item.directory,
                        item.filename,
                        int(item.filename_resolved),
                        item.status.value,
                        item.total_bytes,
                        item.downloaded_bytes,
                        None if item.resumable is None else int(item.resumable),
                        item.etag,
                        item.last_modified,
                        item.error_message,
                        item.created_at,
                        item.scheduled_at,
                        item.completed_at,
                        item.transfer_mode,
                        item.multipart_segments_json,
                    ),
                )
        except sqlite3.Error as exc:
            raise PersistenceError("The download list couldn't be saved.", detail=repr(exc)) from exc

    def delete(self, item_id: str) -> None:
        try:
            with self._lock, self._connection:
                self._connection.execute("DELETE FROM downloads WHERE id = ?", (item_id,))
        except sqlite3.Error as exc:
            raise PersistenceError("The download couldn't be removed from the list.", detail=repr(exc)) from exc

    def close(self) -> None:
        with self._lock:
            try:
                self._connection.close()
            except sqlite3.Error:
                logger.debug("Error while closing database", exc_info=True)


def open_repository(path: Path) -> SqliteDownloadRepository:
    """Open the database, moving a corrupt file aside instead of refusing to start."""
    try:
        return SqliteDownloadRepository(path)
    except sqlite3.DatabaseError:
        backup = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
        logger.exception("Download database is unreadable; moving it to %s", backup)
        path.replace(backup)
        return SqliteDownloadRepository(path)


def _row_to_item(row: sqlite3.Row) -> DownloadItem:
    resumable = row["resumable"]
    return DownloadItem(
        id=row["id"],
        url=row["url"],
        directory=row["directory"],
        filename=row["filename"],
        filename_resolved=bool(row["filename_resolved"]),
        status=DownloadStatus(row["status"]),
        total_bytes=row["total_bytes"],
        downloaded_bytes=row["downloaded_bytes"],
        resumable=None if resumable is None else bool(resumable),
        etag=row["etag"],
        last_modified=row["last_modified"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        scheduled_at=row["scheduled_at"],
        completed_at=row["completed_at"],
        transfer_mode=row["transfer_mode"],
        multipart_segments_json=row["multipart_segments_json"],
    )
