# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from argparse import ArgumentParser, Namespace
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from houou_logs.cli import (
    download_cli,
    fetch_cli,
    import_cli,
    set_download_args,
    set_export_args,
    set_fetch_args,
    set_import_args,
    set_yakuman_args,
    yakuman_cli,
)


def test_set_import_args_parses_correctly() -> None:
    parser = set_import_args(ArgumentParser())
    args = parser.parse_args(["db.sqlite", "data.zip"])
    assert args.db_path == Path("db.sqlite")
    assert args.archive_path == Path("data.zip")


def test_set_import_args_missing_args() -> None:
    parser = set_import_args(ArgumentParser())
    with pytest.raises(SystemExit):
        parser.parse_args(["db.sqlite"])


@patch("houou_logs.import_.import_")
def test_import_cli_calls_import(mock_import: Mock) -> None:
    args = Namespace(db_path=Path("db.sqlite"), archive_path=Path("data.zip"))
    import_cli(args)
    mock_import.assert_called_once_with(Path("db.sqlite"), Path("data.zip"))


def test_set_fetch_args_latest() -> None:
    parser = set_fetch_args(ArgumentParser())
    args = parser.parse_args(["db.sqlite"])
    assert args.db_path == Path("db.sqlite")
    assert not args.archive


def test_set_fetch_args_archive() -> None:
    parser = set_fetch_args(ArgumentParser())
    args = parser.parse_args(["db.sqlite", "--archive"])
    assert args.db_path == Path("db.sqlite")
    assert args.archive


def test_set_fetch_args_missing_args() -> None:
    parser = set_fetch_args(ArgumentParser())
    with pytest.raises(SystemExit):
        parser.parse_args([])


@patch("houou_logs.fetch.fetch")
def test_fetch_cli_calls_fetch(mock_fetch: Mock) -> None:
    args = Namespace(db_path=Path("db.sqlite"), archive=True)
    fetch_cli(args)
    mock_fetch.assert_called_once_with(Path("db.sqlite"), archive=True)


def test_set_yakuman_args() -> None:
    parser = set_yakuman_args(ArgumentParser())
    args = parser.parse_args(["db.sqlite", "2007", "01"])
    assert args.db_path == Path("db.sqlite")
    assert args.year == 2007
    assert args.month == 1


def test_set_yakuman_args_missing_args() -> None:
    parser = set_yakuman_args(ArgumentParser())
    with pytest.raises(SystemExit):
        parser.parse_args([])


@patch("houou_logs.cli.datetime")
@patch("houou_logs.yakuman.yakuman")
def test_yakuman_cli_calls_yakuman_for_current_month(
    mock_yakuman: Mock,
    mock_datetime: Mock,
) -> None:
    now = datetime(2025, 9, 23, 1, 52, 12, 0, UTC)
    mock_datetime.now.return_value = now
    args = Namespace(db_path=Path("db.sqlite"), year=2025, month=9)
    yakuman_cli(args)
    mock_yakuman.assert_called_once_with(Path("db.sqlite"), 2025, 9, now)


@pytest.fixture
def mock_yakuman() -> Iterator:
    with patch("houou_logs.yakuman.yakuman") as m:
        yield m


@patch("houou_logs.cli.datetime")
@pytest.mark.usefixtures("mock_yakuman")
def test_yakuman_cli_warns_yakuman_for_current_month(
    mock_datetime: Mock,
    capsys: pytest.CaptureFixture,
) -> None:
    now = datetime(2025, 9, 23, 1, 52, 12, 0, UTC)
    mock_datetime.now.return_value = now
    mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)  # noqa: DTZ001
    args = Namespace(db_path=Path("db.sqlite"), year=2025, month=9)
    yakuman_cli(args)
    captured = capsys.readouterr()
    assert "Warning: This month is not finished yet." in captured.err


def test_set_download_args_without_options() -> None:
    parser = set_download_args(ArgumentParser())
    args = parser.parse_args(["db.sqlite"])
    assert args.db_path == Path("db.sqlite")
    assert args.players is None
    assert args.length is None
    assert args.limit is None


def test_set_download_args_with_options() -> None:
    parser = set_download_args(ArgumentParser())
    args = parser.parse_args(
        ["db.sqlite", "-p", "4", "-l", "t", "--limit", "50"],
    )
    assert args.db_path == Path("db.sqlite")
    assert args.players == 4
    assert args.length == "t"
    assert args.limit == 50


@patch("houou_logs.download.download")
def test_download_cli_calls_download(mock_download: Mock) -> None:
    args = Namespace(db_path=Path("db.sqlite"), players=4, length="h", limit=1)
    download_cli(args)
    mock_download.assert_called_once_with(Path("db.sqlite"), 4, "h", 1)


def test_set_export_args_without_options() -> None:
    parser = set_export_args(ArgumentParser())
    args = parser.parse_args(["db.sqlite", "xml/"])
    assert args.db_path == Path("db.sqlite")
    assert args.output_dir == Path("xml")
    assert args.players is None
    assert args.length is None
    assert args.limit is None
    assert args.offset == 0


def test_set_export_args_with_options() -> None:
    parser = set_export_args(ArgumentParser())
    args = parser.parse_args(
        [
            "db.sqlite",
            "xml/",
            "-p",
            "4",
            "-l",
            "t",
            "--limit",
            "50",
            "--offset",
            "10",
        ],
    )
    assert args.db_path == Path("db.sqlite")
    assert args.output_dir == Path("xml")
    assert args.players == 4
    assert args.length == "t"
    assert args.limit == 50
    assert args.offset == 10
