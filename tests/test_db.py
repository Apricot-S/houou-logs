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

    # Verify file exists
    assert db_path.exists()

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
