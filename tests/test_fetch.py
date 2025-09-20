# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from requests import Response, Session
from requests.exceptions import HTTPError

from houou_logs.fetch import (
    create_session,
    fetch_file_index_text,
    filter_houou_files,
    parse_file_index,
    should_fetch,
)


@pytest.mark.parametrize(
    ("last_fetch_time", "expected"),
    [
        (datetime(2025, 9, 20, 10, 0, 0, 0, tzinfo=UTC), True),
        (datetime(2025, 9, 20, 10, 40, 0, 0, tzinfo=UTC), False),
        (datetime(2025, 9, 20, 10, 39, 59, 999_999, tzinfo=UTC), True),
    ],
)
def test_should_fetch(last_fetch_time: datetime, *, expected: bool) -> None:
    now = datetime(2025, 9, 20, 11, 0, 0, 0, tzinfo=UTC)
    assert should_fetch(last_fetch_time, now=now) == expected


def test_create_session() -> None:
    session = create_session()
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"  # noqa: E501
    assert session.headers["User-Agent"] == user_agent


def test_fetch_file_index_text_success() -> None:
    fake_url = "https://example.com/fileindex"
    fake_text = "file1\nfile2\n"

    mock_session = Mock(spec_set=Session)
    mock_resp = Mock(spec_set=Response)
    mock_resp.text = fake_text
    mock_resp.raise_for_status.return_value = None
    mock_session.get.return_value = mock_resp

    result = fetch_file_index_text(mock_session, fake_url)

    mock_session.get.assert_called_once_with(fake_url, timeout=(5.0, 5.0))
    mock_resp.raise_for_status.assert_called_once()
    assert result == fake_text


def test_fetch_file_index_text_error() -> None:
    fake_url = "https://example.com/fileindex"

    mock_session = Mock(spec_set=Session)
    mock_resp = Mock(spec_set=Response)
    mock_resp.raise_for_status.side_effect = HTTPError("404 Not Found")
    mock_session.get.return_value = mock_resp

    with pytest.raises(HTTPError):
        fetch_file_index_text(mock_session, fake_url)


def test_parse_file_index_empty() -> None:
    resp = """list();"""
    file_index = parse_file_index(resp)
    assert file_index == {}


def test_parse_file_index_latest_1_entry() -> None:
    resp = """list([

{file:'sca20250101.log.gz',size:75399}

]);


"""
    file_index = parse_file_index(resp)
    expected = {"sca20250101.log.gz": 75399}
    assert file_index == expected


def test_parse_file_index_old_1_entry() -> None:
    resp = """list([

{file:'2025/sca20250101.log.gz',size:75399}

]);


"""
    file_index = parse_file_index(resp)
    expected = {"sca20250101.log.gz": 75399}
    assert file_index == expected


def test_parse_file_index_old_2_entries() -> None:
    resp = """list([

{file:'2025/sca20250101.log.gz',size:75399},

{file:'2025/sca20250102.log.gz',size:71074}

]);


"""
    file_index = parse_file_index(resp)
    expected = {"sca20250101.log.gz": 75399, "sca20250102.log.gz": 71074}
    assert file_index == expected


def test_filter_houou_files_empty() -> None:
    assert filter_houou_files({}) == {}


def test_filter_houou_files_contains_no_houou_file() -> None:
    file_index = {"sca20250101.log.gz": 75399, "sca20250102.log.gz": 71074}
    assert filter_houou_files(file_index) == {}


def test_filter_houou_files_contains_houou_file() -> None:
    file_index = {"sca20250101.log.gz": 75399, "scc20250101.html.gz": 40758}
    assert filter_houou_files(file_index) == {"scc20250101.html.gz": 40758}
