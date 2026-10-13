# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from argparse import ArgumentParser, Namespace
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from houou_logs.cli import (
    INTERRUPTED_EXIT_CODE,
    IO_ERROR_EXIT_CODE,
    SUCCESS_EXIT_CODE,
    USER_INPUT_ERROR_EXIT_CODE,
    download_cli,
    export_cli,
    fetch_cli,
    import_cli,
    main,
    set_download_args,
    set_export_args,
    set_fetch_args,
    set_import_args,
    set_validate_args,
    set_yakuman_args,
    validate_cli,
    yakuman_cli,
)
from houou_logs.exceptions import UserInputError


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
    mock_datetime.side_effect = datetime
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


def test_set_validate_args() -> None:
    parser = set_validate_args(ArgumentParser())
    args = parser.parse_args(["db.sqlite"])
    assert args.db_path == Path("db.sqlite")


@patch("houou_logs.validate.validate")
def test_validate_cli_calls_validate(mock_validate: Mock) -> None:
    mock_validate.return_value = (False, 1, 2)
    args = Namespace(db_path=Path("db.sqlite"))
    validate_cli(args)
    mock_validate.assert_called_once_with(Path("db.sqlite"))


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


@patch("houou_logs.export.export")
def test_export_cli_calls_export(mock_export: Mock) -> None:
    args = Namespace(
        db_path=Path("db.sqlite"),
        output_dir=Path("xml/"),
        players=4,
        length="h",
        limit=10,
        offset=5,
    )
    export_cli(args)
    mock_export.assert_called_once_with(
        Path("db.sqlite"),
        Path("xml"),
        4,
        "h",
        10,
        5,
    )


def test_main_requires_subcommand(
    capsys: pytest.CaptureFixture,
) -> None:
    with pytest.raises(SystemExit) as e:
        main([])

    assert e.value.code == USER_INPUT_ERROR_EXIT_CODE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "usage:" in captured.err
    assert "required" in captured.err


@pytest.mark.parametrize(
    "argv",
    [["fetch", "db.sqlite"], ("fetch", "db.sqlite")],
)
@patch("houou_logs.fetch.fetch")
def test_main_accepts_argument_sequence(
    mock_fetch: Mock,
    argv: Sequence[str],
) -> None:
    assert main(argv) == SUCCESS_EXIT_CODE
    mock_fetch.assert_called_once_with(Path("db.sqlite"), archive=False)


@patch("houou_logs.fetch.fetch")
def test_main_without_arguments_uses_sys_argv(
    mock_fetch: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["houou-logs", "fetch", "db.sqlite"])

    assert main() == SUCCESS_EXIT_CODE
    mock_fetch.assert_called_once_with(Path("db.sqlite"), archive=False)


@pytest.mark.parametrize("year", [-1, 0, 10000, 10001])
@patch("houou_logs.yakuman.create_session")
@patch("houou_logs.yakuman.db.open_db")
def test_main_rejects_invalid_yakuman_year_without_side_effects(
    mock_open_db: Mock,
    mock_create_session: Mock,
    year: int,
    capsys: pytest.CaptureFixture,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "db.sqlite"
    assert main(["yakuman", str(db_path), str(year), "1"]) == (
        USER_INPUT_ERROR_EXIT_CODE
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Error: year must be between 1 and 9999\n"
    mock_open_db.assert_not_called()
    mock_create_session.assert_not_called()
    assert not db_path.exists()


@patch("houou_logs.fetch.fetch")
def test_main_returns_user_input_error_code(
    mock_fetch: Mock,
    capsys: pytest.CaptureFixture,
) -> None:
    mock_fetch.side_effect = UserInputError("invalid option")
    assert main(["fetch", "db.sqlite"]) == USER_INPUT_ERROR_EXIT_CODE
    assert capsys.readouterr().err == "Error: invalid option\n"


@pytest.mark.parametrize("command", ["download", "export", "validate"])
def test_main_rejects_missing_database(
    command: str,
    capsys: pytest.CaptureFixture,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "missing.sqlite"
    output_dir = tmp_path / "xml"
    argv = [command, str(db_path)]
    if command == "export":
        argv.append(str(output_dir))

    assert main(argv) == USER_INPUT_ERROR_EXIT_CODE
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"Error: database file is not found: {db_path}\n"
    assert not db_path.exists()
    assert not output_dir.exists()


@pytest.mark.parametrize("command", ["download", "export"])
@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--players", "2", "invalid number of players: 2"),
        ("--length", "x", "invalid length of game: x"),
        ("--limit", "0", "invalid limit: 0"),
        ("--limit", "-1", "invalid limit: -1"),
    ],
)
def test_main_rejects_invalid_common_options_before_database_access(
    command: str,
    option: str,
    value: str,
    message: str,
    capsys: pytest.CaptureFixture,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "db.sqlite"
    db_path.touch()
    output_dir = tmp_path / "xml"
    argv = [command, str(db_path)]
    if command == "export":
        argv.append(str(output_dir))
    argv.extend([option, value])

    with patch("houou_logs.db.open_db") as mock_open_db:
        assert main(argv) == USER_INPUT_ERROR_EXIT_CODE
        mock_open_db.assert_not_called()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"Error: {message}\n"
    assert not output_dir.exists()


@patch("houou_logs.fetch.fetch")
def test_main_returns_io_error_code_without_traceback(
    mock_fetch: Mock,
    capsys: pytest.CaptureFixture,
) -> None:
    mock_fetch.side_effect = OSError("network is unreachable")
    assert main(["fetch", "db.sqlite"]) == IO_ERROR_EXIT_CODE
    captured = capsys.readouterr()
    assert captured.err == "I/O error: network is unreachable\n"
    assert "Traceback" not in captured.err


@patch("houou_logs.fetch.fetch")
def test_main_returns_interrupted_code_without_traceback(
    mock_fetch: Mock,
    capsys: pytest.CaptureFixture,
) -> None:
    mock_fetch.side_effect = KeyboardInterrupt
    assert main(["fetch", "db.sqlite"]) == INTERRUPTED_EXIT_CODE
    captured = capsys.readouterr()
    assert captured.err == "Interrupted by user.\n"
    assert "Traceback" not in captured.err
