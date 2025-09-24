# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
from contextlib import closing
from pathlib import Path

from tqdm import tqdm

from houou_logs import db
from houou_logs.download import (
    validate_db_path,
    validate_length,
    validate_limit,
    validate_players,
)
from houou_logs.exceptions import UserInputError


def validate_offset(offset: int) -> None:
    if offset < 0:
        msg = f"invalid offset of export: {offset}"
        raise UserInputError(msg)


def export(
    db_path: Path,
    output_dir: Path,
    players: int | None,
    length: str | None,
    limit: int | None,
    offset: int,
) -> int:
    validate_db_path(db_path)
    if players is not None:
        validate_players(players)
    if length is not None:
        validate_length(length)
    if limit is not None:
        validate_limit(limit)
    validate_offset(offset)

    output_dir.mkdir(parents=True, exist_ok=True)

    with closing(db.open_db(db_path)) as conn, conn:
        cursor = conn.cursor()

        num_logs = db.count_log_contents(
            cursor,
            players,
            length,
            limit,
            offset,
        )
        logs_iter = db.iter_log_contents(
            cursor,
            players,
            length,
            limit,
            offset,
        )

        for log_id, compressed_content in tqdm(logs_iter, total=num_logs):
            try:
                content = gzip.decompress(compressed_content).decode("utf-8")
            except Exception as e:  # noqa: BLE001
                tqdm.write(f"{log_id}: failed to decompress: {e}")
                num_logs -= 1
                continue

            filename = (output_dir / log_id).with_suffix(".xml")
            with filename.open("w") as f:
                f.write(content)

    return num_logs
