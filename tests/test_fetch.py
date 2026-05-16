# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from niquests import Response, Session
from niquests.exceptions import HTTPError

from houou_logs import db
from houou_logs import fetch as fetch_module
from houou_logs.fetch import (
    exclude_unchanged_files,
    fetch_file_index_text,
    fetch_log_file_content,
    filter_houou_files,
    parse_file_index,
    should_fetch,
)


@pytest.mark.parametrize(
    ("last_attempt_time", "expected"),
    [
        (datetime(2025, 9, 20, 10, 0, 0, 0, tzinfo=UTC), True),
        (datetime(2025, 9, 20, 10, 40, 0, 0, tzinfo=UTC), False),
        (datetime(2025, 9, 20, 10, 39, 59, 999_999, tzinfo=UTC), True),
    ],
)
def test_should_fetch(last_attempt_time: datetime, *, expected: bool) -> None:
    now = datetime(2025, 9, 20, 11, 0, 0, 0, tzinfo=UTC)
    assert should_fetch(last_attempt_time, now=now) == expected


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


def test_fetch_log_file_content_success() -> None:
    fake_url = "https://example.com/scc20250101.html.gz"
    fake_content = b"content"

    mock_session = Mock(spec_set=Session)
    mock_resp = Mock(spec_set=Response)
    mock_resp.content = fake_content
    mock_resp.raise_for_status.return_value = None
    mock_session.get.return_value = mock_resp

    result = fetch_log_file_content(mock_session, fake_url)

    mock_session.get.assert_called_once_with(fake_url, timeout=(5.0, 5.0))
    mock_resp.raise_for_status.assert_called_once()
    assert result == fake_content


def test_fetch_log_file_content_http_error() -> None:
    fake_url = "https://example.com/scc20250101.html.gz"

    mock_session = Mock(spec_set=Session)
    mock_resp = Mock(spec_set=Response)
    mock_resp.raise_for_status.side_effect = HTTPError("404 Not Found")
    mock_session.get.return_value = mock_resp

    with pytest.raises(HTTPError):
        fetch_log_file_content(mock_session, fake_url)


def test_fetch_log_file_content_none() -> None:
    fake_url = "https://example.com/scc20250101.html.gz"

    mock_session = Mock(spec_set=Session)
    mock_resp = Mock(spec_set=Response)
    mock_resp.content = None
    mock_resp.raise_for_status.return_value = None
    mock_session.get.return_value = mock_resp

    with pytest.raises(RuntimeError, match="response content is None"):
        fetch_log_file_content(mock_session, fake_url)


@pytest.mark.parametrize(
    "resp",
    [
        "list();",
        "list([]);",
        """
list(
);
""",
        """
list([
]);
""",
    ],
)
def test_parse_file_index_empty(resp: str) -> None:
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


def test_parse_file_index_allows_whitespace_around_entry_fields() -> None:
    resp = """list([

{ file : 'scc20250101.html.gz' , size : 40758 }

]);


"""
    file_index = parse_file_index(resp)
    expected = {"scc20250101.html.gz": 40758}
    assert file_index == expected


def test_parse_file_index_rejects_malformed_input() -> None:
    resp = """list([

{file:'scc20250101.html.gz',bytes:40758}

]);


"""
    with pytest.raises(RuntimeError, match="failed to parse file index"):
        parse_file_index(resp)


def test_parse_file_index_old_1_entry() -> None:
    resp = """list([

{file:'2025/sca20250101.log.gz',size:75399}

]);


"""
    file_index = parse_file_index(resp)
    expected = {"2025/sca20250101.log.gz": 75399}
    assert file_index == expected


def test_parse_file_index_old_2_entries() -> None:
    resp = """list([

{file:'2025/sca20250101.log.gz',size:75399},

{file:'2025/sca20250102.log.gz',size:71074}

]);


"""
    file_index = parse_file_index(resp)
    expected = {
        "2025/sca20250101.log.gz": 75399,
        "2025/sca20250102.log.gz": 71074,
    }
    assert file_index == expected


def test_filter_houou_files_empty() -> None:
    assert filter_houou_files({}) == {}


def test_filter_houou_files_contains_no_houou_file() -> None:
    file_index = {"sca20250101.log.gz": 75399, "sca20250102.log.gz": 71074}
    assert filter_houou_files(file_index) == {}


def test_filter_houou_files_contains_houou_file() -> None:
    file_index = {"sca20250101.log.gz": 75399, "scc20250101.html.gz": 40758}
    assert filter_houou_files(file_index) == {"scc20250101.html.gz": 40758}


def test_filter_houou_files_contains_old_houou_file() -> None:
    file_index = {
        "2025/sca20250101.log.gz": 75399,
        "2025/scc20250101.html.gz": 40758,
    }
    assert filter_houou_files(file_index) == {
        "2025/scc20250101.html.gz": 40758,
    }


def test_filter_houou_files_ignores_prefix_in_directory_name() -> None:
    file_index = {"scc_archive/sca20250101.log.gz": 75399}
    assert filter_houou_files(file_index) == {}


def test_exclude_unchanged_files_excludes_unchanged_file() -> None:
    file_index = {"sca20250101.log.gz": 75399, "scc20250101.html.gz": 40759}
    db_records = {"sca20250101.log.gz": 75399, "scc20250101.html.gz": 40758}
    ret = exclude_unchanged_files(file_index, db_records)
    assert ret == {"scc20250101.html.gz": 40759}


def test_fetch_archive_uses_archive_attempt_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "archive.db"
    conn = db.open_db(db_path)
    try:
        db.setup_table(conn)
        cursor = conn.cursor()
        db.update_fetch_attempt_time(
            cursor,
            fetch_module.FETCH_KIND_ARCHIVE,
            datetime.now(UTC),
        )
        conn.commit()
    finally:
        conn.close()

    mock_fetch_file_index_text = Mock()
    monkeypatch.setattr(
        fetch_module,
        "fetch_file_index_text",
        mock_fetch_file_index_text,
    )

    assert fetch_module.fetch(db_path, archive=True) == -1
    mock_fetch_file_index_text.assert_not_called()


def test_fetch_updates_attempt_time_before_file_index_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "latest.db"
    fixed_now = datetime(2025, 9, 20, 11, 0, 0, tzinfo=UTC)

    mock_datetime = Mock(wraps=datetime)
    mock_datetime.now.return_value = fixed_now
    monkeypatch.setattr(fetch_module, "datetime", mock_datetime)
    monkeypatch.setattr(
        fetch_module,
        "fetch_file_index_text",
        Mock(side_effect=OSError("network is unreachable")),
    )

    with pytest.raises(OSError, match="network is unreachable"):
        fetch_module.fetch(db_path, archive=False)

    conn = db.open_db(db_path)
    try:
        cursor = conn.cursor()
        last_attempt_time = db.get_fetch_attempt_time(
            cursor,
            fetch_module.FETCH_KIND_LATEST,
        )
        assert last_attempt_time == fixed_now
    finally:
        conn.close()
