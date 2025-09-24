# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from pathlib import Path

from houou_logs.db import LogEntry
from houou_logs.log_id import (
    extract_ids,
    extract_log_entries,
    parse_date,
    parse_type,
)

MOCK_LOG = """
00:00 | 07 | 四鳳南喰赤 | <a href="http://tenhou.net/0/?log=2009020100gm-00a9-0000-00000000">牌譜</a> | EXAMPLE2(+47) EXAMPLE(+1) EXAMPLE4(-19) EXAMPLE3(-29)<br>

23:02 | 35 | 四鳳南喰赤 | <a href="http://tenhou.net/0/?log=2009020123gm-00a9-0000-00000001">牌譜</a> | EXAMPLE(+38) EXAMPLE2(+4) EXAMPLE4(-16) EXAMPLE3(-26)<br>

"""  # noqa: E501


def test_extract_ids_empty_text() -> None:
    assert extract_ids("") == []


def test_extract_ids_no_match() -> None:
    log = "L1000 | 21:37 | 四般南－－ | NoName(+48) NoName(+13) NoName(-25) NoName(-36)"  # noqa: E501, RUF001
    assert extract_ids(log) == []


def test_extract_ids_multiple_matches() -> None:
    ids = [
        ("00:00", "2009020100gm-00a9-0000-00000000"),
        ("23:02", "2009020123gm-00a9-0000-00000001"),
    ]
    assert extract_ids(MOCK_LOG) == ids


def test_parse_date() -> None:
    assert parse_date("00:05", "2024010100") == "2024-01-01T00:05"


def test_parse_type_4_hanchan() -> None:
    num_players, is_tonpu = parse_type("00a9")
    assert num_players == 4
    assert not is_tonpu


def test_parse_type_4_tonpu() -> None:
    num_players, is_tonpu = parse_type("00e1")
    assert num_players == 4
    assert is_tonpu


def test_parse_type_3_hanchan() -> None:
    num_players, is_tonpu = parse_type("00b9")
    assert num_players == 3
    assert not is_tonpu


def test_extract_log_entries_skips_extension_log(tmp_path: Path) -> None:
    filename = "not_html.log"
    fake_file = tmp_path / filename
    fake_file.write_bytes(b"not a html")

    with fake_file.open(mode="br") as f:
        entries = extract_log_entries(filename, f)

    assert entries == []


def test_extract_log_entries_skips_extension_log_gz(tmp_path: Path) -> None:
    filename = "not_html.log.gz"
    fake_file = tmp_path / filename
    fake_file.write_bytes(b"not a html")

    with fake_file.open(mode="br") as f:
        entries = extract_log_entries(filename, f)

    assert entries == []


def test_extract_log_entries_parse_extension_html(tmp_path: Path) -> None:
    filename = "valid_log.html"
    fake_file = tmp_path / filename
    fake_file.write_text(MOCK_LOG, encoding="utf-8")

    with fake_file.open(mode="br") as f:
        entries = extract_log_entries(filename, f)

    expected = [
        LogEntry(
            id="2009020100gm-00a9-0000-00000000",
            date="2009-02-01T00:00",
            num_players=4,
            is_tonpu=False,
            is_processed=False,
            was_error=False,
            log=None,
        ),
        LogEntry(
            id="2009020123gm-00a9-0000-00000001",
            date="2009-02-01T23:02",
            num_players=4,
            is_tonpu=False,
            is_processed=False,
            was_error=False,
            log=None,
        ),
    ]
    assert entries == expected
