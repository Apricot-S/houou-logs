# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import argparse
import tempfile
from pathlib import Path

from houou_logs import db


def set_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        "db_path",
        type=Path,
        help="Path to the SQLite database file.",
    )
    parser.add_argument(
        "archive_path",
        type=Path,
        help="Path to an archive file (.zip).",
    )
    return parser


def extract_cli(args: argparse.Namespace) -> None:
    extract(args.db_path, args.archive_path)


# 1. 指定されたパスのsqliteのdbを開く。dbがないなら作成する
# 2. dbのテーブルを作成する。既存のテーブルがあるならスキップする
# 3. 指定されたパスのアーカイブファイルの存在チェックをする
# 4. アーカイブファイルを一時ディレクトリでzip展開する
# 5. ディレクトリ内のファイルに対して以下を実行する
#    a. ファイル名がsccで始まるhtml.gzを選択する
#    b. gzを展開して同じディレクトリにhtmlを作成する
#    c. html から対局idを抽出する
#    d. 抽出したidをdbに追加する
# 6. 5をすべてのファイルに対して実行する
def extract(db_path: str | Path, archive_path: Path) -> None:
    conn = db.open_db(db_path)

    try:
        db.setup_table(conn)

        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdir = Path(tmpdirname)
            extract_logs(archive_path, tmpdir)
    finally:
        conn.close()


def extract_logs(archive_path: Path, output_dir: Path) -> None:
    pass
