# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import argparse
import zipfile
from pathlib import Path

from houou_logs import db
from houou_logs.log_id import extract_log_entries

HOUOU_ARCHIVE_PREFIX = "scc"


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


# 1. 指定されたパスのアーカイブファイルの存在チェックをする -> 実装
# 2. 指定されたパスのsqliteのdbを開く。dbがないなら作成する -> 実装
# 3. dbのテーブルを作成する。既存のテーブルがあるならスキップする -> 実装
# 3. アーカイブファイルをzip展開する -> 実装
# 4. ディレクトリ内のファイルに対して以下を実行する -> 仮実装
#    a. ファイル名がsccで始まるファイルを選択する -> 実装
#    b. html.gzなら展開する
#    c. html から対局idを抽出する
#    d. 抽出したidをdbに追加する -> 実装
# 5. 4をすべてのファイルに対して実行する -> 実装
def extract(db_path: str | Path, archive_path: Path) -> None:
    if not archive_path.is_file():
        msg = f"archive file not found: {archive_path}"
        raise FileNotFoundError(msg)

    if not zipfile.is_zipfile(archive_path):
        msg = f"archive file must be zip file: {archive_path}"
        raise ValueError(msg)

    conn = db.open_db(db_path)
    with conn:
        try:
            db.setup_table(conn)
            cursor = conn.cursor()

            with zipfile.ZipFile(archive_path) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    if not info.filename.startswith(HOUOU_ARCHIVE_PREFIX):
                        continue

                    with zf.open(info) as f:
                        entries = extract_log_entries(info.filename, f)
                        db.insert_entries(cursor, entries)
        finally:
            conn.close()
