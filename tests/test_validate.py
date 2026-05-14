# SPDX-FileCopyrightText: 2026 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import sqlite3
from pathlib import Path

import pytest

from houou_logs import db
from houou_logs import validate as validate_module


def compress_log(content: str) -> bytes:
    return gzip.compress(content.encode("utf-8"), mtime=0)


def valid_log() -> bytes:
    return compress_log(
        """
        <mjloggm ver="2.3">
            <INIT seed="0,0,0,0,0,0" ten="25000,25000,25000,25000" />
            <AGARI owari="25000,0,25000,0,25000,0,25000,0" />
        </mjloggm>
        """,
    )


def insert_processed_log(
    cursor: sqlite3.Cursor,
    log_id: str,
    log: bytes,
) -> None:
    db.insert_log_entries(
        cursor,
        [
            db.LogEntry(
                id=log_id,
                date="2025-01-01",
                num_players=4,
                is_tonpu=False,
                is_processed=True,
                was_error=False,
                log=log,
            ),
        ],
    )


def test_validate_continues_after_resetting_invalid_log(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = db.open_db(db_path)
    try:
        db.setup_table(conn)
        cursor = conn.cursor()
        insert_processed_log(
            cursor,
            "2025010100gm-00a9-0000-00000000",
            valid_log(),
        )
        insert_processed_log(
            cursor,
            "2025010101gm-00a9-0000-00000000",
            b"not gzip data",
        )
        insert_processed_log(
            cursor,
            "2025010102gm-00a9-0000-00000000",
            valid_log(),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(validate_module, "VALIDATE_BATCH_SIZE", 2)

    assert validate_module.validate(db_path) == (True, 2, 3)

    conn = db.open_db(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, is_processed, was_error, log
            FROM logs
            ORDER BY id ASC;
            """,
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    assert rows[0][1:] == (1, 0, valid_log())
    assert rows[1] == (
        "2025010101gm-00a9-0000-00000000",
        0,
        0,
        None,
    )
    assert rows[2][1:] == (1, 0, valid_log())
