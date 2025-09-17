# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from . import extract


def set_extract_args(parser: ArgumentParser) -> ArgumentParser:
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


def extract_cli(args: Namespace) -> None:
    num_logs = extract.extract(args.db_path, args.archive_path)
    print(
        f"Number of log entries targeted for DB insertion: {num_logs}",
        file=sys.stderr,
    )


def main() -> None:
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_extract = subparsers.add_parser("extract")
    parser_extract = set_extract_args(parser_extract)
    parser_extract.set_defaults(func=extract_cli)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
