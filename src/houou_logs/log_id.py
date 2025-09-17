# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import re
from html.parser import HTMLParser
from typing import IO

from houou_logs.db import LogEntry


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


_log_parser = LogParser()


def parse_id(id: str) -> LogEntry:
    raise NotImplementedError


# b. html.gzなら展開する
# c. htmlを開く
# c. htmlをHTMLパーサーに変換する
# c. HTMLパーサーから対局idを抽出する
# d. 対局idをDBエントリに変換する
# e. DBエントリのリストを返す
def extract_log_entries(filename: str, fileobj: IO[bytes]) -> list[LogEntry]:
    if filename.endswith(".html.gz"):
        # Logs from 2013 onwards are compressed
        with gzip.open(fileobj, mode="rt", encoding="utf-8") as gz:
            text = gz.read()
    else:
        text = str(fileobj.read())

    ids = _log_parser.extract_ids(text)
    return list(map(parse_id, ids))
