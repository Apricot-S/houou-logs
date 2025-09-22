# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from pathlib import Path
from unittest.mock import MagicMock
from zipfile import ZipFile, ZipInfo

import pytest

from houou_logs.exceptions import UserInputError
from houou_logs.import_ import iter_houou_archive_files, validate_archive


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
