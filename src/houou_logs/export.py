# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import io
import shutil
import zlib
from contextlib import closing
from pathlib import Path
from tempfile import NamedTemporaryFile

from tqdm import tqdm

from houou_logs import db
from houou_logs.exceptions import UserInputError
from houou_logs.input_validation import (
    validate_db_path,
    validate_length,
    validate_limit,
    validate_players,
)


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
        db.create_logs_indexes(conn)
        conn.commit()
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

        with closing(logs_iter):
            for log_id, compressed_content in tqdm(logs_iter, total=num_logs):
                filename = (output_dir / log_id).with_suffix(".xml")
                temp_path = None
                try:
                    with (
                        gzip.GzipFile(
                            fileobj=io.BytesIO(compressed_content),
                        ) as gz,
                        NamedTemporaryFile(
                            mode="wb",
                            dir=filename.parent,
                            prefix=f".{filename.name}.",
                            suffix=".tmp",
                            delete=False,
                        ) as f,
                    ):
                        temp_path = Path(f.name)
                        shutil.copyfileobj(gz, f)
                    temp_path.replace(filename)
                except (OSError, EOFError, zlib.error) as e:
                    tqdm.write(f"{log_id}: failed to decompress: {e}")
                    num_logs -= 1
                    continue
                finally:
                    if temp_path is not None:
                        temp_path.unlink(missing_ok=True)

    return num_logs
