# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import sqlite3
from dataclasses import dataclass
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


def insert_entries(cursor: sqlite3.Cursor, entries: list[LogEntry]) -> None:
    if not entries:
        return

    values = [
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
    ]

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
