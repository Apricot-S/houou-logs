# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
from pathlib import Path
from typing import BinaryIO
from unittest.mock import patch

import pytest

from houou_logs import db
from houou_logs.cli import IO_ERROR_EXIT_CODE, SUCCESS_EXIT_CODE, main
from houou_logs.exceptions import UserInputError
from houou_logs.export import export, validate_offset


@pytest.mark.parametrize("offset", [0, 1, 2**63 - 1])
def test_validate_offset_accepts_valid_counts(offset: int) -> None:
    validate_offset(offset)


@pytest.mark.parametrize("offset", [-1, 2**63, 2**64])
def test_validate_offset_rejects_out_of_range(offset: int) -> None:
    with pytest.raises(UserInputError):
        validate_offset(offset)


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
    assert list(output_dir.iterdir()) == [output_file]


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
    assert list(output_dir.iterdir()) == [output_file]


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize(
    "failure",
    ["decompress", "write", "replace", "bug", "memory"],
)
def test_export_failure_preserves_destination_and_removes_temp_file(
    db_path: Path,
    tmp_path: Path,
    *,
    existing: bool,
    failure: str,
) -> None:
    log_id = "2025010100gm-00a9-0000-00000000"
    content = gzip.compress(b"<mjloggm />")
    if failure == "decompress":
        # Truncate the trailer to fail after reading data.
        content = content[:-4]

    with db.open_db(db_path) as conn:
        db.setup_table(conn)
        db.insert_log_entries(
            conn.cursor(),
            [
                db.LogEntry(
                    id=log_id,
                    date="2025-01-01T00:00",
                    num_players=4,
                    is_tonpu=False,
                    is_processed=True,
                    was_error=False,
                    log=content,
                ),
            ],
        )

    output_dir = tmp_path / "xml"
    output_dir.mkdir()
    output_file = output_dir / f"{log_id}.xml"
    if existing:
        output_file.write_bytes(b"original XML")

    def fail_after_partial_write(source: BinaryIO, target: BinaryIO) -> None:
        target.write(source.read(4))
        msg = "write failed"
        raise OSError(msg)

    def run_export() -> int:
        return export(db_path, output_dir, None, None, None, 0)

    if failure == "write":
        with (
            patch(
                "houou_logs.export.shutil.copyfileobj",
                side_effect=fail_after_partial_write,
            ),
            pytest.raises(OSError, match="write failed"),
        ):
            run_export()
        num_logs = 0
    elif failure == "replace":
        with (
            patch.object(
                Path,
                "replace",
                side_effect=OSError("replace failed"),
            ),
            pytest.raises(OSError, match="replace failed"),
        ):
            run_export()
        num_logs = 0
    elif failure in ("bug", "memory"):
        error_type = RuntimeError if failure == "bug" else MemoryError

        def fail_unexpectedly(source: BinaryIO, target: BinaryIO) -> None:
            target.write(source.read(4))
            raise error_type

        with (
            patch(
                "houou_logs.export.shutil.copyfileobj",
                side_effect=fail_unexpectedly,
            ),
            pytest.raises(error_type),
        ):
            run_export()
        num_logs = 0
    else:
        num_logs = run_export()

    assert num_logs == 0
    if existing:
        assert output_file.read_bytes() == b"original XML"
        assert list(output_dir.iterdir()) == [output_file]
    else:
        assert list(output_dir.iterdir()) == []


@pytest.mark.parametrize(
    "failure",
    ["create", "write", "replace", "bad-gzip", "truncated"],
)
def test_export_cli_distinguishes_output_errors_from_corrupt_gzip(
    db_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
    failure: str,
) -> None:
    log_id = "2025010100gm-00a9-0000-00000000"
    content = gzip.compress(b"<mjloggm />")
    if failure == "bad-gzip":
        content = b"not gzip"
    elif failure == "truncated":
        content = content[:-4]
    with db.open_db(db_path) as conn:
        db.setup_table(conn)
        db.insert_log_entries(
            conn.cursor(),
            [
                db.LogEntry(
                    id=log_id,
                    date="2025-01-01T00:00",
                    num_players=4,
                    is_tonpu=False,
                    is_processed=True,
                    was_error=False,
                    log=content,
                ),
            ],
        )

    output_dir = tmp_path / "xml"
    output_dir.mkdir()
    output_file = output_dir / f"{log_id}.xml"
    output_file.write_bytes(b"original XML")
    argv = ["export", str(db_path), str(output_dir)]

    def fail_write(source: BinaryIO, target: BinaryIO) -> None:
        target.write(source.read(4))
        msg = "disk full"
        raise OSError(msg)

    if failure == "create":
        with patch(
            "houou_logs.export.NamedTemporaryFile",
            side_effect=PermissionError("cannot create"),
        ):
            exit_code = main(argv)
    elif failure == "write":
        with patch(
            "houou_logs.export.shutil.copyfileobj",
            side_effect=fail_write,
        ):
            exit_code = main(argv)
    elif failure == "replace":
        with patch.object(
            Path,
            "replace",
            side_effect=PermissionError("cannot replace"),
        ):
            exit_code = main(argv)
    else:
        exit_code = main(argv)

    captured = capsys.readouterr()
    if failure in ("bad-gzip", "truncated"):
        assert exit_code == SUCCESS_EXIT_CODE
        assert "failed to decompress" in captured.out
        assert "Number of logs exported: 0" in captured.err
        assert "I/O error:" not in captured.err
    else:
        assert exit_code == IO_ERROR_EXIT_CODE
        assert "I/O error:" in captured.err
        assert "failed to decompress" not in captured.out + captured.err
        assert "Number of logs exported:" not in captured.err
        message = {
            "create": "cannot create",
            "write": "disk full",
            "replace": "cannot replace",
        }[failure]
        assert message in captured.err
    assert output_file.read_bytes() == b"original XML"
    assert list(output_dir.iterdir()) == [output_file]
