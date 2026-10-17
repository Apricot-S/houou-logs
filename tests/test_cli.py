# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
from argparse import ArgumentParser, Namespace
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from niquests import Response

from houou_logs import db
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
from houou_logs.yakuman import JST


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


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (
            timedelta(minutes=5, seconds=23),
            "Please retry in approximately 5m 30s.",
        ),
        (timedelta(minutes=1), "Please retry in approximately 1m."),
        (timedelta(seconds=12), "Please retry in approximately 20s."),
        (timedelta(seconds=1), "Please retry in approximately 10s."),
        (timedelta(microseconds=1), "Please retry in approximately 10s."),
        (timedelta(seconds=10), "Please retry in approximately 10s."),
        (
            timedelta(seconds=10, microseconds=1),
            "Please retry in approximately 20s.",
        ),
        (0, "Number of log entries inserted into the DB: 0"),
        (3, "Number of log entries inserted into the DB: 3"),
    ],
)
def test_fetch_cli_reports_result(
    capsys: pytest.CaptureFixture[str],
    result: int | timedelta,
    message: str,
) -> None:
    args = Namespace(db_path=Path("db.sqlite"), archive=False)
    with patch("houou_logs.fetch.fetch", return_value=result):
        fetch_cli(args)
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == f"{message}\n"


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


@pytest.mark.usefixtures("mock_yakuman")
@pytest.mark.parametrize(("year", "month"), [(2026, 10), (2027, 1)])
@pytest.mark.parametrize(("hour", "minute"), [(0, 0), (8, 59), (9, 0)])
@pytest.mark.parametrize("use_utc", [False, True])
def test_yakuman_cli_warns_for_jst_current_month(
    capsys: pytest.CaptureFixture,
    year: int,
    month: int,
    hour: int,
    minute: int,
    *,
    use_utc: bool,
) -> None:
    now = datetime(year, month, 1, hour, minute, tzinfo=JST)
    if use_utc:
        now = now.astimezone(UTC)
    args = Namespace(db_path=Path("db.sqlite"), year=year, month=month)
    yakuman_cli(args, now)
    assert (
        "Warning: This month is not finished yet." in capsys.readouterr().err
    )


@pytest.mark.usefixtures("mock_yakuman")
@pytest.mark.parametrize(
    ("year", "month", "previous_year", "previous_month"),
    [(2026, 10, 2026, 9), (2027, 1, 2026, 12)],
)
@pytest.mark.parametrize(("hour", "minute"), [(0, 0), (8, 59), (9, 0)])
@pytest.mark.parametrize("use_utc", [False, True])
def test_yakuman_cli_does_not_warn_for_jst_previous_month(
    capsys: pytest.CaptureFixture,
    year: int,
    month: int,
    previous_year: int,
    previous_month: int,
    hour: int,
    minute: int,
    *,
    use_utc: bool,
) -> None:
    now = datetime(year, month, 1, hour, minute, tzinfo=JST)
    if use_utc:
        now = now.astimezone(UTC)
    args = Namespace(
        db_path=Path("db.sqlite"),
        year=previous_year,
        month=previous_month,
    )
    yakuman_cli(args, now)
    assert "Warning:" not in capsys.readouterr().err


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
        ("--limit", str(2**63), f"invalid limit: {2**63}"),
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


