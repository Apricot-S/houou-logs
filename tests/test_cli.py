# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from argparse import ArgumentParser, Namespace
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from houou_logs.cli import extract_cli, set_extract_args, set_fetch_args


def test_set_extract_args_parses_correctly() -> None:
    parser = set_extract_args(ArgumentParser())
    args = parser.parse_args(["db.sqlite", "data.zip"])
    assert args.db_path == Path("db.sqlite")
    assert args.archive_path == Path("data.zip")


def test_set_extract_args_missing_args() -> None:
    parser = set_extract_args(ArgumentParser())
    with pytest.raises(SystemExit):
        parser.parse_args(["db.sqlite"])


@patch("houou_logs.extract.extract")
def test_extract_cli_calls_extract(mock_extract: Mock) -> None:
    args = Namespace(db_path=Path("db.sqlite"), archive_path=Path("data.zip"))
    extract_cli(args)
    mock_extract.assert_called_once_with(Path("db.sqlite"), Path("data.zip"))


def test_set_fetch_args_latest() -> None:
    parser = set_fetch_args(ArgumentParser())
    args = parser.parse_args(["db.sqlite"])
    assert args.db_path == Path("db.sqlite")
    assert not args.archive


def test_set_fetch_args_latest_archive() -> None:
    parser = set_fetch_args(ArgumentParser())
    args = parser.parse_args(["db.sqlite", "--archive"])
    assert args.db_path == Path("db.sqlite")
    assert args.archive


def test_set_fetch_args_missing_args() -> None:
    parser = set_fetch_args(ArgumentParser())
    with pytest.raises(SystemExit):
        parser.parse_args([])
