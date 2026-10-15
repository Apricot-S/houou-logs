# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import re
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import IO

from tqdm import tqdm

from houou_logs.db import LogEntry
from houou_logs.exceptions import ExternalResponseParseError

HOUOU_ARCHIVE_PREFIX = "scc"

LINE_PATTERN = re.compile(r'^(\d{2}:\d{2}).*?log=([^">]+)', re.MULTILINE)
LOG_ID_PATTERN = re.compile(
    r"^\d{10}gm-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{8}$",
)
LOG_DATE_PATTERN = re.compile(r"\d{8}(?:\d{2})?")
TIME_PATTERN = re.compile(r"\d{2}:\d{2}")

TYPE_IS_HANCHAN = 0x008
TYPE_IS_3_PLAYERS = 0x010


def parse_date(time: str, log_date: str) -> str:
    msg = f"invalid log date: {log_date} {time}"
    if not LOG_DATE_PATTERN.fullmatch(log_date) or not TIME_PATTERN.fullmatch(
        time,
    ):
        raise ExternalResponseParseError(msg)

    year = log_date[0:4]
    month = log_date[4:6]
    day = log_date[6:8]
    try:
        datetime(
            int(year),
            int(month),
            int(day),
            int(time[0:2]),
            int(time[3:5]),
            tzinfo=UTC,
        )
    except ValueError as e:
        raise ExternalResponseParseError(msg) from e

    if len(log_date) == 10 and not 0 <= int(log_date[8:10]) <= 23:  # noqa: PLR2004
        raise ExternalResponseParseError(msg)

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

    date = parse_date(time, log_id[0:10])
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


def iter_log_entries(
    filename: str,
    fileobj: IO[bytes],
    *,
    validate_body: bool = False,
) -> Iterator[LogEntry]:
    """Read lines, optionally validating rows and IDs.

    Empty bodies and blank lines represent valid empty lists.
    Keep the caller's file open. Archive imports retain lenient parsing.
    """
    if filename.endswith(".html.gz"):
        # Logs from 2013 onwards are compressed
        with gzip.open(fileobj, mode="rb") as gz:
            yield from _iter_log_entries(
                filename,
                gz,
                validate_body=validate_body,
            )
    else:
        yield from _iter_log_entries(
            filename,
            fileobj,
            validate_body=validate_body,
        )


def _iter_log_entries(
    filename: str,
    lines: Iterable[bytes],
    *,
    validate_body: bool = False,
) -> Iterator[LogEntry]:
    for line in lines:
        text = line.decode("utf-8")
        matched = False
        for match in LINE_PATTERN.finditer(text):
            matched = True
            time, log_id = match.groups()
            try:
                entry = parse_id(time, log_id)
            except ExternalResponseParseError as e:
                if validate_body:
                    raise
                tqdm.write(f"{filename}: {e}")
            else:
                yield entry

        if validate_body and text.strip() and not matched:
            msg = f"{filename}: failed to parse log list row"
            raise ExternalResponseParseError(msg)
