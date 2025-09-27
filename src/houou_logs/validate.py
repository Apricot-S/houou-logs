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


def split_log_to_game_rounds(log_content: str) -> list[list[str]]:
    root = ET.fromstring(log_content)  # noqa: S314
    if root.tag != "mjloggm":
        msg = "invalid root tag, expected <mjloggm>"
        raise ValueError(msg)

    rounds: list[list[str]] = []
    current_round: list[str] = []
    game_ended = False

    for elem in root:
        tagname = elem.tag

        if game_ended and tagname not in ("UN", "BYE"):
            # After game end, only connection-related tags (UN/BYE)
            # are allowed.
            msg = f"unexpected element <{tagname}> after game end"
            raise ValueError(msg)

        if tagname in ("SHUFFLE", "TAIKYOKU", "GO"):
            # Skip tags that are not part of round content
            continue

        if tagname == "INIT":
            # A new round starts at INIT.
            if current_round:
                # If there is an ongoing round, close it first.
                rounds.append(current_round)
                current_round = []

            # Remove legacy 'shuffle' attribute if present
            elem.attrib.pop("shuffle", None)

        if tagname in ("AGARI", "RYUUKYOKU") and "owari" in elem.attrib:
            # Game ends when 'owari' attribute is present.
            current_round.append(ET.tostring(elem, encoding="unicode"))
            rounds.append(current_round)
            current_round = []
            game_ended = True
            continue

        # Append the element to the current round
        current_round.append(ET.tostring(elem, encoding="unicode"))

    if not game_ended:
        # If no 'owari' was found, the log is incomplete
        msg = "log ended without 'owari' attribute"
        raise ValueError(msg)

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
