# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import xml.etree.ElementTree as ET
import zlib
from contextlib import closing
from io import BytesIO, StringIO, TextIOWrapper
from pathlib import Path
from typing import TextIO

from tqdm import tqdm

from houou_logs import db
from houou_logs.exceptions import InvalidLogContentError
from houou_logs.input_validation import validate_db_path

VALIDATE_BATCH_SIZE = 1000


class _LogStructureTarget:
    def __init__(self) -> None:
        self.depth = 0
        self.game_ended = False
        self.error: str | None = None

    def start(self, tag: str, attrs: dict[str, str]) -> None:
        if self.depth == 0 and tag != "mjloggm":
            self.error = "invalid root tag, expected <mjloggm>"
        elif self.depth == 1:
            if (
                self.game_ended
                and tag not in ("UN", "BYE")
                and self.error is None
            ):
                self.error = f"unexpected element <{tag}> after game end"
            if tag in ("AGARI", "RYUUKYOKU") and "owari" in attrs:
                self.game_ended = True
        self.depth += 1

    def end(self, _tag: str) -> None:
        self.depth -= 1

    def data(self, data: str) -> None:
        pass

    def close(self) -> bool:
        if self.error is not None:
            raise InvalidLogContentError(self.error)
        if not self.game_ended:
            msg = "log ended without 'owari' attribute"
            raise InvalidLogContentError(msg)
        return True


def validate_log_structure(log_content: str | TextIO) -> bool:
    # Avoid retaining elements, text, or the complete XML tree.
    # Delay structural errors until close so syntax is checked to EOF.
    parser = ET.XMLParser(target=_LogStructureTarget())  # noqa: S314
    stream = (
        StringIO(log_content) if isinstance(log_content, str) else log_content
    )
    while chunk := stream.read(64 * 1024):
        parser.feed(chunk)
    parser.close()
    return True


def is_valid_log_content(
    log_id: str,
    compressed_content: bytes | None,
) -> bool:
    if not compressed_content:
        return False
    try:
        with (
            gzip.GzipFile(fileobj=BytesIO(compressed_content)) as decompressed,
            TextIOWrapper(decompressed, encoding="utf-8") as content,
        ):
            return validate_log_structure(content)
    except (gzip.BadGzipFile, EOFError, zlib.error, UnicodeDecodeError) as e:
        tqdm.write(f"{log_id}: failed to decompress: {e}")
        return False
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
            last_id = None
            while True:
                invalid_ids = []
                batch_count = 0
                for (
                    log_id,
                    compressed_content,
                ) in db.iter_processed_log_contents_after(
                    cursor,
                    last_id,
                    VALIDATE_BATCH_SIZE,
                ):
                    last_id = log_id
                    batch_count += 1
                    if is_valid_log_content(log_id, compressed_content):
                        num_valid_logs += 1
                        progress.update(1)
                        continue

                    were_errors = True
                    msg = "Invalid log content detected. Reset to unprocessed."
                    tqdm.write(msg)
                    invalid_ids.append(log_id)

                    progress.update(1)

                if not batch_count:
                    break

                # Finish reads before starting the batch's writes.
                # An interrupted batch leaves its contents unchanged.
                conn.commit()
                db.reset_log_contents(cursor, invalid_ids)
                conn.commit()

    return (were_errors, num_valid_logs, num_ids)
