# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import sqlite3
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from houou_logs import db


@pytest.fixture
def conn_test_db(tmp_path: Path) -> Generator[sqlite3.Connection, None, None]:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path, autocommit=False)

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
            log=b"broken log data",
        ),
        db.LogEntry(
            id="2013020101gm-00f1-0000-00000000",
            date="2013-02-01",
            num_players=3,
            is_tonpu=True,
            is_processed=True,
            was_error=False,
            log=b"sample log data",
        ),
        db.LogEntry(
            id="2023020101gm-00f1-0000-00000000",
            date="2023-02-01",
            num_players=3,
            is_tonpu=True,
            is_processed=False,
            was_error=True,
            log=b"invalid log data",
        ),
    ]

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

    conn.executemany(
        """
        INSERT INTO logs (id, date, num_players, is_tonpu, is_processed, was_error, log)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,  # noqa: E501
        values,
    )
    conn.commit()

    yield conn

    conn.close()


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


def test_setup_table_creates_fetch_state_table() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)

        cursor = conn.execute(
            """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                AND name='fetch_state';
            """,
        )
        table = cursor.fetchone()
        assert table is not None
        assert table[0] == "fetch_state"

        cursor = conn.execute("PRAGMA table_info(fetch_state);")
        columns = [row[1] for row in cursor.fetchall()]
        assert columns == ["kind", "last_attempt_time"]
    finally:
        conn.close()


def test_setup_table_migrates_legacy_last_fetch_time_to_fetch_state(
    capsys: pytest.CaptureFixture[str],
) -> None:
    conn = db.open_db(":memory:")

    try:
        conn.execute("CREATE TABLE last_fetch_time (time REAL);")
        conn.execute("INSERT INTO last_fetch_time (time) VALUES (?);", (1.0,))
        conn.execute("INSERT INTO last_fetch_time (time) VALUES (?);", (2.0,))
        conn.commit()

        db.setup_table(conn)

        cursor = conn.execute("PRAGMA table_info(fetch_state);")
        columns = [row[1] for row in cursor.fetchall()]
        assert columns == ["kind", "last_attempt_time"]

        cursor = conn.execute(
            "SELECT kind, last_attempt_time FROM fetch_state;",
        )
        assert cursor.fetchall() == [("latest", 2.0)]

        cursor = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
                AND name='last_fetch_time';
            """,
        )
        assert cursor.fetchone() is None

        captured = capsys.readouterr()
        assert captured.err == "Migrated last_fetch_time to fetch_state.\n"
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


