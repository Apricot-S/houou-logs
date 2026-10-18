# SPDX-FileCopyrightText: 2026 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from houou_logs import db, download, export, validate


def assert_logs_indexes(conn: sqlite3.Connection) -> None:
    expected = {
        "idx_logs_status_filter": [
            "is_processed",
            "was_error",
            "num_players",
            "is_tonpu",
            "id",
        ],
        "idx_logs_status_id": [
            "is_processed",
            "was_error",
            "id",
            "num_players",
            "is_tonpu",
        ],
    }
    indexes = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='index' AND tbl_name='logs'",
    )
    assert {row[0] for row in indexes} == expected.keys()
    for name, columns in expected.items():
        actual = conn.execute(f"PRAGMA index_info({name})")
        assert [row[2] for row in actual] == columns


def test_setup_table_creates_both_logs_indexes() -> None:
    with closing(db.open_db(":memory:")) as conn:
        db.setup_table(conn)
        assert_logs_indexes(conn)


@pytest.mark.parametrize("existing_indexes", [0, 1, 2])
@pytest.mark.parametrize("command", ["download", "export", "validate"])
def test_commands_upgrade_legacy_logs_indexes_without_changing_data(
    db_path: Path,
    tmp_path: Path,
    existing_indexes: int,
    command: str,
) -> None:
    with closing(db.open_db(db_path)) as conn, conn:
        db.create_logs_table(conn)
        if existing_indexes:
            db.create_logs_status_filter_index(conn)
        if existing_indexes == 2:
            db.create_logs_indexes(conn)
        db.insert_log_entries(
            conn.cursor(),
            [
                db.LogEntry(
                    "2025010100gm-00f1-0000-00000000",
                    "2025-01-01T00:00",
                    3,
                    is_tonpu=True,
                    is_processed=False,
                    was_error=False,
                    log=None,
                ),
            ],
        )
        before = conn.execute("SELECT * FROM logs").fetchall()

    # Run twice to verify persistence and idempotence.
    # The download filter excludes the row, so no request is made.
    for _ in range(2):
        match command:
            case "download":
                assert (
                    download.download(
                        db_path,
                        4,
                        None,
                        None,
                    )
                    == download.DownloadResult()
                )
            case "export":
                assert (
                    export.export(
                        db_path,
                        tmp_path / "xml",
                        None,
                        None,
                        None,
                        0,
                    )
                    == 0
                )
            case "validate":
                assert validate.validate(db_path) == validate.ValidateResult(
                    num_ids=1,
                )
        with closing(db.open_db(db_path)) as conn:
            assert_logs_indexes(conn)
            assert conn.execute("SELECT * FROM logs").fetchall() == before


@pytest.mark.parametrize("processed", [False, True])
@pytest.mark.parametrize("players", [None, 3, 4])
@pytest.mark.parametrize("length", [None, "t", "h"])
def test_logs_selection_avoids_temporary_sort(
    processed: bool,  # noqa: FBT001
    players: int | None,
    length: str | None,
) -> None:
    with closing(db.open_db(":memory:")) as conn:
        db.setup_table(conn)
        db.insert_log_entries(
            conn.cursor(),
            (
                db.LogEntry(
                    f"{i:08d}",
                    "2025-01-01",
                    3 + i % 2,
                    is_tonpu=bool((i // 2) % 2),
                    is_processed=processed,
                    was_error=False,
                    log=b"content" if processed else None,
                )
                for i in range(1000)
            ),
        )
        statements: list[str] = []
        conn.set_trace_callback(statements.append)
        cursor = conn.cursor()
        if processed:
            rows = list(db.iter_log_contents(cursor, players, length, 10, 0))
            ids = [row[0] for row in rows]
        else:
            ids = db.list_undownloaded_log_ids_after(
                cursor,
                players,
                length,
                "00000010",
                10,
            )
        conn.set_trace_callback(None)
        assert ids == sorted(ids)
        assert len(ids) == 10
        plan = conn.execute("EXPLAIN QUERY PLAN " + statements[-1])
        assert all("TEMP B-TREE" not in row[3] for row in plan)
