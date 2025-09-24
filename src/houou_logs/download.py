# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
from contextlib import closing
from pathlib import Path

from requests import Session
from tqdm import tqdm

from houou_logs import db
from houou_logs.exceptions import UserInputError
from houou_logs.session import TIMEOUT, create_session


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
    if "mjlog" not in resp.text:
        msg = "no log content in response"
        raise RuntimeError(msg)

    content = resp.content
    if content is None:
        msg = "content could not be retrieved"
        raise RuntimeError(msg)

    return content


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
            ids = db.get_undownloaded_log_ids(cursor, players, length, limit)

            for log_id in tqdm(ids):
                content = b""
                was_error = False

                url = build_url(log_id)

                try:
                    content = fetch_log_content(session, url)
                except Exception as e:  # noqa: BLE001
                    tqdm.write(f"{log_id}: {e}")
                    was_error = True

                compressed_content = None
                if not was_error:
                    try:
                        compressed_content = gzip.compress(content)
                    except Exception as e:  # noqa: BLE001
                        tqdm.write(f"{log_id}: failed to compress: {e}")
                        was_error = True

                db.update_log_entries(
                    cursor,
                    log_id,
                    was_error,
                    compressed_content,
                )
                num_logs += 1

                conn.commit()

    return num_logs
