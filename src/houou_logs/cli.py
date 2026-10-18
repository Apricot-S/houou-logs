# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from gzip import BadGzipFile
from pathlib import Path

from niquests.exceptions import RequestException

from houou_logs import download, export, fetch, import_, validate, yakuman
from houou_logs.exceptions import ExternalResponseParseError, UserInputError

SUCCESS_EXIT_CODE = 0
IO_ERROR_EXIT_CODE = 1
USER_INPUT_ERROR_EXIT_CODE = 2
INTERRUPTED_EXIT_CODE = 130
EXTERNAL_IO_ERRORS = (
    OSError,
    sqlite3.Error,
    BadGzipFile,
    EOFError,
    zlib.error,
    zipfile.BadZipFile,
    ET.ParseError,
    UnicodeDecodeError,
    RequestException,
)


def set_import_args(parser: ArgumentParser) -> ArgumentParser:
    parser.add_argument(
        "db_path",
        type=Path,
        help="Path to the SQLite database file.",
        metavar="db-path",
    )
    parser.add_argument(
        "archive_path",
        type=Path,
        help="Path to an archive file (.zip).",
        metavar="archive-path",
    )
    return parser


def import_cli(args: Namespace) -> None:
    num_logs = import_.import_(args.db_path, args.archive_path)
    print(
        f"Number of log entries inserted into the DB: {num_logs}",
        file=sys.stderr,
    )


def set_fetch_args(parser: ArgumentParser) -> ArgumentParser:
    parser.add_argument(
        "db_path",
        type=Path,
        help="Path to the SQLite database file.",
        metavar="db-path",
    )
    parser.add_argument(
        "-a",
        "--archive",
        action="store_true",
        help="Fetch log IDs from Jan 1 of the current year through 7 days ago.",  # noqa: E501
    )
    return parser


