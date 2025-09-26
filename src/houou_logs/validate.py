# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import xml.etree.ElementTree as ET
from contextlib import closing
from pathlib import Path

from tqdm import tqdm

from houou_logs import db
from houou_logs.download import validate_db_path


def is_init_elem(elem: ET.Element) -> bool:
    return elem.tag.upper() == "INIT"


def split_log_to_game_rounds(log_content: str) -> list[list[str]]:
    root = ET.fromstring(log_content)  # noqa: S314
    rounds: list[list[str]] = []
    current_round_tags: list[str] = []

    skip_tags = {"SHUFFLE", "TAIKYOKU", "mjloggm", "GO"}

    for elem in root:
        tagname = elem.tag.upper()

        # スキップ対象
        if tagname in skip_tags:
            continue

        # INIT タグが来たら新しいラウンド開始
        if is_init_elem(elem) and current_round_tags:
            rounds.append(current_round_tags)
            current_round_tags = []

        # owari タグでゲーム終了
        if tagname.lower() == "owari":
            current_round_tags.append(ET.tostring(elem, encoding="unicode"))
            rounds.append(current_round_tags)
            current_round_tags = []
            continue

        # shuffle属性を削除 旧ログ対応
        if is_init_elem(elem) and "shuffle" in elem.attrib:
            del elem.attrib["shuffle"]

        # タグを文字列化して追加
        current_round_tags.append(ET.tostring(elem, encoding="unicode"))

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
