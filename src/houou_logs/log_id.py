# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import re
from collections.abc import Iterable, Iterator
from typing import IO

from tqdm import tqdm

from houou_logs.db import LogEntry
from houou_logs.exceptions import ExternalResponseParseError

HOUOU_ARCHIVE_PREFIX = "scc"

LINE_PATTERN = re.compile(r'^(\d{2}:\d{2}).*?log=([^">]+)', re.MULTILINE)
LOG_ID_PATTERN = re.compile(
    r"^\d{10}gm-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{8}$",
)

TYPE_IS_HANCHAN = 0x008
TYPE_IS_3_PLAYERS = 0x010


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
    if not LOG_ID_PATTERN.fullmatch(log_id):
        msg = f"invalid log ID: {log_id}"
        raise ExternalResponseParseError(msg)

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


def iter_log_entries(filename: str, fileobj: IO[bytes]) -> Iterator[LogEntry]:
    """Read lines without closing the caller's file object."""
    if filename.endswith(".html.gz"):
        # Logs from 2013 onwards are compressed
        with gzip.open(fileobj, mode="rb") as gz:
            yield from _iter_log_entries(filename, gz)
    else:
        yield from _iter_log_entries(filename, fileobj)


def _iter_log_entries(
    filename: str,
    lines: Iterable[bytes],
) -> Iterator[LogEntry]:
    for line in lines:
        for match in LINE_PATTERN.finditer(line.decode("utf-8")):
            time, log_id = match.groups()
            try:
                entry = parse_id(time, log_id)
            except ExternalResponseParseError as e:
                tqdm.write(f"{filename}: {e}")
            else:
                yield entry
