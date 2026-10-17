# SPDX-FileCopyrightText: 2026 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest
from tqdm import tqdm

from houou_logs import db
from houou_logs.export import export
from houou_logs.fetch import FetchResult, fetch
from houou_logs.import_ import import_
from houou_logs.log_id import parse_id
from houou_logs.yakuman import yakuman

LOG_IDS = [f"202501010{i}gm-00a9-0000-00000000" for i in range(3)]


def test_insert_log_entries_counts_only_new_ids(db_path: Path) -> None:
    entries = [parse_id("00:00", log_id) for log_id in LOG_IDS]
    with closing(db.open_db(db_path)) as conn:
        db.setup_table(conn)
        cursor = conn.cursor()
        assert db.insert_log_entries(cursor, entries[:1]) == 1
        assert db.insert_log_entries(cursor, [*entries, entries[-1]]) == 2
        assert db.insert_log_entries(cursor, entries) == 0
        assert db.insert_log_entries(cursor, []) == 0
        assert db.count_all_ids(cursor) == 3


@pytest.mark.parametrize("operation", ["import", "fetch", "yakuman"])
def test_import_operations_report_actual_insertions(
    db_path: Path,
    tmp_path: Path,
    operation: str,
) -> None:
    with closing(db.open_db(db_path)) as conn, conn:
        db.setup_table(conn)
        db.insert_log_entries(conn.cursor(), [parse_id("00:00", LOG_IDS[0])])

    html = "\n".join(
        f'00:00 <a href="?log={log_id}">log</a>'
        for log_id in [*LOG_IDS, LOG_IDS[-1]]
    )
    compressed = gzip.compress(html.encode())
    filename = "scc20250101.html.gz"

    if operation == "import":
        archive_path = tmp_path / "logs.zip"
        with ZipFile(archive_path, "w") as archive:
            archive.writestr(filename, compressed)
            archive.writestr("scc20250102.html.gz", compressed)
        assert import_(db_path, archive_path) == 2
        assert import_(db_path, archive_path) == 0
    elif operation == "fetch":
        index = {filename: len(compressed), "scc20250102.html.gz": 1}
        with (
            patch("houou_logs.fetch.create_session"),
            patch("houou_logs.fetch.should_fetch", return_value=True),
            patch("houou_logs.fetch.fetch_file_index_text", return_value=""),
            patch("houou_logs.fetch.parse_file_index", return_value=index),
            patch(
                "houou_logs.fetch.db.list_changed_file_index",
                return_value=index,
            ),
            patch(
                "houou_logs.fetch.fetch_log_file_content",
                return_value=compressed,
            ),
        ):
            assert fetch(db_path, archive=False) == FetchResult(2, 2)
            assert fetch(db_path, archive=False) == FetchResult(0, 2)
    else:
        ids = [("01/01 00:00", log_id) for log_id in [*LOG_IDS, LOG_IDS[-1]]]
        with (
            patch("houou_logs.yakuman.create_session"),
            patch(
                "houou_logs.yakuman.fetch_yakuman_log_ids_text",
                return_value="",
            ),
            patch("houou_logs.yakuman.iter_ids", return_value=ids),
        ):
            now = datetime(2025, 2, 1, tzinfo=UTC)
            assert yakuman(db_path, 2025, 1, now) == 2
            assert yakuman(db_path, 2025, 1, now) == 0

    with closing(db.open_db(db_path)) as conn:
        assert db.count_all_ids(conn.cursor()) == 3


@pytest.mark.parametrize(
    ("limit", "offset", "expected_indices"),
    [
        (None, 0, [0, 1, 2]),
        (None, 1, [0, 1, 2]),
        (None, 10, [0, 1, 2]),
        (1, 0, [0]),
        (1, 1, [1]),
        (10, 1, [1, 2]),
        (1, 3, []),
        (1, 10, []),
    ],
)
def test_export_count_matches_selection_and_progress(
    db_path: Path,
    tmp_path: Path,
    limit: int | None,
    offset: int,
    expected_indices: list[int],
) -> None:
    content = gzip.compress(b"<mjloggm />")
    with closing(db.open_db(db_path)) as conn, conn:
        db.setup_table(conn)
        cursor = conn.cursor()
        entries = [parse_id("00:00", log_id) for log_id in LOG_IDS]
        db.insert_log_entries(cursor, entries)
        for log_id in LOG_IDS:
            db.update_log_entries(cursor, log_id, False, content)  # noqa: FBT003
        assert db.count_log_contents(cursor, None, None, limit, offset) == len(
            expected_indices,
        )
        selected = list(
            db.iter_log_contents(cursor, None, None, limit, offset),
        )
        assert [log_id for log_id, _ in selected] == [
            LOG_IDS[i] for i in expected_indices
        ]

    output_dir = tmp_path / "xml"
    with patch("houou_logs.export.tqdm", wraps=tqdm) as progress:
        assert export(db_path, output_dir, None, None, limit, offset) == len(
            expected_indices,
        )
    assert progress.call_args.kwargs["total"] == len(expected_indices)
    assert sorted(path.name for path in output_dir.iterdir()) == [
        f"{LOG_IDS[i]}.xml" for i in expected_indices
    ]
