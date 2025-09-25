# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import re
from typing import IO

from houou_logs.db import LogEntry

HOUOU_ARCHIVE_PREFIX = "scc"

LINE_PATTERN = re.compile(r'^(\d{2}:\d{2}).*?log=([^">]+)', re.MULTILINE)

TYPE_IS_HANCHAN = 0x008
TYPE_IS_3_PLAYERS = 0x010


def extract_ids(text: str) -> list[tuple[str, str]]:
    matches = LINE_PATTERN.findall(text)
    if not matches:
        return []
    return matches


def parse_date(time: str, log_date: str) -> str:
    year = log_date[0:4]
    month = log_date[4:6]
    day = log_date[6:8]
    return f"{year}-{month}-{day}T{time}"


def parse_type(log_type: str) -> tuple[int, bool]:
    t = int(log_type, 16)
    is_3p = (t & TYPE_IS_3_PLAYERS) == TYPE_IS_3_PLAYERS
    is_hanchan = (t & TYPE_IS_HANCHAN) == TYPE_IS_HANCHAN

    num_players = 3 if is_3p else 4
    is_tonpu = not is_hanchan
    return (num_players, is_tonpu)


def parse_id(time: str, log_id: str) -> LogEntry:
    date = parse_date(time, log_id[0:8])
    num_players, is_tonpu = parse_type(log_id[13:17])

    return LogEntry(
        log_id,
        date,
        num_players,
        is_tonpu,
        is_processed=False,
        was_error=False,
        log=None,
    )


def extract_log_entries(filename: str, fileobj: IO[bytes]) -> list[LogEntry]:
    if filename.endswith(".html.gz"):
        # Logs from 2013 onwards are compressed
        with gzip.open(fileobj, mode="rt", encoding="utf-8") as gz:
            text = gz.read()
    else:
        text = fileobj.read().decode("utf-8")

    ids = extract_ids(text)
    return [parse_id(i[0], i[1]) for i in ids]
