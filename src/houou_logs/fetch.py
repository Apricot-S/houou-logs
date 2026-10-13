# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import io
import re
import zlib
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import niquests
from niquests.exceptions import RequestException
from tqdm import tqdm

from houou_logs import db
from houou_logs.exceptions import ExternalResponseParseError
from houou_logs.log_id import HOUOU_ARCHIVE_PREFIX, iter_log_entries
from houou_logs.session import TIMEOUT, create_session

MIN_FETCH_INTERVAL = timedelta(minutes=20)
FETCH_KIND_LATEST = "latest"
FETCH_KIND_ARCHIVE = "archive"

INDEX_URL_LATEST = "https://tenhou.net/sc/raw/list.cgi"
INDEX_URL_OLD = "https://tenhou.net/sc/raw/list.cgi?old"
LOG_DOWNLOAD_URL = "https://tenhou.net/sc/raw/dat/"

FILE_INDEX_ENTRY_PATTERN = re.compile(
    r"\{\s*file\s*:\s*'([^']+)'\s*,\s*size\s*:\s*([0-9]+)\s*\}",
)
FILE_INDEX_ARRAY_PATTERN = re.compile(
    r"\s*list\s*\(\s*\[(.*?)\]\s*\)\s*;\s*",
    re.DOTALL,
)
FILE_INDEX_ENTRIES_PATTERN = re.compile(
    rf"\s*{FILE_INDEX_ENTRY_PATTERN.pattern}"
    rf"(?:\s*,\s*{FILE_INDEX_ENTRY_PATTERN.pattern})*\s*,?\s*",
)
EMPTY_FILE_INDEX_PATTERN = re.compile(
    r"^\s*list\s*\(\s*(?:\[\s*\])?\s*\)\s*;\s*$",
)


def should_fetch(
    last_attempt_time: datetime,
    *,
    now: datetime | None = None,
) -> bool:
    if now is None:
        now = datetime.now(tz=UTC)

    return now - last_attempt_time > MIN_FETCH_INTERVAL


def fetch_file_index_text(session: niquests.Session, url: str) -> str:
    res = session.get(url, timeout=TIMEOUT)
    res.raise_for_status()

    text = res.text
    if text is None:
        msg = "response text is None"
        raise ExternalResponseParseError(msg)

    return text


def fetch_log_file_content(session: niquests.Session, url: str) -> bytes:
    res = session.get(url, timeout=TIMEOUT)
    res.raise_for_status()

    content = res.content
    if content is None:
        msg = "response content is None"
        raise ExternalResponseParseError(msg)

    return content


def parse_file_index(response: str) -> dict[str, int]:
    if EMPTY_FILE_INDEX_PATTERN.fullmatch(response):
        return {}

    array = FILE_INDEX_ARRAY_PATTERN.fullmatch(response)
    if array is None or not FILE_INDEX_ENTRIES_PATTERN.fullmatch(array[1]):
        msg = "failed to parse file index"
        raise ExternalResponseParseError(msg)

    matches = FILE_INDEX_ENTRY_PATTERN.findall(array[1])
    try:
        file_index = {path: int(size) for path, size in matches}
    except ValueError as e:
        msg = "file index size exceeds the integer parsing limit"
        raise ExternalResponseParseError(msg) from e
    # Sizes are stored in positive SQLite signed 64-bit INTEGER columns.
    if any(size <= 0 for size in file_index.values()):
        msg = "file index size must be positive"
        raise ExternalResponseParseError(msg)
    if any(size > 2**63 - 1 for size in file_index.values()):
        msg = "file index size exceeds the supported range"
        raise ExternalResponseParseError(msg)
    return file_index


def filter_houou_files(file_index: dict[str, int]) -> dict[str, int]:
    return {
        name: size
        for name, size in file_index.items()
        if Path(name).name.startswith(HOUOU_ARCHIVE_PREFIX)
    }


def fetch(db_path: str | Path, *, archive: bool) -> int:
    num_logs = 0
    first_file_error: Exception | None = None
    with closing(db.open_db(db_path)) as conn, conn:
        db.setup_table(conn)
        cursor = conn.cursor()

        kind = FETCH_KIND_ARCHIVE if archive else FETCH_KIND_LATEST
        last_attempt_time = db.get_fetch_attempt_time(cursor, kind)
        if not should_fetch(last_attempt_time):
            return -1

        db.update_fetch_attempt_time(cursor, kind, datetime.now(UTC))
        conn.commit()

        with create_session() as session:
            index_url = INDEX_URL_OLD if archive else INDEX_URL_LATEST
            resp = fetch_file_index_text(session, index_url)

            file_index = parse_file_index(resp)
            file_index = filter_houou_files(file_index)

            changed_files = db.list_changed_file_index(cursor, file_index)

            for filename, size in tqdm(changed_files.items()):
                url = f"{LOG_DOWNLOAD_URL}{filename}"
                try:
                    content = fetch_log_file_content(session, url)

                    with io.BytesIO(content) as f:
                        entries = iter_log_entries(
                            filename,
                            f,
                            validate_body=True,
                        )
                        inserted = db.insert_log_entries(cursor, entries)
                except (
                    RequestException,
                    ExternalResponseParseError,
                    UnicodeDecodeError,
                    OSError,
                    EOFError,
                    zlib.error,
                ) as e:
                    conn.rollback()
                    tqdm.write(f"{filename}: {e}")
                    if first_file_error is None:
                        first_file_error = e
                    continue

                db.insert_file_index(cursor, filename, size)
                conn.commit()
                num_logs += inserted

            # Report failure only after committing all successful files.
            if first_file_error is not None:
                raise first_file_error

    return num_logs
