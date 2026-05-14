# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import sqlite3
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

from tqdm import tqdm

from houou_logs import db
from houou_logs.download import validate_db_path

VALIDATE_BATCH_SIZE = 1000


def iter_processed_log_id_batches(
    cursor: sqlite3.Cursor,
    batch_size: int,
) -> Iterator[list[str]]:
    last_id = None
    while True:
        log_ids = db.list_all_processed_log_ids_after(
            cursor,
            last_id,
            batch_size,
        )
        if not log_ids:
            break

        last_id = log_ids[-1]
        yield log_ids


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


def is_valid_log_content(
    log_id: str,
    compressed_content: bytes | None,
) -> bool:
    content = None
    try:
        if compressed_content is not None:
            decompressed = gzip.decompress(compressed_content)
            content = decompressed.decode("utf-8")
    except Exception as e:  # noqa: BLE001
        tqdm.write(f"{log_id}: failed to decompress: {e}")
        return False

    if not content:
        return False

    try:
        parsed_rounds = split_log_to_game_rounds(content)
    except Exception as e:  # noqa: BLE001
        tqdm.write(f"{log_id}: failed to parse: {e}")
        return False

    return bool(parsed_rounds)


def validate(db_path: Path) -> tuple[bool, int, int]:
    validate_db_path(db_path)

    with closing(db.open_db(db_path)) as conn, conn:
        cursor = conn.cursor()

        num_ids = db.count_all_ids(cursor)
        num_logs = db.count_all_log_contents(cursor)
        were_errors = False
        num_valid_logs = 0

        with tqdm(total=num_logs) as progress:
            for log_ids in iter_processed_log_id_batches(
                cursor,
                VALIDATE_BATCH_SIZE,
            ):
                for log_id in log_ids:
                    compressed_content = db.get_log_content(cursor, log_id)
                    if is_valid_log_content(log_id, compressed_content):
                        num_valid_logs += 1
                        progress.update(1)
                        continue

                    were_errors = True
                    msg = "Invalid log content detected. Reset to unprocessed."
                    tqdm.write(msg)
                    db.reset_log_content(cursor, log_id)

                    progress.update(1)

    return (were_errors, num_valid_logs, num_ids)
