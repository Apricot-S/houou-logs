# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import argparse

from . import extract


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_extract = subparsers.add_parser("extract")
    parser_extract = extract.set_args(parser_extract)
    parser_extract.set_defaults(func=extract.extract_cli)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
