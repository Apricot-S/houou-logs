# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
from pathlib import Path

import pytest

from houou_logs import db
from houou_logs.exceptions import UserInputError
from houou_logs.export import export, validate_offset


@pytest.mark.parametrize("offset", [0, 1])
def test_validate_offset_accepts_valid_counts(offset: int) -> None:
    validate_offset(offset)


def test_validate_offset_rejects_out_of_range() -> None:
    with pytest.raises(UserInputError):
        validate_offset(-1)


def test_export_writes_utf8_and_overwrites_existing_file(
    db_path: Path,
    tmp_path: Path,
) -> None:
    conn = db.open_db(db_path)
    try:
        db.setup_table(conn)
        cursor = conn.cursor()
        log_id = "2025010100gm-00a9-0000-00000000"
        entry = db.LogEntry(
            id=log_id,
            date="2025-01-01T00:00",
            num_players=4,
            is_tonpu=False,
            is_processed=True,
            was_error=False,
            log=gzip.compress("<mjloggm>東</mjloggm>".encode()),
        )
        db.insert_log_entries(cursor, [entry])
        conn.commit()
    finally:
        conn.close()

    output_dir = tmp_path / "xml"
    output_dir.mkdir()
    output_file = output_dir / f"{log_id}.xml"
    output_file.write_text("old content", encoding="utf-8")

    num_logs = export(db_path, output_dir, None, None, None, 0)

    assert num_logs == 1
    assert output_file.read_text(encoding="utf-8") == "<mjloggm>東</mjloggm>"


def test_export_writes_decompressed_bytes_without_utf8_validation(
    db_path: Path,
    tmp_path: Path,
) -> None:
    conn = db.open_db(db_path)
    try:
        db.setup_table(conn)
        cursor = conn.cursor()
        log_id = "2025010100gm-00a9-0000-00000000"
        entry = db.LogEntry(
            id=log_id,
            date="2025-01-01T00:00",
            num_players=4,
            is_tonpu=False,
            is_processed=True,
            was_error=False,
            log=gzip.compress(b"<mjloggm>\xff</mjloggm>"),
        )
        db.insert_log_entries(cursor, [entry])
        conn.commit()
    finally:
        conn.close()

    output_dir = tmp_path / "xml"

    num_logs = export(db_path, output_dir, None, None, None, 0)

    assert num_logs == 1
    output_file = output_dir / f"{log_id}.xml"
    assert output_file.read_bytes() == b"<mjloggm>\xff</mjloggm>"