def test_setup_table_creates_logs_status_filter_index() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)

        cursor = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='index'
                AND name='idx_logs_status_filter';
            """,
        )
        index = cursor.fetchone()
        assert index is not None
        assert index[0] == "idx_logs_status_filter"
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


def test_insert_log_entries_keeps_existing_row_on_conflict() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        log_id = "2009010100gm-00a9-0000-00000000"
        entry = db.LogEntry(
            id=log_id,
            date="2009-01-01",
            num_players=4,
            is_tonpu=False,
            is_processed=True,
            was_error=False,
            log=b"downloaded log",
        )
        db.insert_log_entries(cursor, [entry])
        conn.commit()

        refreshed_entry = db.LogEntry(
            id=log_id,
            date="2009-01-02",
            num_players=3,
            is_tonpu=True,
            is_processed=False,
            was_error=True,
            log=None,
        )
        db.insert_log_entries(cursor, [refreshed_entry])
        conn.commit()

        cursor.execute("SELECT * FROM logs WHERE id = ?;", (log_id,))
        actual = cursor.fetchone()
        expected = (
            log_id,
            "2009-01-01",
            4,
            0,
            1,
            0,
            b"downloaded log",
        )
        assert actual == expected
    finally:
        conn.close()


def test_list_undownloaded_log_ids_after() -> None:
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
                id="2009010101gm-00a9-0000-00000000",
                date="2009-01-01",
                num_players=4,
                is_tonpu=False,
                is_processed=False,
                was_error=False,
                log=None,
            ),
            db.LogEntry(
                id="2009010102gm-00a9-0000-00000000",
                date="2009-01-01",
                num_players=4,
                is_tonpu=False,
                is_processed=False,
                was_error=False,
                log=None,
            ),
        ]
        db.insert_log_entries(cursor, entries)
        conn.commit()

        actual = db.list_undownloaded_log_ids_after(
            cursor,
            None,
            None,
            "2009010100gm-00a9-0000-00000000",
            2,
        )
        expected = [
            "2009010101gm-00a9-0000-00000000",
            "2009010102gm-00a9-0000-00000000",
        ]
        assert actual == expected
    finally:
        conn.close()


def test_count_undownloaded_log_ids_with_limit(
    conn_test_db: sqlite3.Connection,
) -> None:
    cursor = conn_test_db.cursor()
    actual = db.count_undownloaded_log_ids(cursor, None, None, 1)
    assert actual == 1


def test_update_log_entries() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        entry = db.LogEntry(
            id="2009010100gm-00a9-0000-00000000",
            date="2009-01-01",
            num_players=4,
            is_tonpu=False,
            is_processed=False,
            was_error=False,
            log=None,
        )
        db.insert_log_entries(cursor, [entry])
        conn.commit()

        db.update_log_entries(
            cursor,
            entry.id,
            True,  # noqa: FBT003
            b"sample",
        )

        cursor.execute("SELECT * FROM logs;")
        actual = cursor.fetchone()
        expected = (
            entry.id,
            entry.date,
            entry.num_players,
            entry.is_tonpu,
            1,
            1,
            b"sample",
        )
        assert actual == expected
    finally:
        conn.close()


def test_update_log_entries_rejects_missing_id() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        with pytest.raises(RuntimeError, match="log entry not found"):
            db.update_log_entries(
                cursor,
                "2009010100gm-00a9-0000-00000000",
                True,  # noqa: FBT003
                b"sample",
            )
    finally:
        conn.close()


def test_iter_all_log_contents(conn_test_db: sqlite3.Connection) -> None:
    cursor = conn_test_db.cursor()
    actual = list(db.iter_all_log_contents(cursor))
    expected = [
        ("2013020100gm-00f1-0000-00000000", b"broken log data"),
        ("2013020101gm-00f1-0000-00000000", b"sample log data"),
    ]
    assert actual == expected


def test_count_all_log_contents(conn_test_db: sqlite3.Connection) -> None:
    cursor = conn_test_db.cursor()
    actual = db.count_all_log_contents(cursor)
    assert actual == 2


def test_iter_log_contents(conn_test_db: sqlite3.Connection) -> None:
    cursor = conn_test_db.cursor()
    actual = list(db.iter_log_contents(cursor, None, None, None, 0))
    expected = [("2013020101gm-00f1-0000-00000000", b"sample log data")]
    assert actual == expected


def test_count_log_contents(conn_test_db: sqlite3.Connection) -> None:
    cursor = conn_test_db.cursor()
    actual = db.count_log_contents(cursor, None, None, None, 0)
    assert actual == 1


def test_count_log_contents_applies_limit_and_offset(
    conn_test_db: sqlite3.Connection,
) -> None:
    cursor = conn_test_db.cursor()
    actual = db.count_log_contents(cursor, None, None, 1, 1)
    assert actual == 0


def test_count_all_ids(conn_test_db: sqlite3.Connection) -> None:
    cursor = conn_test_db.cursor()
    actual = db.count_all_ids(cursor)
    assert actual == 4


def test_reset_log_content() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        log_id = "2009010100gm-00a9-0000-00000000"
        entry = db.LogEntry(
            id=log_id,
            date="2009-01-01",
            num_players=4,
            is_tonpu=False,
            is_processed=False,
            was_error=False,
            log=None,
        )
        db.insert_log_entries(cursor, [entry])
        db.update_log_entries(cursor, entry.id, True, b"sample")  # noqa: FBT003
        conn.commit()

        db.reset_log_content(cursor, log_id)

        cursor.execute("SELECT * FROM logs;")
        expected = (
            entry.id,
            entry.date,
            entry.num_players,
            entry.is_tonpu,
            0,
            0,
            None,
        )
        assert cursor.fetchone() == expected
    finally:
        conn.close()


def test_update_fetch_attempt_time() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        zone_info = ZoneInfo("Asia/Tokyo")
        time = datetime(2025, 9, 20, 10, 30, 40, 500, tzinfo=zone_info)
        timestamp = time.astimezone(UTC).timestamp()

        db.update_fetch_attempt_time(cursor, "latest", time)
        conn.commit()

        cursor.execute("SELECT kind, last_attempt_time FROM fetch_state;")
        rows = cursor.fetchall()
        assert rows == [("latest", timestamp)]
    finally:
        conn.close()


def test_update_fetch_attempt_time_has_only_one_row_per_kind() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        zone_info = ZoneInfo("Asia/Tokyo")
        time1 = datetime(2025, 9, 20, 10, 30, 40, 500, tzinfo=zone_info)
        time2 = datetime(2025, 9, 21, 10, 30, 40, 500, tzinfo=zone_info)

        db.update_fetch_attempt_time(cursor, "latest", time1)
        db.update_fetch_attempt_time(cursor, "latest", time2)
        conn.commit()

        cursor.execute("SELECT last_attempt_time FROM fetch_state;")
        rows = cursor.fetchall()
        assert len(rows) == 1
    finally:
        conn.close()


def test_fetch_state_allows_latest_and_archive_rows() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        db.update_fetch_attempt_time(
            cursor,
            "latest",
            datetime(2025, 9, 20, tzinfo=UTC),
        )
        db.update_fetch_attempt_time(
            cursor,
            "archive",
            datetime(2025, 9, 21, tzinfo=UTC),
        )
        conn.commit()

        cursor.execute("SELECT kind FROM fetch_state ORDER BY kind;")
        assert cursor.fetchall() == [("archive",), ("latest",)]
    finally:
        conn.close()


def test_update_fetch_attempt_time_has_only_last_time() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        zone_info = ZoneInfo("Asia/Tokyo")
        time1 = datetime(2025, 9, 20, 10, 30, 40, 500, tzinfo=zone_info)
        time2 = datetime(2025, 9, 21, 10, 30, 40, 500, tzinfo=zone_info)
        timestamp = time2.astimezone(UTC).timestamp()

        db.update_fetch_attempt_time(cursor, "latest", time1)
        db.update_fetch_attempt_time(cursor, "latest", time2)
        conn.commit()

        cursor.execute("SELECT last_attempt_time FROM fetch_state;")
        rows = cursor.fetchall()
        assert rows[0][0] == timestamp
    finally:
        conn.close()


def test_get_fetch_attempt_time_never_fetched() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()
        last_attempt_time = db.get_fetch_attempt_time(cursor, "archive")
        assert last_attempt_time.astimezone(UTC).timestamp() == 0.0
    finally:
        conn.close()


def test_get_fetch_attempt_time_2_times_updated() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()
        zone_info = ZoneInfo("Asia/Tokyo")
        time1 = datetime(2025, 9, 20, 10, 30, 40, 500, tzinfo=zone_info)
        time2 = datetime(2025, 9, 21, 10, 30, 40, 500, tzinfo=zone_info)
        timestamp = time2.astimezone(UTC).timestamp()

        db.update_fetch_attempt_time(cursor, "latest", time1)
        db.update_fetch_attempt_time(cursor, "latest", time2)
        conn.commit()

        last_attempt_time = db.get_fetch_attempt_time(cursor, "latest")
        assert last_attempt_time.astimezone(UTC).timestamp() == timestamp
    finally:
        conn.close()


def test_get_file_index_empty() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        file_index = db.get_file_index(cursor)
        assert file_index == {}
    finally:
        conn.close()


def test_insert_file_index_new() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        file = "scc20250512.html.gz"
        size = 30045
        db.insert_file_index(cursor, file, size)

        file_index = db.get_file_index(cursor)
        assert file_index[file] == size
    finally:
        conn.close()


def test_insert_file_index_update() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        file = "scc20250512.html.gz"
        size1 = 30045
        size2 = 30090
        db.insert_file_index(cursor, file, size1)
        db.insert_file_index(cursor, file, size2)

        file_index = db.get_file_index(cursor)
        assert file_index[file] == size2
    finally:
        conn.close()


def test_insert_file_index_multiple() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)
        cursor = conn.cursor()

        file1 = "scc20250512.html.gz"
        size1 = 30045
        db.insert_file_index(cursor, file1, size1)
        file2 = "scc20250513.html.gz"
        size2 = 32538
        db.insert_file_index(cursor, file2, size2)

        file_index = db.get_file_index(cursor)
        assert file_index[file1] == size1
        assert file_index[file2] == size2
    finally:
        conn.close()
