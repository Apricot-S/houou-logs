# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class LogEntry:
    id: str
    date: str
    num_players: int  # 4 or 3
    is_tonpu: bool
    is_processed: bool
    was_error: bool
    log: bytes | None


def open_db(db_path: str | Path) -> sqlite3.Connection:
    return sqlite3.connect(db_path, autocommit=False)


def setup_table(conn: sqlite3.Connection) -> None:
    with conn:
        create_logs_table(conn)
        create_last_fetch_time_table(conn)


def create_logs_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            num_players INTEGER NOT NULL CHECK(num_players IN (4, 3)),
            is_tonpu INTEGER NOT NULL CHECK(is_tonpu IN (0, 1)),
            is_processed INTEGER NOT NULL CHECK(is_processed IN (0, 1)),
            was_error INTEGER NOT NULL CHECK(was_error IN (0, 1)),
            log BLOB
        ) WITHOUT ROWID;
        """,
    )


def create_last_fetch_time_table(conn: sqlite3.Connection) -> None:
    cursor = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
            AND name='last_fetch_time';
        """,
    )
    exists = cursor.fetchone() is not None
    if exists:
        return

    conn.execute("CREATE TABLE last_fetch_time (time REAL);")
    conn.execute("INSERT INTO last_fetch_time (time) VALUES (?);", (0.0,))


def insert_entries(cursor: sqlite3.Cursor, entries: list[LogEntry]) -> None:
    if not entries:
        return

    values = (
        (
            entry.id,
            entry.date,
            entry.num_players,
            int(entry.is_tonpu),
            int(entry.is_processed),
            int(entry.was_error),
            entry.log,
        )
        for entry in entries
    )

    cursor.executemany(
        """
        INSERT INTO logs (id, date, num_players, is_tonpu, is_processed, was_error, log)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            date=excluded.date,
            num_players=excluded.num_players,
            is_tonpu=excluded.is_tonpu,
            is_processed=excluded.is_processed,
            was_error=excluded.was_error,
            log=excluded.log;
        """,  # noqa: E501
        values,
    )


def update_last_fetch_time(cursor: sqlite3.Cursor, time: datetime) -> None:
    cursor.execute(
        """
        UPDATE last_fetch_time SET time = ?;
        """,
        (time.astimezone(UTC).timestamp(),),
    )


def get_last_fetch_time(cursor: sqlite3.Cursor) -> datetime:
    cursor.execute(
        """
        SELECT time FROM last_fetch_time;
        """,
    )
    timestamp = cursor.fetchone()[0]
    return datetime.fromtimestamp(timestamp, UTC)
