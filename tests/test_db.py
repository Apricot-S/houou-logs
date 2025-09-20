# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from houou_logs import db


def test_open_db_create_file(db_path: Path) -> None:
    conn = db.open_db(db_path)
    try:
        assert conn is not None
    finally:
        conn.close()


def test_open_db_persists_after_reopen(db_path: Path) -> None:
    # 1st step: Create DB & insert data
    conn1 = db.open_db(db_path)
    conn1.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT)")
    conn1.execute("INSERT INTO users(name) VALUES (?)", ("Alice",))
    conn1.commit()
    conn1.close()

    # 2nd step: Reopen and check if the data is still there
    conn2 = db.open_db(db_path)
    row = conn2.execute("SELECT name FROM users").fetchone()
    conn2.close()

    assert row == ("Alice",)


def test_setup_table_creates_logs_table() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)

        cursor = conn.execute(
            """
            SELECT name FROM sqlite_master WHERE type='table' AND name='logs';
            """,
        )
        table = cursor.fetchone()
        assert table is not None
        assert table[0] == "logs"
    finally:
        conn.close()


def test_setup_table_creates_last_fetch_time_table() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)

        cursor = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
                AND name='last_fetch_time';
            """,
        )
        table = cursor.fetchone()
        assert table is not None
        assert table[0] == "last_fetch_time"
    finally:
        conn.close()


def test_setup_table_creates_file_index_table() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)

        cursor = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
                AND name='file_index';
            """,
        )
        table = cursor.fetchone()
        assert table is not None
        assert table[0] == "file_index"
    finally:
        conn.close()


def test_insert_log_entries() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        entries = [
            db.LogEntry(
                id="2009010100gm-00a9-0000-00000000",
                date="2009-01-01",
                num_players=4,
                is_tonpu=False,
                is_processed=False,
                was_error=False,
                log=None,
            ),
            db.LogEntry(
                id="2013020100gm-00f1-0000-00000000",
                date="2013-02-01",
                num_players=3,
                is_tonpu=True,
                is_processed=True,
                was_error=True,
                log=b"sample log data",
            ),
        ]

        db.insert_log_entries(cursor, entries)
        conn.commit()

        cursor.execute("SELECT * FROM logs;")
        rows = cursor.fetchall()
        assert len(rows) == len(entries)
    finally:
        conn.close()


def test_update_last_fetch_time() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        zone_info = ZoneInfo("Asia/Tokyo")
        time = datetime(2025, 9, 20, 10, 30, 40, 500, tzinfo=zone_info)
        timestamp = time.astimezone(UTC).timestamp()

        db.update_last_fetch_time(cursor, time)
        conn.commit()

        cursor.execute("SELECT * FROM last_fetch_time;")
        rows = cursor.fetchall()
        assert rows[0][0] == timestamp
    finally:
        conn.close()


def test_update_last_fetch_time_has_only_one_row() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        zone_info = ZoneInfo("Asia/Tokyo")
        time1 = datetime(2025, 9, 20, 10, 30, 40, 500, tzinfo=zone_info)
        time2 = datetime(2025, 9, 21, 10, 30, 40, 500, tzinfo=zone_info)

        db.update_last_fetch_time(cursor, time1)
        db.update_last_fetch_time(cursor, time2)
        conn.commit()

        cursor.execute("SELECT * FROM last_fetch_time;")
        rows = cursor.fetchall()
        assert len(rows) == 1
    finally:
        conn.close()


def test_update_last_fetch_time_has_only_last_time() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        zone_info = ZoneInfo("Asia/Tokyo")
        time1 = datetime(2025, 9, 20, 10, 30, 40, 500, tzinfo=zone_info)
        time2 = datetime(2025, 9, 21, 10, 30, 40, 500, tzinfo=zone_info)
        timestamp = time2.astimezone(UTC).timestamp()

        db.update_last_fetch_time(cursor, time1)
        db.update_last_fetch_time(cursor, time2)
        conn.commit()

        cursor.execute("SELECT * FROM last_fetch_time;")
        rows = cursor.fetchall()
        assert rows[0][0] == timestamp
    finally:
        conn.close()


def test_get_last_fetch_time_never_fetched() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()
        last_fetch_time = db.get_last_fetch_time(cursor)
        assert last_fetch_time.astimezone(UTC).timestamp() == 0.0
    finally:
        conn.close()


def test_get_last_fetch_time_2_times_updated() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()
        zone_info = ZoneInfo("Asia/Tokyo")
        time1 = datetime(2025, 9, 20, 10, 30, 40, 500, tzinfo=zone_info)
        time2 = datetime(2025, 9, 21, 10, 30, 40, 500, tzinfo=zone_info)
        timestamp = time2.astimezone(UTC).timestamp()

        db.update_last_fetch_time(cursor, time1)
        db.update_last_fetch_time(cursor, time2)
        conn.commit()

        last_fetch_time = db.get_last_fetch_time(cursor)
        assert last_fetch_time.astimezone(UTC).timestamp() == timestamp
    finally:
        conn.close()
