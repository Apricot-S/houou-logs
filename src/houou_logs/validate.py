# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from contextlib import closing
from pathlib import Path

from houou_logs import db


def validate(db_path: Path) -> tuple[bool, int, int]:
    with closing(db.open_db(db_path)) as conn, conn:
        cursor = conn.cursor()

        total_ids = db.count_all_ids(cursor)

    return (False, 0, 0)
