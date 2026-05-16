# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import sqlite3
import sys
from collections.abc import Iterator
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
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(db_path, autocommit=False)


def setup_table(conn: sqlite3.Connection) -> None:
    with conn:
        create_logs_table(conn)
        create_fetch_state_table(conn)
        migrate_last_fetch_time_to_fetch_state(conn)
        create_file_index_table(conn)
        create_logs_status_filter_index(conn)


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


def create_fetch_state_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fetch_state (
            kind TEXT PRIMARY KEY,
            last_attempt_time REAL NOT NULL
        ) WITHOUT ROWID;
        """,
    )


def migrate_last_fetch_time_to_fetch_state(conn: sqlite3.Connection) -> None:
    cursor = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
            AND name='last_fetch_time';
        """,
    )
    if cursor.fetchone() is None:
        return

    # v1.0.8 and earlier used last_fetch_time for latest fetches only.
    cursor = conn.execute("SELECT MAX(time) FROM last_fetch_time;")
    time = cursor.fetchone()[0]
    if time is None:
        time = 0.0

    conn.execute(
        """
        INSERT INTO fetch_state (kind, last_attempt_time)
        VALUES (?, ?)
        ON CONFLICT(kind) DO UPDATE SET
            last_attempt_time=excluded.last_attempt_time;
        """,
        ("latest", time),
    )
    conn.execute("DROP TABLE last_fetch_time;")
    print("Migrated last_fetch_time to fetch_state.", file=sys.stderr)


def create_file_index_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS file_index (
            file TEXT PRIMARY KEY,
            size INTEGER NOT NULL CHECK(size > 0)
        ) WITHOUT ROWID;
        """,
    )


def create_logs_status_filter_index(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_logs_status_filter
        ON logs (is_processed, was_error, num_players, is_tonpu, id);
        """,
    )


def insert_log_entries(
    cursor: sqlite3.Cursor,
    entries: list[LogEntry],
) -> None:
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
        ON CONFLICT(id) DO NOTHING;
        """,  # noqa: E501
        values,
    )


def list_undownloaded_log_ids_after(
    cursor: sqlite3.Cursor,
    players: int | None,
    length: str | None,
    after_id: str | None,
    limit: int,
) -> list[str]:
    conditions = ["is_processed = 0", "was_error = 0"]
    params: list = []

    if players is not None:
        conditions.append("num_players = ?")
        params.append(players)

    if length is not None:
        match length:
            case "t":
                conditions.append("is_tonpu = 1")
            case "h":
                conditions.append("is_tonpu = 0")
            case _:
                msg = f"unknown length: {length}"
                raise ValueError(msg)

    if after_id is not None:
        conditions.append("id > ?")
        params.append(after_id)

    sql = f"""
        SELECT id
        FROM logs
        WHERE {" AND ".join(conditions)}
        ORDER BY id ASC
        LIMIT ?
        """  # noqa: S608
    params.append(limit)

    cursor.execute(sql, params)
    return [row[0] for row in cursor.fetchall()]


def count_undownloaded_log_ids(
    cursor: sqlite3.Cursor,
    players: int | None,
    length: str | None,
    limit: int | None,
) -> int:
    conditions = ["is_processed = 0", "was_error = 0"]
    params: list = []

    if players is not None:
        conditions.append("num_players = ?")
        params.append(players)

    if length is not None:
        match length:
            case "t":
                conditions.append("is_tonpu = 1")
            case "h":
                conditions.append("is_tonpu = 0")
            case _:
                msg = f"unknown length: {length}"
                raise ValueError(msg)

    sql = f"""
        SELECT COUNT(*)
        FROM logs
        WHERE {" AND ".join(conditions)}
        """  # noqa: S608

    cursor.execute(sql, params)
    count = cursor.fetchone()[0]
    if limit is not None:
        return min(count, limit)
    return count


def update_log_entries(
    cursor: sqlite3.Cursor,
    log_id: str,
    was_error: bool,  # noqa: FBT001
    log: bytes | None,
) -> None:
    result = cursor.execute(
        """
        UPDATE logs SET is_processed = 1, was_error = ?, log = ?
        WHERE id = ?;
        """,
        (int(was_error), log, log_id),
    )
    if result.rowcount != 1:
        msg = f"log entry not found: {log_id}"
        raise RuntimeError(msg)


def count_all_log_contents(cursor: sqlite3.Cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM logs
        WHERE is_processed = 1
        """,
    )
    return cursor.fetchone()[0]


def list_all_processed_log_ids_after(
    cursor: sqlite3.Cursor,
    after_id: str | None,
    limit: int,
) -> list[str]:
    if after_id is None:
        cursor.execute(
            """
            SELECT id
            FROM logs
            WHERE is_processed = 1
            ORDER BY id ASC
            LIMIT ?;
            """,
            (limit,),
        )
    else:
        cursor.execute(
            """
            SELECT id
            FROM logs
            WHERE is_processed = 1
                AND id > ?
            ORDER BY id ASC
            LIMIT ?;
            """,
            (after_id, limit),
        )

    return [row[0] for row in cursor.fetchall()]


