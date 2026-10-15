# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock
from zipfile import ZipFile, ZipInfo

import pytest

from houou_logs import db
from houou_logs.exceptions import UserInputError
from houou_logs.import_ import (
    import_,
    iter_houou_archive_files,
    validate_archive,
)


def test_validate_archive_raises_if_file_not_found() -> None:
    path = Path("missing.zip")
    with pytest.raises(UserInputError):
        validate_archive(path)


def test_validate_archive_raises_if_not_zipfile(tmp_path: Path) -> None:
    fake_file = tmp_path / "not_zip.txt"
    fake_file.write_text("not a zip")
    with pytest.raises(UserInputError):
        validate_archive(fake_file)


def test_validate_archive_passes_for_valid_zip(tmp_path: Path) -> None:
    zip_path = tmp_path / "valid.zip"
    with ZipFile(zip_path, "w") as zf:
        zf.writestr("dummy.txt", "hello")

    validate_archive(zip_path)


def test_iter_houou_archive_files_skips_directories() -> None:
    mock_info = MagicMock(spec_set=ZipInfo)
    mock_info.is_dir.return_value = True
    mock_info.filename = "some_dir/"

    zf = MagicMock(spec_set=ZipFile)
    zf.infolist.return_value = [mock_info]

    result = list(iter_houou_archive_files(zf))
    assert result == []


def test_iter_houou_archive_files_skips_non_matching_files() -> None:
    mock_info = MagicMock(spec_set=ZipInfo)
    mock_info.is_dir.return_value = False
    mock_info.filename = "unrelated_file.txt"

    zf = MagicMock(spec_set=ZipFile)
    zf.infolist.return_value = [mock_info]

    result = list(iter_houou_archive_files(zf))
    assert result == []


def test_iter_houou_archive_files_yields_matching_files() -> None:
    mock_info = MagicMock(spec_set=ZipInfo)
    mock_info.is_dir.return_value = False
    mock_info.filename = "2024/scc20240312.html.gz"

    zf = MagicMock(spec_set=ZipFile)
    zf.infolist.return_value = [mock_info]

    result = list(iter_houou_archive_files(zf))
    assert result == [mock_info]


@pytest.mark.parametrize("compressed", [False, True])
@pytest.mark.parametrize("failure", ["decode", "gzip", "database"])
def test_import_commits_completed_files_and_rolls_back_failed_file(
    tmp_path: Path,
    *,
    compressed: bool,
    failure: str,
) -> None:
    path = tmp_path / "logs.db"
    archive = tmp_path / "logs.zip"
    ids = [f"2025010100gm-00a9-0000-{i:08x}" for i in range(3)]
    lines = [f'00:00 log={log_id}">\n'.encode() for log_id in ids]
    suffix = ".html.gz" if compressed else ".html"
    with closing(db.open_db(path)) as conn, conn:
        db.setup_table(conn)
        if failure == "database":
            conn.execute(
                "CREATE TRIGGER reject_log BEFORE INSERT ON logs "
                f"WHEN NEW.id = '{ids[1]}' "
                "BEGIN SELECT RAISE(ABORT, 'insert failure'); END;",
            )
    with ZipFile(archive, "w") as zf:
        for i, line in enumerate(lines):
            content = line * 2
            if i == 1 and failure == "decode":
                content += b"\xff\n"
            if compressed:
                content = gzip.compress(content)
            filename = f"scc{i}{suffix}"
            if i == 1 and failure == "gzip":
                filename = "scc1.html.gz"
                content = gzip.compress(line * 2)[:-8]
            zf.writestr(filename, content)
    with pytest.raises((UnicodeDecodeError, EOFError, sqlite3.IntegrityError)):
        import_(path, archive)
    with closing(db.open_db(path)) as conn:
        assert conn.execute("SELECT id FROM logs").fetchall() == [(ids[0],)]
        assert conn.execute("SELECT * FROM file_index").fetchall() == []
        conn.execute("DROP TRIGGER IF EXISTS reject_log")
        conn.commit()
    # Repair and rerun the same archive; completed IDs remain unchanged.
    with ZipFile(archive, "w") as zf:
        for i, line in enumerate(lines):
            content = line * 2 + b'00:00 log=invalid">\n'
            if compressed:
                content = gzip.compress(content)
            zf.writestr(f"scc{i}{suffix}", content)
    assert import_(path, archive) == 2
    assert import_(path, archive) == 0
    with closing(db.open_db(path)) as conn:
        assert db.count_all_ids(conn.cursor()) == 3
