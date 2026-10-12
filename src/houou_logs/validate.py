# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import sqlite3
import xml.etree.ElementTree as ET
import zlib
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

from tqdm import tqdm

from houou_logs import db
from houou_logs.download import validate_db_path
from houou_logs.exceptions import InvalidLogContentError

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


def validate_log_structure(log_content: str) -> bool:
    # Parse the entire document before checking the game-end marker.
    root = ET.fromstring(log_content)  # noqa: S314
    if root.tag != "mjloggm":
        msg = "invalid root tag, expected <mjloggm>"
        raise InvalidLogContentError(msg)

    game_ended = False
    for elem in root:
        if game_ended and elem.tag not in ("UN", "BYE"):
            msg = f"unexpected element <{elem.tag}> after game end"
            raise InvalidLogContentError(msg)
        if elem.tag in ("AGARI", "RYUUKYOKU") and "owari" in elem.attrib:
            game_ended = True

    if not game_ended:
        msg = "log ended without 'owari' attribute"
        raise InvalidLogContentError(msg)
    return True


def is_valid_log_content(
    log_id: str,
    compressed_content: bytes | None,
) -> bool:
    content = None
    try:
        if compressed_content is not None:
            content = gzip.decompress(compressed_content).decode("utf-8")
    except (gzip.BadGzipFile, EOFError, zlib.error, UnicodeDecodeError) as e:
        tqdm.write(f"{log_id}: failed to decompress: {e}")
        return False

    if not content:
        return False

    try:
        return validate_log_structure(content)
    except (ET.ParseError, InvalidLogContentError) as e:
        tqdm.write(f"{log_id}: failed to parse: {e}")
        return False


def validate(db_path: Path) -> tuple[bool, int, int]:
    validate_db_path(db_path)

    with closing(db.open_db(db_path)) as conn, conn:
        db.create_logs_indexes(conn)
        conn.commit()
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
