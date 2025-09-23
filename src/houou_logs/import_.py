# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from zipfile import ZipFile, ZipInfo, is_zipfile

from tqdm import tqdm

from houou_logs import db
from houou_logs.exceptions import UserInputError
from houou_logs.log_id import HOUOU_ARCHIVE_PREFIX, extract_log_entries


def validate_archive(archive_path: Path) -> None:
    if not archive_path.is_file():
        msg = f"archive file not found: {archive_path}"
        raise UserInputError(msg)

    if not is_zipfile(archive_path):
        msg = f"archive file must be zip file: {archive_path}"
        raise UserInputError(msg)


def iter_houou_archive_files(zf: ZipFile) -> Iterator[ZipInfo]:
    for info in zf.infolist():
        if info.is_dir():
            continue
        filename = Path(info.filename).name
        if filename.startswith(HOUOU_ARCHIVE_PREFIX):
            yield info


def import_(db_path: str | Path, archive_path: Path) -> int:
    validate_archive(archive_path)

    num_logs = 0
    with closing(db.open_db(db_path)) as conn, conn:
        db.setup_table(conn)
        cursor = conn.cursor()

        with ZipFile(archive_path) as zf:
            for info in tqdm(list(iter_houou_archive_files(zf))):
                with zf.open(info) as f:
                    entries = extract_log_entries(info.filename, f)

                db.insert_log_entries(cursor, entries)
                num_logs += len(entries)

    return num_logs
