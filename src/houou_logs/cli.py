# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from houou_logs import fetch, import_


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


def main() -> None:
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_import = subparsers.add_parser("import")
    parser_import = set_import_args(parser_import)
    parser_import.set_defaults(func=import_cli)

    parser_fetch = subparsers.add_parser("fetch")
    parser_fetch = set_fetch_args(parser_fetch)
    parser_fetch.set_defaults(func=fetch_cli)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
