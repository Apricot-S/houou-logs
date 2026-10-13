# SPDX-FileCopyrightText: 2026 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import sqlite3
from collections.abc import Generator
from functools import partial
from itertools import product

import pytest

from houou_logs import db


@pytest.fixture(params=[0, 1, 2], ids=["legacy", "indexed", "two_indexes"])
def count_db(request: pytest.FixtureRequest) -> Generator[sqlite3.Connection]:
    conn = db.open_db(":memory:")
    try:
        db.create_logs_table(conn)
        if request.param:
            db.create_logs_status_filter_index(conn)
        if request.param == 2:
            db.create_logs_indexes(conn)
        entries = (
            db.LogEntry(
                id=f"{i:08d}",
                date="2025-01-01",
                num_players=players,
                is_tonpu=tonpu,
                is_processed=processed,
                was_error=error,
                log=b"content" if processed else None,
            )
            for i, (players, tonpu, processed, error, _) in enumerate(
                product(
                    (3, 4),
                    (False, True),
                    (False, True),
                    (False, True),
                    range(3),
                ),
            )
        )
        db.insert_log_entries(conn.cursor(), entries)
        yield conn
    finally:
        conn.close()


@pytest.mark.parametrize("players", [None, 3, 4])
@pytest.mark.parametrize("length", [None, "t", "h"])
@pytest.mark.parametrize("limit", [None, 0, 2, 3, 4, 12, 20])
def test_download_count_matches_selection(
    count_db: sqlite3.Connection,
    players: int | None,
    length: str | None,
    limit: int | None,
) -> None:
    cursor = count_db.cursor()
    total = (2 if players is None else 1) * (2 if length is None else 1) * 3
    expected = total if limit is None else min(total, limit)
    assert (
        db.count_undownloaded_log_ids(cursor, players, length, limit)
        == expected
    )
    selected = db.list_undownloaded_log_ids_after(
        cursor,
        players,
        length,
        None,
        total if limit is None else limit,
    )
    assert len(selected) == expected


@pytest.mark.parametrize("players", [None, 3, 4])
@pytest.mark.parametrize("length", [None, "t", "h"])
@pytest.mark.parametrize("limit", [None, 0, 2, 3, 4, 12, 20])
@pytest.mark.parametrize("offset", [0, 1, 3, 12, 20])
def test_export_count_matches_selection(
    count_db: sqlite3.Connection,
    players: int | None,
    length: str | None,
    limit: int | None,
    offset: int,
) -> None:
    cursor = count_db.cursor()
    total = (2 if players is None else 1) * (2 if length is None else 1) * 3
    expected = total if limit is None else min(max(total - offset, 0), limit)
    assert (
        db.count_log_contents(cursor, players, length, limit, offset)
        == expected
    )
    selected = list(
        db.iter_log_contents(cursor, players, length, limit, offset),
    )
    assert len(selected) == expected


@pytest.mark.parametrize("players", [None, 3, 4])
@pytest.mark.parametrize("length", ["", "x", "T"])
@pytest.mark.parametrize(
    "query",
    [
        "list_undownloaded_log_ids_after",
        "count_undownloaded_log_ids",
        "iter_log_contents",
        "count_log_contents",
    ],
)
def test_log_queries_reject_unknown_length(
    count_db: sqlite3.Connection,
    players: int | None,
    length: str,
    query: str,
) -> None:
    statements: list[str] = []
    count_db.set_trace_callback(statements.append)
    cursor = count_db.cursor()
    queries = {
        "list_undownloaded_log_ids_after": partial(
            db.list_undownloaded_log_ids_after,
            cursor,
            players,
            length,
            None,
            10,
        ),
        "count_undownloaded_log_ids": partial(
            db.count_undownloaded_log_ids,
            cursor,
            players,
            length,
            10,
        ),
        "iter_log_contents": partial(
            list,
            db.iter_log_contents(cursor, players, length, 10, 0),
        ),
        "count_log_contents": partial(
            db.count_log_contents,
            cursor,
            players,
            length,
            10,
            0,
        ),
    }
    assert statements == []
    with pytest.raises(ValueError, match=f"^unknown length: {length}$"):
        queries[query]()
    assert statements == []


@pytest.mark.parametrize("processed", [False, True])
def test_limited_counts_stop_before_scanning_all_matches(
    processed: bool,  # noqa: FBT001
) -> None:
    conn = db.open_db(":memory:")
    try:
        db.setup_table(conn)
        db.insert_log_entries(
            conn.cursor(),
            (
                db.LogEntry(
                    id=f"{i:08d}",
                    date="2025-01-01",
                    num_players=4,
                    is_tonpu=False,
                    is_processed=processed,
                    was_error=False,
                    log=b"content" if processed else None,
                )
                for i in range(10_000)
            ),
        )
        # A full count exceeds this budget of 5,000 VM instructions.
        conn.set_progress_handler(lambda: 1, 5_000)
        if processed:
            assert (
                db.count_log_contents(conn.cursor(), 4, "h", 100, 100) == 100
            )
        else:
            assert (
                db.count_undownloaded_log_ids(conn.cursor(), 4, "h", 100)
                == 100
            )
    finally:
        conn.set_progress_handler(None, 0)
        conn.close()


@pytest.mark.parametrize("limit", [None, 100])
def test_counts_on_empty_database(
    count_db: sqlite3.Connection,
    limit: int | None,
) -> None:
    cursor = count_db.cursor()
    cursor.execute("DELETE FROM logs")
    assert db.count_undownloaded_log_ids(cursor, None, None, limit) == 0
    assert db.count_log_contents(cursor, None, None, limit, 100) == 0
