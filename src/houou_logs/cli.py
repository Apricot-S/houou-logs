# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import sys
from argparse import ArgumentParser, Namespace
from datetime import UTC, datetime
from pathlib import Path

from houou_logs import fetch, import_, yakuman


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
        f"Number of log entries targeted for DB insertion: {num_logs}",
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
        msg = f"Number of log entries targeted for DB insertion: {num_logs}"
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
        choices=range(1, 13),
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
        f"Number of log entries targeted for DB insertion: {num_logs}",
        file=sys.stderr,
    )


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

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
