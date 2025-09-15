# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
from typing import IO

from houou_logs import db


def extract_log_entries(
    filename: str,
    fileobj: IO[bytes],
) -> list[db.LogEntry]:
    if filename.endswith(".gz"):
        # Logs from 2013 onwards are compressed
        with gzip.open(fileobj, mode="rt", encoding="utf-8") as gz:
            pass
    else:
        pass

    return []  # TODO: implement


def parse_ids_from_html(html: str) -> list[db.LogEntry]:
    return []  # TODO: implement
