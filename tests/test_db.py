# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from houou_logs import db


def test_open_db() -> None:
    conn = db.open_db(":memory:")
    assert conn is not None
    conn.close()
