# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from pathlib import Path

from houou_logs import db


def test_open_db_create_file(db_path: Path) -> None:
    conn = db.open_db(db_path)
    try:
        assert conn is not None
    finally:
        conn.close()


def test_open_db_persists_after_reopen(db_path: Path) -> None:
    # 1st time: Create DB & insert data
    conn1 = db.open_db(db_path)
    conn1.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT)")
    conn1.execute("INSERT INTO users(name) VALUES (?)", ("Alice",))
    conn1.commit()
    conn1.close()

    # 2nd time: Reopen and check if the data is still there
    conn2 = db.open_db(db_path)
    row = conn2.execute("SELECT name FROM users").fetchone()
    conn2.close()

    assert row == ("Alice",)


def test_setup_table() -> None:
    conn = db.open_db(":memory:")

    try:
        db.setup_table(conn)

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='logs';",  # noqa: E501
        )
        table = cursor.fetchone()
        assert table is not None
        assert table[0] == "logs"
    finally:
        conn.close()


def test_insert_entries() -> None:
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

        db.insert_entries(cursor, entries)
        conn.commit()

        cursor.execute("SELECT * FROM logs;")
        rows = cursor.fetchall()
        assert len(rows) == len(entries)
    finally:
        conn.close()