@pytest.mark.parametrize("limit", [None, 1])
@pytest.mark.parametrize("offset", [-1, 2**63, 2**64])
def test_main_rejects_invalid_offset_before_database_access(
    limit: int | None,
    offset: int,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "db.sqlite"
    db_path.touch()
    output_dir = tmp_path / "xml"
    argv = ["export", str(db_path), str(output_dir), "--offset", str(offset)]
    if limit is not None:
        argv.extend(["--limit", str(limit)])

    with patch("houou_logs.db.open_db") as mock_open_db:
        assert main(argv) == USER_INPUT_ERROR_EXIT_CODE
        mock_open_db.assert_not_called()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"Error: invalid offset of export: {offset}\n"
    assert not output_dir.exists()


@pytest.mark.parametrize(
    ("command", "options"),
    [
        ("download", ["--limit", str(2**63 - 1)]),
        ("export", ["--limit", str(2**63 - 1)]),
        ("export", ["--limit", "1", "--offset", str(2**63 - 1)]),
    ],
)
def test_main_accepts_sqlite_integer_upper_bound(
    command: str,
    options: list[str],
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "db.sqlite"
    conn = db.open_db(db_path)
    try:
        db.setup_table(conn)
        conn.commit()
    finally:
        conn.close()
    argv = [command, str(db_path)]
    if command == "export":
        argv.append(str(tmp_path / "xml"))
    argv.extend(options)

    with patch("houou_logs.download.create_session"):
        assert main(argv) == SUCCESS_EXIT_CODE


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


@pytest.mark.parametrize("archive", [False, True])
def test_main_fetch_parse_error_preserves_attempt_time(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    *,
    archive: bool,
) -> None:
    now = datetime(2025, 9, 20, 11, tzinfo=UTC)
    mock_datetime = Mock(wraps=datetime)
    mock_datetime.now.return_value = now
    monkeypatch.setattr("houou_logs.fetch.datetime", mock_datetime)
    with (
        patch("houou_logs.fetch.create_session"),
        patch(
            "houou_logs.fetch.fetch_file_index_text",
            return_value="<html>Service unavailable</html>",
        ),
    ):
        argv = ["fetch", str(db_path)]
        if archive:
            argv.append("--archive")
        assert main(argv) == IO_ERROR_EXIT_CODE

    captured = capsys.readouterr()
    assert captured.err == "Response parse error: failed to parse file index\n"
    assert "Traceback" not in captured.out + captured.err
    conn = db.open_db(db_path)
    try:
        kind = "archive" if archive else "latest"
        assert db.get_fetch_attempt_time(conn.cursor(), kind) == now
        assert db.count_all_ids(conn.cursor()) == 0
        assert conn.execute("SELECT * FROM file_index").fetchall() == []
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("<html>Service unavailable</html>", "ykm array not found"),
        ("ykm=[foo];", "failed to parse ykm array"),
        ("ykm=['date' 'name',,];", "failed to parse ykm array"),
        ("ykm=['date'];", "invalid new ykm array length"),
        (
            "ykm=['date', 'name', 'data', [], 123];",
            "invalid new ykm array entry",
        ),
        ("ykm=[123];", "unsupported ykm array format"),
        (
            (
                "ykm=[['01/01 00:00', 'name', 'data', [], "
                "'2025010100gm-00a9-0000-00000000'], []];"
            ),
            "invalid old ykm array entry",
        ),
        (
            (
                "ykm=[['01/01 00:00', 'name', 'data', [], "
                "'2025010100gm-00a9-0000-00000000'], "
                "['01/01 01:00', 'name', 'data', [], 123]];"
            ),
            "invalid old ykm array entry",
        ),
        (
            (
                "ykm=['01/01 00:00', 'name', 'data', [], "
                "'2025010100gm-00a9-0000-00000000', "
                "'01/01 01:00', 'name', 'data', [], 123];"
            ),
            "invalid new ykm array entry",
        ),
    ],
)
def test_main_yakuman_parse_error_rolls_back(
    db_path: Path,
    capsys: pytest.CaptureFixture,
    text: str,
    message: str,
) -> None:
    with (
        patch("houou_logs.yakuman.create_session"),
        patch(
            "houou_logs.yakuman.fetch_yakuman_log_ids_text",
            return_value=text,
        ),
    ):
        assert (
            main(["yakuman", str(db_path), "2025", "1"]) == IO_ERROR_EXIT_CODE
        )

    captured = capsys.readouterr()
    assert "Response parse error:" in captured.err
    assert message in captured.err
    assert "Traceback" not in captured.out + captured.err
    conn = db.open_db(db_path)
    try:
        assert db.count_all_ids(conn.cursor()) == 0
    finally:
        conn.close()


@pytest.mark.parametrize("error_type", [RuntimeError, TypeError])
@pytest.mark.parametrize("command", ["fetch", "yakuman"])
def test_main_propagates_unexpected_parser_bugs(
    db_path: Path,
    command: str,
    error_type: type[Exception],
) -> None:
    if command == "fetch":
        response_function = "fetch_file_index_text"
        parser_function = "parse_file_index"
        argv = [command, str(db_path)]
    else:
        response_function = "fetch_yakuman_log_ids_text"
        parser_function = "iter_ids"
        argv = [command, str(db_path), "2025", "1"]
    with (
        patch(f"houou_logs.{command}.create_session"),
        patch(f"houou_logs.{command}.{response_function}", return_value=""),
        patch(
            f"houou_logs.{command}.{parser_function}",
            side_effect=error_type("unexpected bug"),
        ),
        pytest.raises(error_type, match="unexpected bug"),
    ):
        main(argv)


@pytest.mark.parametrize("error_type", [ValueError, RuntimeError, TypeError])
def test_main_yakuman_propagates_unexpected_parse_id_bug(
    db_path: Path,
    error_type: type[Exception],
) -> None:
    text = (
        "ykm=['01/01 00:00', 'name', 'data', [], "
        "'2025010100gm-00a9-0000-00000000'];"
    )
    with (
        patch("houou_logs.yakuman.create_session"),
        patch(
            "houou_logs.yakuman.fetch_yakuman_log_ids_text",
            return_value=text,
        ),
        patch("houou_logs.yakuman.parse_type", side_effect=error_type("bug")),
        pytest.raises(error_type, match="bug"),
    ):
        main(["yakuman", str(db_path), "2025", "1"])


