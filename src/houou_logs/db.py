# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import sqlite3
from pathlib import Path


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
