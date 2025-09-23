# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import sys
from argparse import ArgumentParser, Namespace
from datetime import UTC, datetime
from pathlib import Path

from houou_logs import download, export, fetch, import_, yakuman
from houou_logs.exceptions import UserInputError


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


def fetch_cli(args: Namespace) -> None:
    num_logs = fetch.fetch(args.db_path, archive=args.archive)
    if num_logs == -1:
        msg = "Skipping fetch: last fetch was within 20 minutes."
    else:
        msg = f"Number of log entries inserted into the DB: {num_logs}"
    print(msg, file=sys.stderr)


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

    if args.year == now.year and args.month == now.month:
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
        help="Max number of logs to download. If omitted, all available logs are downloaded.",  # noqa: E501
    )
    return parser


def download_cli(args: Namespace) -> None:
    num_logs = download.download(
        args.db_path,
        args.players,
        args.length,
        args.limit,
    )
    print(f"Number of logs downloaded: {num_logs}", file=sys.stderr)


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
        help="Number of logs to skip before starting export. Default is 0.",
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


def main() -> None:
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_import = subparsers.add_parser("import")
    parser_import = set_import_args(parser_import)
    parser_import.set_defaults(func=import_cli)

    parser_fetch = subparsers.add_parser("fetch")
    parser_fetch = set_fetch_args(parser_fetch)
    parser_fetch.set_defaults(func=fetch_cli)

    parser_yakuman = subparsers.add_parser("yakuman")
    parser_yakuman = set_yakuman_args(parser_yakuman)
    parser_yakuman.set_defaults(func=yakuman_cli)

    parser_download = subparsers.add_parser("download")
    parser_download = set_download_args(parser_download)
    parser_download.set_defaults(func=download_cli)

    parser_export = subparsers.add_parser("export")
    parser_export = set_export_args(parser_export)
    parser_export.set_defaults(func=export_cli)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return

    try:
        args.func(args)
    except UserInputError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
