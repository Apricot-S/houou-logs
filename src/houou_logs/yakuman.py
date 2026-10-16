# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import ast
import re
from collections.abc import Iterable, Iterator
from contextlib import closing
from datetime import MAXYEAR, MINYEAR, UTC, datetime
from pathlib import Path

from niquests import Session
from tqdm import tqdm

from houou_logs import db
from houou_logs.exceptions import ExternalResponseParseError, UserInputError
from houou_logs.log_id import parse_date, parse_type
from houou_logs.session import TIMEOUT, create_session

YAKUMAN_LOGS_AVAILABLE_FROM = datetime(2006, 10, 1, tzinfo=UTC)

YKM_ARRAY_START_PATTERN = re.compile(r"ykm=(?=\[)")
YAKUMAN_LOG_DATE_PATTERN = re.compile(r"^\d{2}/\d{2} \d{2}:\d{2}$")
YAKUMAN_LOG_ID_PATTERN = re.compile(
    r"^\d{8}(?:\d{2})?gm-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{8}$",
)


def validate_yakuman_log_date(year: int, month: int, now: datetime) -> None:
    if not (1 <= month <= 12):  # noqa: PLR2004
        msg = "month must be between 1 and 12"
        raise UserInputError(msg)

    if not (MINYEAR <= year <= MAXYEAR):
        msg = f"year must be between {MINYEAR} and {MAXYEAR}"
        raise UserInputError(msg)

    target_date = datetime(year, month, 1, tzinfo=UTC)

    if target_date < YAKUMAN_LOGS_AVAILABLE_FROM:
        msg = f"yakuman logs are available starting from {YAKUMAN_LOGS_AVAILABLE_FROM.year}/{YAKUMAN_LOGS_AVAILABLE_FROM.month}"  # noqa: E501
        raise UserInputError(msg)

    if target_date > now:
        msg = "future dates are not allowed"
        raise UserInputError(msg)


def build_url(year: int, month: int) -> str:
    return f"https://tenhou.net/sc/{year}/{month:02}/ykm.js"


def fetch_yakuman_log_ids_text(session: Session, url: str) -> str:
    res = session.get(url, timeout=TIMEOUT)
    res.raise_for_status()

    content = res.content
    if content is None:
        msg = "response content is None"
        raise ExternalResponseParseError(msg)

    return content.decode("utf-8")


def iter_ids_from_new_format(ykm_array: list) -> Iterator[tuple[str, str]]:
    # New format: format from February 2008
    if len(ykm_array) % 5 != 0:
        msg = "invalid new ykm array length"
        raise ExternalResponseParseError(msg)

    for i in range(0, len(ykm_array), 5):
        date = ykm_array[i]
        log_id = ykm_array[i + 4]
        if not isinstance(date, str) or not isinstance(log_id, str):
            msg = "invalid new ykm array entry"
            raise ExternalResponseParseError(msg)
        yield date, log_id.split("&", 1)[0]


def iter_ids_from_old_format(ykm_array: list) -> Iterator[tuple[str, str]]:
    # Old format: format until January 2008
    for entry in ykm_array:
        if (
            not isinstance(entry, list)
            or len(entry) < 5  # noqa: PLR2004
            or not isinstance(entry[0], str)
            or not isinstance(entry[4], str)
        ):
            msg = "invalid old ykm array entry"
            raise ExternalResponseParseError(msg)
        yield entry[0], entry[4]


def extract_ykm_array(text: str) -> str:
    match = YKM_ARRAY_START_PATTERN.search(text)
    if not match:
        msg = "ykm array not found in input text"
        raise ExternalResponseParseError(msg)

    depth = 0
    quote = None
    escaped = False
    for index in range(match.end(), len(text)):
        char = text[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                if text[index + 1 : index + 2] == ";":
                    return text[match.end() : index + 1]
                break

    msg = "failed to parse ykm array"
    raise ExternalResponseParseError(msg)


def iter_ids(text: str) -> Iterator[tuple[str, str]]:
    ykm_text = extract_ykm_array(text)
    try:
        ykm_array = ast.literal_eval(ykm_text)
    except (SyntaxError, ValueError) as e:
        msg = "failed to parse ykm array"
        raise ExternalResponseParseError(msg) from e

    if not isinstance(ykm_array, list):
        msg = "ykm array must be a list"
        raise ExternalResponseParseError(msg)

    if len(ykm_array) == 0:
        return

    match ykm_array[0]:
        case str():
            yield from iter_ids_from_new_format(ykm_array)
        case list():
            yield from iter_ids_from_old_format(ykm_array)
        case _:
            msg = "unsupported ykm array format"
            raise ExternalResponseParseError(msg)


def parse_id(year: int, date: str, log_id: str) -> db.LogEntry:
    if not YAKUMAN_LOG_DATE_PATTERN.fullmatch(date):
        msg = f"invalid yakuman log date: {date}"
        raise ExternalResponseParseError(msg)

    if not YAKUMAN_LOG_ID_PATTERN.fullmatch(log_id):
        msg = f"invalid yakuman log ID: {log_id}"
        raise ExternalResponseParseError(msg)

    log_date = f"{year:04}{date[0:2]}{date[3:5]}"
    # Legacy IDs contain only the date; newer IDs also contain the hour.
    id_date = log_id.split("gm", 1)[0]
    if id_date[:8] != log_date:
        msg = (
            f"yakuman log date does not match log ID: {year} {date}, {log_id}"
        )
        raise ExternalResponseParseError(msg)

    date = parse_date(date[6:11], id_date)
    id_parts = log_id.split("-")
    num_players, is_tonpu = parse_type(id_parts[1])

    return db.LogEntry(
        log_id,
        date,
        num_players,
        is_tonpu,
        is_processed=False,
        was_error=False,
        log=None,
    )


def iter_entries(
    year: int,
    ids: Iterable[tuple[str, str]],
) -> Iterator[db.LogEntry]:
    for date, log_id in ids:
        try:
            entry = parse_id(year, date, log_id)
        except ExternalResponseParseError as e:
            tqdm.write(str(e))
        else:
            yield entry


def yakuman(db_path: Path, year: int, month: int, now: datetime) -> int:
    validate_yakuman_log_date(year, month, now)

    with closing(db.open_db(db_path)) as conn, conn:
        db.setup_table(conn)
        cursor = conn.cursor()

        with create_session() as session:
            url = build_url(year, month)
            resp = fetch_yakuman_log_ids_text(session, url)

            ids = iter_ids(resp)
            entries = iter_entries(year, ids)

            num_logs = db.insert_log_entries(cursor, entries)

    return num_logs
