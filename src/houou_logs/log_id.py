# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import re
from functools import cache
from html.parser import HTMLParser
from typing import IO

from houou_logs.db import LogEntry

TYPE_IS_HANCHAN = 0x008
TYPE_IS_3_PLAYERS = 0x010


class LogParser(HTMLParser):
    TARGET_TAG = "a"
    TARGET_ATTR = "href"
    LOG_PATTERN = re.compile(r"log=([^\"]+)")

    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag != self.TARGET_TAG:
            return

        for attr_name, attr_value in attrs:
            if attr_name != self.TARGET_ATTR:
                continue
            if attr_value is None:
                continue
            if match := self.LOG_PATTERN.search(attr_value):
                self.ids.append(match.group(1))

    def extract_ids(self, html: str) -> list[str]:
        self.feed(html)
        ids = self.ids
        self.clear_ids()
        return ids

    def clear_ids(self) -> None:
        self.ids = []


@cache
def get_log_parser() -> LogParser:
    return LogParser()


def parse_date(log_date: str) -> str:
    year = log_date[0:4]
    month = log_date[4:6]
    day = log_date[6:8]
    hour = log_date[8:10]
    return f"{year}-{month}-{day} {hour}"


def parse_type(log_type: str) -> tuple[int, bool]:
    t = int(log_type, 16)
    is_3p = (t & TYPE_IS_3_PLAYERS) == TYPE_IS_3_PLAYERS
    is_hanchan = (t & TYPE_IS_HANCHAN) == TYPE_IS_HANCHAN

    num_players = 3 if is_3p else 4
    is_tonpu = not is_hanchan
    return (num_players, is_tonpu)


def parse_id(log_id: str) -> LogEntry:
    date = parse_date(log_id[0:10])
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
        text = str(fileobj.read())

    parser = get_log_parser()
    ids = parser.extract_ids(text)
    return [parse_id(i) for i in ids]
