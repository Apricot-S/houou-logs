# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import niquests
from niquests import Session
from tqdm import tqdm

from houou_logs import db
from houou_logs.exceptions import UserInputError
from houou_logs.session import TIMEOUT, create_session

DOWNLOAD_BATCH_SIZE = 1000


def validate_db_path(db_path: Path) -> None:
    if not db_path.is_file():
        msg = f"database file is not found: {db_path}"
        raise UserInputError(msg)


def validate_players(players: int) -> None:
    if players not in (4, 3):
        msg = f"invalid number of players: {players}"
        raise UserInputError(msg)


def validate_length(length: str) -> None:
    if length not in ("t", "h"):
        msg = f"invalid length of game: {length}"
        raise UserInputError(msg)


def validate_limit(limit: int) -> None:
    if limit <= 0:
        msg = f"invalid limit of download: {limit}"
        raise UserInputError(msg)


def build_url(log_id: str) -> str:
    return f"https://tenhou.net/0/log/?{log_id}"


def fetch_log_content(session: Session, url: str) -> bytes:
    resp = session.get(url, timeout=TIMEOUT)
    if resp.status_code != niquests.codes["ok"]:
        msg = f"failed to fetch: HTTP {resp.status_code}"
        raise RuntimeError(msg)

    text = resp.text
    if text is None:
        msg = "response text is None (failed to decode or empty response)"
        raise RuntimeError(msg)

    if "mjlog" not in text:
        msg = "no log content in response"
        raise RuntimeError(msg)

    content = resp.content
    if content is None:
        msg = "content could not be retrieved"
        raise RuntimeError(msg)

    return content


def fetch_log_content_for_download(
    session: Session,
    log_id: str,
) -> tuple[bool, bytes]:
    url = build_url(log_id)

    try:
        content = fetch_log_content(session, url)
    except Exception as e:  # noqa: BLE001
        tqdm.write(f"{log_id}: {e}")
        return (True, b"")

    return (False, content)


def compress_log_content(
    log_id: str,
    content: bytes,
) -> tuple[bool, bytes | None]:
    try:
        return (False, gzip.compress(content))
    except Exception as e:  # noqa: BLE001
        tqdm.write(f"{log_id}: failed to compress: {e}")
        return (True, None)


def iter_undownloaded_log_id_batches(
    cursor: sqlite3.Cursor,
    players: int | None,
    length: str | None,
    limit: int | None,
    batch_size: int,
) -> Iterator[list[str]]:
    last_id = None
    num_logs = 0
    while limit is None or num_logs < limit:
        current_batch_size = batch_size
        if limit is not None:
            current_batch_size = min(current_batch_size, limit - num_logs)

        log_ids = db.list_undownloaded_log_ids_after(
            cursor,
            players,
            length,
            last_id,
            current_batch_size,
        )
        if not log_ids:
            break

        last_id = log_ids[-1]
        num_logs += len(log_ids)
        yield log_ids


def download(
    db_path: Path,
    players: int | None,
    length: str | None,
    limit: int | None,
) -> int:
    validate_db_path(db_path)
    if players is not None:
        validate_players(players)
    if length is not None:
        validate_length(length)
    if limit is not None:
        validate_limit(limit)

    num_logs = 0
    with closing(db.open_db(db_path)) as conn, conn:
        cursor = conn.cursor()

        with create_session() as session:
            total = db.count_undownloaded_log_ids(
                cursor,
                players,
                length,
                limit,
            )

            with tqdm(total=total) as progress:
                for ids in iter_undownloaded_log_id_batches(
                    cursor,
                    players,
                    length,
                    limit,
                    DOWNLOAD_BATCH_SIZE,
                ):
                    for log_id in ids:
                        was_error, content = fetch_log_content_for_download(
                            session,
                            log_id,
                        )

                        compressed_content = None
                        if not was_error:
                            was_error, compressed_content = (
                                compress_log_content(log_id, content)
                            )

                        db.update_log_entries(
                            cursor,
                            log_id,
                            was_error,
                            compressed_content,
                        )
                        num_logs += 1
                        progress.update(1)

                        conn.commit()

    return num_logs
