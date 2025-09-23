# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import io
import re
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests
from tqdm import tqdm

from houou_logs import db
from houou_logs.log_id import HOUOU_ARCHIVE_PREFIX, extract_log_entries
from houou_logs.session import TIMEOUT, create_session

MIN_FETCH_INTERVAL = timedelta(minutes=20)

INDEX_URL_LATEST = "https://tenhou.net/sc/raw/list.cgi"
INDEX_URL_OLD = "https://tenhou.net/sc/raw/list.cgi?old"
LOG_DOWNLOAD_URL = "https://tenhou.net/sc/raw/dat/"

FILE_INDEX_ENTRY_PATTERN = re.compile(r"file:'([^']+)',size:(\d+)")


def should_fetch(
    last_fetch_time: datetime,
    *,
    now: datetime | None = None,
) -> bool:
    if now is None:
        now = datetime.now(tz=UTC)

    return now - last_fetch_time > MIN_FETCH_INTERVAL


def fetch_file_index_text(session: requests.Session, url: str) -> str:
    res = session.get(url, timeout=TIMEOUT)
    res.raise_for_status()
    return res.text


def parse_file_index(response: str) -> dict[str, int]:
    matches = FILE_INDEX_ENTRY_PATTERN.findall(response)
    return {path: int(size) for path, size in matches}


def filter_houou_files(file_index: dict[str, int]) -> dict[str, int]:
    return {
        name: size
        for name, size in file_index.items()
        if HOUOU_ARCHIVE_PREFIX in name
    }


def exclude_unchanged_files(
    file_index: dict[str, int],
    db_records: dict[str, int],
) -> dict[str, int]:
    return {
        name: size
        for name, size in file_index.items()
        if db_records.get(name) != size
    }


def fetch(db_path: str | Path, *, archive: bool) -> int:
    num_logs = 0
    with closing(db.open_db(db_path)) as conn, conn:
        db.setup_table(conn)
        cursor = conn.cursor()

        if not archive:
            last_fetch_time = db.get_last_fetch_time(cursor)
            if not should_fetch(last_fetch_time):
                return -1

        with create_session() as session:
            index_url = INDEX_URL_OLD if archive else INDEX_URL_LATEST
            resp = fetch_file_index_text(session, index_url)

            file_index = parse_file_index(resp)
            file_index = filter_houou_files(file_index)

            db_records = db.get_file_index(cursor)
            changed_files = exclude_unchanged_files(file_index, db_records)

            for filename, size in tqdm(changed_files.items()):
                url = f"{LOG_DOWNLOAD_URL}{filename}"
                page = session.get(url, timeout=TIMEOUT)

                with io.BytesIO(page.content) as f:
                    entries = extract_log_entries(filename, f)

                num_logs += len(entries)
                db.insert_log_entries(cursor, entries)
                db.insert_file_index(cursor, filename, size)

                conn.commit()

        if not archive:
            now = datetime.now(UTC)
            db.update_last_fetch_time(cursor, now)

    return num_logs
