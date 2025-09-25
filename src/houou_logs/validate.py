# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from contextlib import closing
from pathlib import Path

from tqdm import tqdm

from houou_logs import db


def validate(db_path: Path) -> tuple[bool, int, int]:
    with closing(db.open_db(db_path)) as conn, conn:
        cursor = conn.cursor()

        num_ids = db.count_all_ids(cursor)
        logs_iter = db.iter_all_log_contents(cursor)

        were_errors = False
        num_valid_logs = 0
        for log_id, compressed_content in tqdm(logs_iter):
            was_error = False

            if was_error:
                were_errors = True
                tqdm.write(
                    "Invalid log content detected. Reset to unprocessed.",
                )

    return (were_errors, num_valid_logs, num_ids)
