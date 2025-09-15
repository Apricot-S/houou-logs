# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from typing import IO

from houou_logs import db


def extract_log_entries(logfile: IO[bytes]) -> list[db.LogEntry]:
    return []  # TODO: implement
