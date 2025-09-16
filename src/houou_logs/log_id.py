# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
from html.parser import HTMLParser
from typing import IO

from houou_logs.db import LogEntry


class LogParser(HTMLParser):
    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        pass

    def handle_endtag(self, tag: str) -> None:
        pass

    def handle_data(self, data: str) -> None:
        pass


# b. html.gzなら展開する
# c. htmlを開く
# c. htmlをHTMLパーサーに変換する
# c. HTMLパーサーから対局idを抽出する
# d. 対局idをDBエントリに変換する
# e. DBエントリのリストを返す
def extract_log_entries(filename: str, fileobj: IO[bytes]) -> list[LogEntry]:
    if filename.endswith(".gz"):
        # Logs from 2013 onwards are compressed
        with gzip.open(fileobj, mode="rt", encoding="utf-8") as gz:
            text = gz.read()
    else:
        text = str(fileobj.read())

    return []  # TODO: implement


def extract_ids_from_html(html: str) -> list[str]:
    return []  # TODO: implement


def parse_id(id: str) -> LogEntry:
    raise NotImplementedError