def get_log_content(cursor: sqlite3.Cursor, log_id: str) -> bytes | None:
    cursor.execute(
        """
        SELECT log
        FROM logs
        WHERE id = ?;
        """,
        (log_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return row[0]


def iter_log_contents(
    cursor: sqlite3.Cursor,
    players: int | None,
    length: str | None,
    limit: int | None,
    offset: int,
) -> Iterator[tuple[str, bytes]]:
    conditions = ["is_processed = 1", "was_error = 0"]
    params: list = []

    if players is not None:
        conditions.append("num_players = ?")
        params.append(players)

    if length is not None:
        match length:
            case "t":
                conditions.append("is_tonpu = 1")
            case "h":
                conditions.append("is_tonpu = 0")
            case _:
                msg = f"unknown length: {length}"
                raise ValueError(msg)

    sql = f"""
        SELECT id, log
        FROM logs
        WHERE {" AND ".join(conditions)}
        ORDER BY id ASC
        """  # noqa: S608

    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    cursor.execute(sql, params)
    yield from cursor


def count_log_contents(
    cursor: sqlite3.Cursor,
    players: int | None,
    length: str | None,
    limit: int | None,
    offset: int,
) -> int:
    conditions = ["is_processed = 1", "was_error = 0"]
    params: list = []

    if players is not None:
        conditions.append("num_players = ?")
        params.append(players)

    if length is not None:
        match length:
            case "t":
                conditions.append("is_tonpu = 1")
            case "h":
                conditions.append("is_tonpu = 0")
            case _:
                msg = f"unknown length: {length}"
                raise ValueError(msg)

    sql = f"""
        SELECT COUNT(*)
        FROM logs
        WHERE {" AND ".join(conditions)}
        """  # noqa: S608

    cursor.execute(sql, params)
    count = cursor.fetchone()[0]

    if offset > 0:
        count = max(count - offset, 0)

    if limit is not None:
        return min(count, limit)

    return count


def count_all_ids(cursor: sqlite3.Cursor) -> int:
    cursor.execute("SELECT COUNT(*) from logs;")
    return cursor.fetchone()[0]


def reset_log_content(cursor: sqlite3.Cursor, log_id: str) -> None:
    cursor.execute(
        """
        UPDATE logs SET is_processed = 0, was_error = 0, log = NULL
        WHERE id = ?;
        """,
        (log_id,),
    )


def update_fetch_attempt_time(
    cursor: sqlite3.Cursor,
    kind: str,
    time: datetime,
) -> None:
    cursor.execute(
        """
        INSERT INTO fetch_state (kind, last_attempt_time)
        VALUES (?, ?)
        ON CONFLICT(kind) DO UPDATE SET
            last_attempt_time=excluded.last_attempt_time;
        """,
        (kind, time.astimezone(UTC).timestamp()),
    )


def get_fetch_attempt_time(cursor: sqlite3.Cursor, kind: str) -> datetime:
    cursor.execute(
        """
        SELECT last_attempt_time FROM fetch_state
        WHERE kind = ?;
        """,
        (kind,),
    )
    row = cursor.fetchone()
    if row is None:
        return datetime.fromtimestamp(0.0, UTC)

    timestamp = row[0]
    return datetime.fromtimestamp(timestamp, UTC)


def list_changed_file_index(
    cursor: sqlite3.Cursor,
    file_index: dict[str, int],
) -> dict[str, int]:
    if not file_index:
        return {}

    try:
        cursor.execute(
            """
            CREATE TEMP TABLE input_file_index (
                file TEXT PRIMARY KEY,
                size INTEGER NOT NULL CHECK(size > 0)
            ) WITHOUT ROWID;
            """,
        )
        cursor.executemany(
            """
            INSERT INTO input_file_index(file, size)
            VALUES (?, ?);
            """,
            file_index.items(),
        )
        cursor.execute(
            """
            SELECT input.file, input.size
            FROM input_file_index AS input
            LEFT JOIN file_index AS stored
                ON stored.file = input.file
                AND stored.size = input.size
            WHERE stored.file IS NULL;
            """,
        )
        return dict(cursor.fetchall())
    finally:
        cursor.execute("DROP TABLE IF EXISTS input_file_index;")


def insert_file_index(cursor: sqlite3.Cursor, file: str, size: int) -> None:
    cursor.execute(
        """
        INSERT INTO file_index (file, size)
        VALUES (?, ?)
        ON CONFLICT(file) DO UPDATE SET
            size=excluded.size;
        """,
        (file, size),
    )
