# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from argparse import ArgumentParser, Namespace
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from zipfile import ZipFile, ZipInfo

import pytest

from houou_logs.extract import (
    extract_cli,
    iter_houou_archive_files,
    set_args,
    validate_archive,
)


def test_set_args_parses_correctly() -> None:
    parser = set_args(ArgumentParser())
    args = parser.parse_args(["db.sqlite", "data.zip"])
    assert args.db_path == Path("db.sqlite")
    assert args.archive_path == Path("data.zip")


def test_set_args_missing_args() -> None:
    parser = set_args(ArgumentParser())
    with pytest.raises(SystemExit):
        parser.parse_args(["db.sqlite"])


@patch("houou_logs.extract.extract")
def test_extract_cli_calls_extract(mock_extract: Mock) -> None:
    args = Namespace(db_path=Path("db.sqlite"), archive_path=Path("data.zip"))
    extract_cli(args)
    mock_extract.assert_called_once_with(Path("db.sqlite"), Path("data.zip"))


def test_validate_archive_raises_if_file_not_found() -> None:
    path = Path("missing.zip")
    with pytest.raises(FileNotFoundError):
        validate_archive(path)


def test_validate_archive_raises_if_not_zipfile(tmp_path: Path) -> None:
    fake_file = tmp_path / "not_zip.txt"
    fake_file.write_text("not a zip")
    with pytest.raises(ValueError, match="archive file must be zip file"):
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
    mock_info.filename = "scc20240312.html.gz"

    zf = MagicMock(spec_set=ZipFile)
    zf.infolist.return_value = [mock_info]

    result = list(iter_houou_archive_files(zf))
    assert result == [mock_info]
