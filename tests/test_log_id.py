# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import io
from pathlib import Path
from unittest.mock import patch

import pytest

from houou_logs.db import LogEntry
from houou_logs.exceptions import ExternalResponseParseError
from houou_logs.log_id import (
    iter_log_entries,
    parse_date,
    parse_id,
    parse_type,
)

MOCK_LOG = """
00:00 | 07 | 四鳳南喰赤 | <a href="http://tenhou.net/0/?log=2009020100gm-00a9-0000-00000000">牌譜</a> | EXAMPLE2(+47) EXAMPLE(+1) EXAMPLE4(-19) EXAMPLE3(-29)<br>

23:02 | 35 | 四鳳南喰赤 | <a href="http://tenhou.net/0/?log=2009020123gm-00a9-0000-00000001">牌譜</a> | EXAMPLE(+38) EXAMPLE2(+4) EXAMPLE4(-16) EXAMPLE3(-26)<br>

"""  # noqa: E501


@pytest.mark.parametrize("compressed", [False, True])
@pytest.mark.parametrize("content", [b"", b"\r\n \t\r\n"])
def test_validated_list_accepts_empty_body(
    content: bytes,
    *,
    compressed: bool,
) -> None:
    filename = "scc.html.gz" if compressed else "scc.html"
    with io.BytesIO(
        gzip.compress(content) if compressed else content,
    ) as source:
        assert (
            list(iter_log_entries(filename, source, validate_body=True)) == []
        )
        assert not source.closed


@pytest.mark.parametrize("compressed", [False, True])
@pytest.mark.parametrize(
    "content",
    [
        b"<html>Service unavailable</html>",
        b"Service unavailable",
        b"00:00 | missing log link<br>",
        b'00:00 log=invalid">',
    ],
)
def test_validated_list_rejects_invalid_body(
    content: bytes,
    *,
    compressed: bool,
) -> None:
    filename = "scc.html.gz" if compressed else "scc.html"
    with (
        io.BytesIO(
            gzip.compress(content) if compressed else content,
        ) as source,
        pytest.raises(ExternalResponseParseError),
    ):
        list(iter_log_entries(filename, source, validate_body=True))


def test_parse_date() -> None:
    assert parse_date("00:05", "2024010100") == "2024-01-01T00:05"


@pytest.mark.parametrize(
    ("time", "log_date"),
    [
        ("00:00", "2025023100"),
        ("00:00", "2025000100"),
        ("00:00", "2025130100"),
        ("00:00", "2025010000"),
        ("24:00", "2025010124"),
        ("99:99", "2025010199"),
        ("23:60", "2025010123"),
        ("00:00", "2025022900"),
        ("00:00", "2025010124"),
        ("00:00", "0000010100"),
    ],
)
def test_parse_date_and_id_reject_invalid_datetime(
    time: str,
    log_date: str,
) -> None:
    with pytest.raises(ExternalResponseParseError, match="invalid log date"):
        parse_date(time, log_date)
    with pytest.raises(ExternalResponseParseError, match="invalid log date"):
        parse_id(time, f"{log_date}gm-00a9-0000-00000000")


@pytest.mark.parametrize("year", [2024, 2000])
def test_parse_id_accepts_leap_day(year: int) -> None:
    entry = parse_id("23:59", f"{year}022923gm-00a9-0000-00000000")
    assert entry.date == f"{year}-02-29T23:59"


@pytest.mark.parametrize(
    ("time", "log_date"),
    [
        ("0:00", "20250101"),
        ("00:00:00", "20250101"),
        ("00:00", "202501"),
        ("00:00", "20250101000"),
    ],
)
def test_parse_date_rejects_invalid_format(time: str, log_date: str) -> None:
    with pytest.raises(ExternalResponseParseError, match="invalid log date"):
        parse_date(time, log_date)