def format_retry_delay(remaining: timedelta) -> str:
    step = timedelta(seconds=10)
    seconds = -(-remaining // step) * 10
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if minutes:
        parts.append(f"{minutes}m")
    if seconds:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def fetch_cli(args: Namespace) -> int:
    result = fetch.fetch(args.db_path, archive=args.archive)
    if isinstance(result, timedelta):
        delay = format_retry_delay(result)
        print(f"Please retry in approximately {delay}.", file=sys.stderr)
        return SUCCESS_EXIT_CODE

    print(
        f"Number of log entries inserted into the DB: {result.num_inserted}",
        file=sys.stderr,
    )
    print(
        f"Number of list files fetched: {result.num_succeeded}",
        file=sys.stderr,
    )
    print(f"Number of list files failed: {result.num_failed}", file=sys.stderr)
    if result.stopped:
        print("Fetch stopped due to a temporary error.", file=sys.stderr)
    if result.num_failed or result.stopped:
        return IO_ERROR_EXIT_CODE
    return SUCCESS_EXIT_CODE


def set_yakuman_args(parser: ArgumentParser) -> ArgumentParser:
    parser.add_argument(
        "db_path",
        type=Path,
        help="Path to the SQLite database file.",
        metavar="db-path",
    )
    parser.add_argument(
        "year",
        type=int,
        help="Year to fetch for yakuman logs (e.g., 2006).",
    )
    parser.add_argument(
        "month",
        type=int,
        help="Month to fetch for yakuman logs (1-12).",
    )
    return parser


def yakuman_cli(args: Namespace, now: datetime | None = None) -> None:
    if now is None:
        now = datetime.now(UTC)

    now_jst = now.astimezone(yakuman.JST)
    if args.year == now_jst.year and args.month == now_jst.month:
        print(
            "Warning: This month is not finished yet. More logs may appear later.",  # noqa: E501
            file=sys.stderr,
        )

    num_logs = yakuman.yakuman(args.db_path, args.year, args.month, now)
    print(
        f"Number of log entries inserted into the DB: {num_logs}",
        file=sys.stderr,
    )


def set_download_args(parser: ArgumentParser) -> ArgumentParser:
    parser.add_argument(
        "db_path",
        type=Path,
        help="Path to the SQLite database file.",
        metavar="db-path",
    )
    parser.add_argument(
        "-p",
        "--players",
        type=int,
        help="Number of players. If omitted, both are included.",
    )
    parser.add_argument(
        "-l",
        "--length",
        type=str,
        help="Game length: 't' for tonpu (East Only), 'h' for hanchan (Two-Wind Match). If omitted, both are included.",  # noqa: E501
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Max number of logs to process, including failures. If omitted, all available logs are processed.",  # noqa: E501
    )
    return parser


def download_cli(args: Namespace) -> int:
    result = download.download(
        args.db_path,
        args.players,
        args.length,
        args.limit,
    )
    print(f"Number of logs processed: {result.num_processed}", file=sys.stderr)
    print(
        f"Number of logs downloaded: {result.num_succeeded}",
        file=sys.stderr,
    )
    print(f"Number of logs failed: {result.num_failed}", file=sys.stderr)

    if result.stopped:
        print("Download stopped due to a temporary error.", file=sys.stderr)
    if result.num_failed or result.stopped:
        return IO_ERROR_EXIT_CODE
    return SUCCESS_EXIT_CODE


def set_validate_args(parser: ArgumentParser) -> ArgumentParser:
    parser.add_argument(
        "db_path",
        type=Path,
        help="Path to the SQLite database file.",
        metavar="db-path",
    )
    return parser


def validate_cli(args: Namespace) -> None:
    were_errors, num_valid, total = validate.validate(args.db_path)
    if not were_errors:
        print(
            f"Everything is fine, checked {num_valid}/{total} (valid logs / all IDs)",  # noqa: E501
            file=sys.stderr,
        )


def set_export_args(parser: ArgumentParser) -> ArgumentParser:
    parser.add_argument(
        "db_path",
        type=Path,
        help="Path to the SQLite database file.",
        metavar="db-path",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Path to the directory where the log contents will be exported. The directory will be created if it does not exist.",  # noqa: E501
        metavar="output-dir",
    )
    parser.add_argument(
        "-p",
        "--players",
        type=int,
        help="Number of players. If omitted, both are included.",
    )
    parser.add_argument(
        "-l",
        "--length",
        type=str,
        help="Game length: 't' for tonpu (East Only), 'h' for hanchan (Two-Wind Match). If omitted, both are included.",  # noqa: E501
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Max number of logs to export. If omitted, all available logs are exported.",  # noqa: E501
    )
    parser.add_argument(
        "--offset",
        type=int,
        help="Number of logs to skip before starting export. Default is 0. Ignored if '--limit' is not specified.",  # noqa: E501
        default=0,
    )
    return parser


def export_cli(args: Namespace) -> None:
    num_logs = export.export(
        args.db_path,
        args.output_dir,
        args.players,
        args.length,
        args.limit,
        args.offset,
    )
    print(f"Number of logs exported: {num_logs}", file=sys.stderr)


def format_external_io_error(error: Exception) -> str:
    message = str(error) or error.__class__.__name__
    return f"I/O error: {message}"


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="Tools to download Houou (Phoenix) logs from tenhou.net",
    )
    subparsers = parser.add_subparsers(required=True)

    parser_import = subparsers.add_parser(
        "import",
        description="Import log IDs from a yearly archive file",
        help="Import log IDs from a yearly archive file",
    )
    parser_import = set_import_args(parser_import)
    parser_import.set_defaults(func=import_cli)

    parser_fetch = subparsers.add_parser(
        "fetch",
        description="Fetch latest log IDs into the database",
        help="Fetch latest log IDs into the database",
    )
    parser_fetch = set_fetch_args(parser_fetch)
    parser_fetch.set_defaults(func=fetch_cli)

    parser_yakuman = subparsers.add_parser(
        "yakuman",
        description="Fetch yakuman log IDs for a specific year and month",
        help="Fetch yakuman log IDs for a specific year and month",
    )
    parser_yakuman = set_yakuman_args(parser_yakuman)
    parser_yakuman.set_defaults(func=yakuman_cli)

    parser_download = subparsers.add_parser(
        "download",
        description="Download log contents into the database",
        help="Download log contents into the database",
    )
    parser_download = set_download_args(parser_download)
    parser_download.set_defaults(func=download_cli)

    parser_validate = subparsers.add_parser(
        "validate",
        description="Validate that downloaded logs can be parsed",
        help="Validate that downloaded logs can be parsed",
    )
    parser_validate = set_validate_args(parser_validate)
    parser_validate.set_defaults(func=validate_cli)

    parser_export = subparsers.add_parser(
        "export",
        description="Export downloaded log contents as XML files",
        help="Export downloaded log contents as XML files",
    )
    parser_export = set_export_args(parser_export)
    parser_export.set_defaults(func=export_cli)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        exit_code = args.func(args)
    except KeyboardInterrupt:
        print("Interrupted by user.", file=sys.stderr)
        return INTERRUPTED_EXIT_CODE
    except UserInputError as e:
        print(f"Error: {e}", file=sys.stderr)
        return USER_INPUT_ERROR_EXIT_CODE
    except ExternalResponseParseError as e:
        print(f"Response parse error: {e}", file=sys.stderr)
        return IO_ERROR_EXIT_CODE
    except EXTERNAL_IO_ERRORS as e:
        print(format_external_io_error(e), file=sys.stderr)
        return IO_ERROR_EXIT_CODE
    else:
        return SUCCESS_EXIT_CODE if exit_code is None else exit_code


if __name__ == "__main__":
    sys.exit(main())