@pytest.mark.parametrize("old_format", [False, True])
@pytest.mark.parametrize("invalid_field", ["date", "id"])
def test_main_yakuman_skips_invalid_log_and_commits_valid_logs(
    db_path: Path,
    capsys: pytest.CaptureFixture,
    invalid_field: str,
    *,
    old_format: bool,
) -> None:
    first_id = "2025010100gm-00a9-0000-00000000"
    last_id = "2025010102gm-00a9-0000-00000000"
    records = [
        ["01/01 00:00", "name", "data", [], first_id],
        [
            "invalid" if invalid_field == "date" else "01/01 01:00",
            "name",
            "data",
            [],
            "invalid"
            if invalid_field == "id"
            else "2025010101gm-00a9-0000-00000000",
        ],
        ["01/01 02:00", "name", "data", [], last_id],
    ]
    array = (
        records
        if old_format
        else [item for record in records for item in record]
    )
    with (
        patch("houou_logs.yakuman.create_session"),
        patch(
            "houou_logs.yakuman.fetch_yakuman_log_ids_text",
            return_value=f"ykm={array!r};",
        ),
    ):
        assert (
            main(["yakuman", str(db_path), "2025", "1"]) == SUCCESS_EXIT_CODE
        )
    captured = capsys.readouterr()
    field_label = "ID" if invalid_field == "id" else "date"
    assert f"invalid yakuman log {field_label}: invalid" in captured.out
    assert "Number of log entries inserted into the DB: 2" in captured.err
    assert "Response parse error:" not in captured.err
    conn = db.open_db(db_path)
    try:
        assert {row[0] for row in conn.execute("SELECT id FROM logs")} == {
            first_id,
            last_id,
        }
    finally:
        conn.close()


@pytest.mark.parametrize(
    "text",
    [
        "list([{file:'scc.html',size:100}, garbage]);",
        f"list([{{file:'scc.html',size:{2**63}}}]);",
    ],
)
def test_main_fetch_rejects_invalid_index_before_downloading(
    db_path: Path,
    text: str,
    capsys: pytest.CaptureFixture,
) -> None:
    with (
        patch("houou_logs.fetch.create_session"),
        patch("houou_logs.fetch.fetch_file_index_text", return_value=text),
        patch("houou_logs.fetch.fetch_log_file_content") as fetch_content,
    ):
        assert main(["fetch", str(db_path)]) == IO_ERROR_EXIT_CODE
        fetch_content.assert_not_called()
    captured = capsys.readouterr()
    assert "Response parse error:" in captured.err
    assert "Traceback" not in captured.out + captured.err
    conn = db.open_db(db_path)
    try:
        assert db.count_all_ids(conn.cursor()) == 0
        assert conn.execute("SELECT * FROM file_index").fetchall() == []
        assert db.get_fetch_attempt_time(conn.cursor(), "latest").year > 1970
    finally:
        conn.close()


@pytest.mark.parametrize(
    "content",
    [
        None,
        b"",
        b"\xff",
        b"not gzip",
        gzip.compress(b"<html>Service unavailable</html>"),
    ],
)
def test_main_fetch_handles_invalid_file_response(
    db_path: Path,
    capsys: pytest.CaptureFixture,
    content: bytes | None,
) -> None:
    response = Mock(spec_set=Response)
    response.content = content
    response.raise_for_status.return_value = None
    filename = "scc.html" if content == b"\xff" else "scc.html.gz"
    with (
        patch("houou_logs.fetch.create_session") as create_session,
        patch(
            "houou_logs.fetch.fetch_file_index_text",
            return_value=f"list([{{file:'{filename}',size:100}}]);",
        ),
    ):
        create_session.return_value.__enter__.return_value.get.return_value = (
            response
        )
        assert main(["fetch", str(db_path)]) == SUCCESS_EXIT_CODE
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err
    assert filename in captured.out
    assert "Number of log entries inserted into the DB: 0" in captured.err
    conn = db.open_db(db_path)
    try:
        assert db.count_all_ids(conn.cursor()) == 0
        assert conn.execute("SELECT * FROM file_index").fetchall() == []
    finally:
        conn.close()


@pytest.mark.parametrize("content", [None, b"\xff"])
def test_main_yakuman_handles_invalid_response_encoding(
    db_path: Path,
    content: bytes | None,
    capsys: pytest.CaptureFixture,
) -> None:
    response = Mock(spec_set=Response)
    response.content = content
    response.raise_for_status.return_value = None
    with patch("houou_logs.yakuman.create_session") as create_session:
        create_session.return_value.__enter__.return_value.get.return_value = (
            response
        )
        assert (
            main(["yakuman", str(db_path), "2025", "1"]) == IO_ERROR_EXIT_CODE
        )
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err
    assert "Number of log entries inserted" not in captured.err
