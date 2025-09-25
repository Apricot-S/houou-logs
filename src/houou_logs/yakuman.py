# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import ast
import re
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from requests import Session

from houou_logs import db
from houou_logs.exceptions import UserInputError
from houou_logs.log_id import parse_type
from houou_logs.session import TIMEOUT, create_session

YAKUMAN_LOGS_AVAILABLE_FROM = datetime(2006, 10, 1, tzinfo=UTC)

YKM_ARRAY_PATTERN = re.compile(r"ykm=(\[.*?\]);", re.DOTALL)


def validate_yakuman_log_date(year: int, month: int, now: datetime) -> None:
    if not (1 <= month <= 12):  # noqa: PLR2004
        msg = "month must be between 1 and 12"
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
    return res.content.decode("utf-8")


def extract_ids(text: str) -> list[tuple[str, str]]:
    match = YKM_ARRAY_PATTERN.search(text)
    if not match:
        msg = "ykm array not found in input text"
        raise RuntimeError(msg)

    ykm_text = match.group(1)
    ykm_array = ast.literal_eval(ykm_text)

    if len(ykm_array) == 0:
        return []

    match ykm_array[0]:
        case str():
            # New format: format from February 2008
            return [
                (ykm_array[i], ykm_array[i + 4].split("&", 1)[0])
                for i in range(0, len(ykm_array) - 4, 5)
            ]
        case list():
            # Old format: format until January 2008
            return [(entry[0], entry[4]) for entry in ykm_array]
        case _:
            msg = "unsupported ykm array format"
            raise RuntimeError(msg)


def parse_id(year: int, date: str, log_id: str) -> db.LogEntry:
    date = f"{year}-{date[0:2]}-{date[3:5]}T{date[6:11]}"
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


def yakuman(db_path: Path, year: int, month: int, now: datetime) -> int:
    validate_yakuman_log_date(year, month, now)

    with closing(db.open_db(db_path)) as conn, conn:
        db.setup_table(conn)
        cursor = conn.cursor()

        with create_session() as session:
            url = build_url(year, month)
            resp = fetch_yakuman_log_ids_text(session, url)

            ids = extract_ids(resp)
            entries = [parse_id(year, i[0], i[1]) for i in ids]

            db.insert_log_entries(cursor, entries)
            num_logs = len(entries)

    return num_logs