@pytest.mark.parametrize("compressed", [False, True])
def test_iter_log_entries_skips_invalid_datetime(
    *,
    compressed: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    content = b'99:99 log=2025023199gm-00a9-0000-00000000">\n'
    content += b'23:59 log=2024022923gm-00a9-0000-00000001">\n'
    filename = "scc.html.gz" if compressed else "scc.html"
    payload = gzip.compress(content) if compressed else content
    with io.BytesIO(payload) as source:
        entries = list(iter_log_entries(filename, source))
    assert [entry.date for entry in entries] == ["2024-02-29T23:59"]
    assert f"{filename}: invalid log date" in capsys.readouterr().out
    with (
        io.BytesIO(payload) as source,
        pytest.raises(
            ExternalResponseParseError,
            match="invalid log date",
        ),
    ):
        list(iter_log_entries(filename, source, validate_body=True))


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


def test_parse_id_rejects_invalid_log_id() -> None:
    invalid_log_id = "invalid"

    with pytest.raises(
        ExternalResponseParseError,
        match=f"invalid log ID: {invalid_log_id}",
    ):
        parse_id("00:00", invalid_log_id)


def test_iter_log_entries_propagates_unexpected_value_error() -> None:
    content = b'00:00 log=2009020100gm-00a9-0000-00000000">'
    with (
        io.BytesIO(content) as source,
        patch("houou_logs.log_id.parse_type", side_effect=ValueError("bug")),
        pytest.raises(ValueError, match="bug"),
    ):
        list(iter_log_entries("scc.html", source))


def test_iter_log_entries_skips_extension_log(tmp_path: Path) -> None:
    filename = "not_html.log"
    fake_file = tmp_path / filename
    fake_file.write_bytes(b"not a html")

    with fake_file.open(mode="br") as f:
        entries = list(iter_log_entries(filename, f))

    assert entries == []


def test_iter_log_entries_skips_extension_log_gz(tmp_path: Path) -> None:
    filename = "not_html.log.gz"
    fake_file = tmp_path / filename
    fake_file.write_bytes(b"not a html")

    with fake_file.open(mode="br") as f:
        entries = list(iter_log_entries(filename, f))

    assert entries == []


def test_iter_log_entries_parse_extension_html(tmp_path: Path) -> None:
    filename = "valid_log.html"
    fake_file = tmp_path / filename
    fake_file.write_text(MOCK_LOG, encoding="utf-8")

    with fake_file.open(mode="br") as f:
        entries = list(iter_log_entries(filename, f))

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


def test_iter_log_entries_skips_invalid_log_id(tmp_path: Path) -> None:
    filename = "valid_log.html"
    fake_file = tmp_path / filename
    log = """
00:00 | <a href="http://tenhou.net/0/?log=invalid">牌譜</a><br>
23:02 | <a href="http://tenhou.net/0/?log=2009020123gm-00a9-0000-00000001">牌譜</a><br>
"""
    fake_file.write_text(log, encoding="utf-8")

    with fake_file.open(mode="br") as f:
        entries = list(iter_log_entries(filename, f))

    assert entries == [
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


@pytest.mark.parametrize("compressed", [False, True])
def test_iterator_is_lazy_and_keeps_file_open(
    *,
    compressed: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    content = b'00:00 log=2009020100gm-00a9-0000-00000000">\r\n'
    content += b'00:01 log=invalid">\n'
    content += b'23:02 log=2009020123gm-00a9-0000-00000001">'
    filename = "scc.html.gz" if compressed else "scc.html"
    with io.BytesIO(gzip.compress(content) if compressed else content) as f:
        entries = iter_log_entries(filename, f)
        assert next(entries).id == "2009020100gm-00a9-0000-00000000"
        assert capsys.readouterr().out == ""
        assert [entry.id for entry in entries] == [
            "2009020123gm-00a9-0000-00000001",
        ]
        assert not f.closed
    assert capsys.readouterr().out == f"{filename}: invalid log ID: invalid\n"
