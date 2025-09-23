# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from contextlib import closing
from pathlib import Path

from tqdm import tqdm

from houou_logs import db
from houou_logs.exceptions import UserInputError
from houou_logs.session import TIMEOUT, create_session


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


def download(
    db_path: Path,
    players: int | None,
    length: str | None,
    limit: int | None,
) -> int:
    if players is not None:
        validate_players(players)
    if length is not None:
        validate_length(length)
    if limit is not None:
        validate_limit(limit)

    num_logs = 0
    with closing(db.open_db(db_path)) as conn, conn:
        db.setup_table(conn)
        cursor = conn.cursor()

        with create_session() as session:
            ids = db.get_undownloaded_log_ids(cursor, players, length, limit)

            for log_id in tqdm(ids):
                content = None
                was_error = False

                url = build_url(log_id)

                try:
                    resp = session.get(url, timeout=TIMEOUT)
                    content = resp.content
                except Exception as e:  # noqa: BLE001
                    print(f"{log_id}: {e}")
                    was_error = True

                if content is None:
                    print(f"{log_id}: Content could not be retrieved")
                    was_error = True

                num_logs += 1

                conn.commit()

    return num_logs
