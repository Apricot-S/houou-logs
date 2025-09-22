# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from argparse import ArgumentParser, Namespace
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from houou_logs.cli import (
    fetch_cli,
    import_cli,
    set_fetch_args,
    set_import_args,
    set_yakuman_args,
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
