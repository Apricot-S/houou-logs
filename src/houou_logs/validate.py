# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import xml.etree.ElementTree as ET
from contextlib import closing
from pathlib import Path
from pprint import pprint

from tqdm import tqdm

from houou_logs import db
from houou_logs.download import validate_db_path

SKIP_TAGS = {"SHUFFLE", "TAIKYOKU", "GO"}


def split_log_to_game_rounds(log_content: str) -> list[list[str]]:
    root = ET.fromstring(log_content)  # noqa: S314
    rounds: list[list[str]] = []
    current_round: list[str] = []

    if root.tag != "mjloggm":
        return []

    for elem in root:
        match elem.tag:
            case tagname if tagname in SKIP_TAGS:
                # スキップ対象
                continue
            case "INIT":
                # INIT タグが来たら新しいラウンド開始
                if current_round:
                    # 前ラウンドを閉じる
                    rounds.append(current_round)
                    current_round = []

                if "shuffle" in elem.attrib:
                    # shuffle属性を削除 旧ログ対応
                    del elem.attrib["shuffle"]
            case "owari":
                # owari タグでゲーム終了
                current_round.append(ET.tostring(elem, encoding="unicode"))
                rounds.append(current_round)
                current_round = []
                continue

        # タグを文字列化して追加
        current_round.append(ET.tostring(elem, encoding="unicode"))

    # pprint([rounds])  # 開発中確認用
    return rounds


def validate(db_path: Path) -> tuple[bool, int, int]:
    validate_db_path(db_path)

    with closing(db.open_db(db_path)) as conn, conn:
        cursor = conn.cursor()

        num_ids = db.count_all_ids(cursor)
        num_logs = db.count_all_log_contents(cursor)
        logs_iter = db.iter_all_log_contents(cursor)

        were_errors = False
        num_valid_logs = 0
        for log_id, compressed_content in tqdm(logs_iter, total=num_logs):
            was_error = False

            content = None
            try:
                content = gzip.decompress(compressed_content).decode("utf-8")
            except Exception as e:  # noqa: BLE001
                tqdm.write(f"{log_id}: failed to decompress: {e}")
                was_error = True

            if not content:
                was_error = True

            parsed_rounds = None
            try:
                if content:
                    parsed_rounds = split_log_to_game_rounds(content)
            except Exception as e:  # noqa: BLE001
                tqdm.write(f"{log_id}: failed to parse: {e}")
                was_error = True

            if parsed_rounds:
                num_valid_logs += 1
            else:
                was_error = True

            if was_error:
                were_errors = True
                tqdm.write(
                    "Invalid log content detected. Reset to unprocessed.",
                )
                db.reset_log_content(cursor, log_id)

    return (were_errors, num_valid_logs, num_ids)
