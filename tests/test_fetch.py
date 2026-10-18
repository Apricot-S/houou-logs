# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import io
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from niquests import Response, Session
from niquests.exceptions import ConnectionError as NiquestsConnectionError
from niquests.exceptions import HTTPError, Timeout

from houou_logs import db
from houou_logs import fetch as fetch_module
from houou_logs.exceptions import ExternalResponseParseError
from houou_logs.fetch import (
    FetchResult,
    fetch_file_index_text,
    fetch_log_file_content,
    filter_houou_files,
    parse_file_index,
    should_fetch,
)
from houou_logs.log_id import iter_log_entries


@pytest.mark.parametrize(
    "failure",
    ["body", "decode", "gzip", "truncated", "http"],
)
def test_fetch_continues_after_file_errors_and_retries_only_failed_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    path = tmp_path / "fetch.db"
    filenames = [f"scc2025010{i}.html.gz" for i in range(1, 5)]
    contents = [
        gzip.compress(
            f'00:00 log=2025010{i}00gm-00a9-0000-00000000">\n'.encode(),
        )
        for i in range(1, 5)
    ]
    invalid: bytes | Exception
    if failure == "body":
        invalid = gzip.compress(
            gzip.decompress(contents[1]) + b"<html>Service unavailable</html>",
        )
    elif failure == "decode":
        invalid = gzip.compress(gzip.decompress(contents[1]) + b"\xff")
    elif failure == "gzip":
        invalid = b"not gzip"
    elif failure == "truncated":
        invalid = contents[1][:-4]
    else:
        response = Response()
        response.status_code = 404
        invalid = HTTPError("404 Not Found", response=response)
    index = (
        "list(["
        + ",".join(f"{{file:'{filename}',size:123}}" for filename in filenames)
        + "]);"
    )
    monkeypatch.setattr(
        fetch_module,
        "fetch_file_index_text",
        Mock(return_value=index),
    )
    body_fetch = Mock(
        side_effect=[
            contents[0],
            invalid,
            invalid,
            contents[3],
            contents[1],
            contents[2],
        ],
    )
    monkeypatch.setattr(fetch_module, "fetch_log_file_content", body_fetch)
    conn = db.open_db(path)
    try:
        db.setup_table(conn)
        db.insert_file_index(conn.cursor(), filenames[1], 100)
        conn.commit()
    finally:
        conn.close()

    assert fetch_module.fetch(path, archive=False) == FetchResult(2, 2, 2)
    assert body_fetch.call_count == 4
    output = capsys.readouterr().out
    assert filenames[1] in output
    assert filenames[2] in output
    conn = db.open_db(path)
    try:
        assert db.count_all_ids(conn.cursor()) == 2
        assert dict(conn.execute("SELECT file, size FROM file_index")) == {
            filenames[0]: 123,
            filenames[1]: 100,
            filenames[3]: 123,
        }
        db.update_fetch_attempt_time(
            conn.cursor(),
            fetch_module.FETCH_KIND_LATEST,
            datetime.now(UTC)
            - fetch_module.MIN_FETCH_INTERVAL
            - timedelta(seconds=1),
        )
        conn.commit()
    finally:
        conn.close()

    assert fetch_module.fetch(path, archive=False) == FetchResult(2, 2)
    assert body_fetch.call_count == 6
    assert [call.args[1] for call in body_fetch.call_args_list[4:]] == [
        f"{fetch_module.LOG_DOWNLOAD_URL}{filename}"
        for filename in filenames[1:3]
    ]
    conn = db.open_db(path)
    try:
        assert db.count_all_ids(conn.cursor()) == 4
        assert dict(
            conn.execute("SELECT file, size FROM file_index"),
        ) == dict.fromkeys(
            filenames,
            123,
        )
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("last_attempt_time", "expected"),
    [
        (datetime(2025, 9, 20, 10, 0, 0, 0, tzinfo=UTC), True),
        (datetime(2025, 9, 20, 10, 40, 0, 0, tzinfo=UTC), True),
        (datetime(2025, 9, 20, 10, 40, 0, 1, tzinfo=UTC), False),
        (datetime(2025, 9, 20, 10, 39, 59, 999_999, tzinfo=UTC), True),
    ],
)
def test_should_fetch(last_attempt_time: datetime, *, expected: bool) -> None:
    now = datetime(2025, 9, 20, 11, 0, 0, 0, tzinfo=UTC)
    assert should_fetch(last_attempt_time, now=now) == expected


@pytest.mark.parametrize("archive", [False, True])
@pytest.mark.parametrize(
    ("remaining", "delay"),
    [
        (timedelta(minutes=5, seconds=23), "5m 30s"),
        (timedelta(minutes=1), "1m"),
        (timedelta(seconds=12), "20s"),
        (timedelta(seconds=1), "10s"),
        (timedelta(microseconds=1), "10s"),
        (timedelta(seconds=10), "10s"),
        (timedelta(seconds=10, microseconds=1), "20s"),
        (timedelta(0), None),
        (timedelta(microseconds=-1), None),
    ],
)
def test_fetch_retry_delay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    remaining: timedelta,
    delay: str | None,
    *,
    archive: bool,
) -> None:
    path = tmp_path / "fetch.db"
    now = datetime(2025, 9, 20, 11, 0, tzinfo=UTC)
    last_attempt = now - fetch_module.MIN_FETCH_INTERVAL + remaining
    kind = (
        fetch_module.FETCH_KIND_ARCHIVE
        if archive
        else fetch_module.FETCH_KIND_LATEST
    )
    conn = db.open_db(path)
    try:
        db.setup_table(conn)
        db.update_fetch_attempt_time(conn.cursor(), kind, last_attempt)
        conn.commit()
    finally:
        conn.close()
    mock_datetime = Mock(wraps=datetime)
    mock_datetime.now.return_value = now
    monkeypatch.setattr(fetch_module, "datetime", mock_datetime)
    index_fetch = Mock(return_value="list([]);")
    monkeypatch.setattr(fetch_module, "fetch_file_index_text", index_fetch)
    session_factory = Mock(wraps=fetch_module.create_session)
    monkeypatch.setattr(fetch_module, "create_session", session_factory)

    assert fetch_module.fetch(path, archive=archive) == (
        remaining if delay else FetchResult()
    )
    output = capsys.readouterr()
    if delay:
        assert output.out == ""
        assert output.err == ""
        index_fetch.assert_not_called()
        session_factory.assert_not_called()
    else:
        assert "Please retry" not in output.err
        index_fetch.assert_called_once()
    conn = db.open_db(path)
    try:
        assert db.get_fetch_attempt_time(conn.cursor(), kind) == (
            last_attempt if delay else now
        )
    finally:
        conn.close()
    mock_datetime.now.assert_called_once_with(UTC)


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

    with pytest.raises(
        ExternalResponseParseError,
        match="response content is None",
    ):
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
    with pytest.raises(
        ExternalResponseParseError,
        match="failed to parse file index",
    ):
        parse_file_index(resp)


def test_parse_file_index_rejects_oversized_size() -> None:
    limit = sys.get_int_max_str_digits()
    if limit == 0:
        pytest.skip("integer string conversion is unlimited")
    response = "list([{file:'scc.html',size:" + "9" * (limit + 1) + "}]);"
    with pytest.raises(
        ExternalResponseParseError,
        match="file index size exceeds the integer parsing limit",
    ):
        parse_file_index(response)


@pytest.mark.parametrize(
    "response",
    [
        "{file:'scc.html',size:100}",
        "<html>{file:'scc.html',size:100}</html>",
        "list([{file:'scc.html',size:100}",
        "list([{file:'scc.html',size:100}, {file:'other.html',bytes:1}]);",
        "list([{file:'scc.html',size:100}, garbage]);",
        "list([{file:'scc.html',size:100},,]);",
        "list([{file:'scc.html',size:100}]); garbage",
    ],
)
def test_parse_file_index_rejects_partially_valid_response(
    response: str,
) -> None:
    with pytest.raises(
        ExternalResponseParseError,
        match="failed to parse file index",
    ):
        parse_file_index(response)


@pytest.mark.parametrize(
    ("size", "message"),
    [
        (0, "file index size must be positive"),
        (2**63, "file index size exceeds the supported range"),
        (10**100, "file index size exceeds the supported range"),
    ],
)
def test_parse_file_index_rejects_size_outside_sqlite_range(
    size: int,
    message: str,
) -> None:
    with pytest.raises(ExternalResponseParseError, match=message):
        parse_file_index(f"list([{{file:'scc.html',size:{size}}}]);")


def test_parse_file_index_accepts_trailing_comma_and_maximum_size() -> None:
    assert parse_file_index(
        f"list([{{file:'scc.html',size:{2**63 - 1}}},]);",
    ) == {"scc.html": 2**63 - 1}


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

    assert isinstance(fetch_module.fetch(db_path, archive=True), timedelta)
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


@pytest.mark.parametrize("compressed", [False, True])
@pytest.mark.parametrize(
    "failure",
    [None, "decode", "body", "invalid_id", "database", "index"],
)
def test_fetch_file_is_atomic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    compressed: bool,
    failure: str | None,
) -> None:
    path = tmp_path / "fetch.db"
    filename = "scc.html.gz" if compressed else "scc.html"
    content = b'00:00 log=2009020100gm-00a9-0000-00000000">\n' * 2
    if failure == "decode":
        content += b"\xff\n"
    if failure == "body":
        content += b"<html>Service unavailable</html>\n"
    if failure == "invalid_id":
        content += b'00:01 log=invalid">\n'
    if compressed:
        content = gzip.compress(content)
    monkeypatch.setattr(
        fetch_module,
        "fetch_file_index_text",
        Mock(
            return_value=f"list([{{file:'{filename}',size:100}}]);",
        ),
    )
    monkeypatch.setattr(
        fetch_module,
        "fetch_log_file_content",
        Mock(
            return_value=content,
        ),
    )
    statements: list[str] = []
    original_open = db.open_db

    def traced_open(db_path: str | Path) -> sqlite3.Connection:
        conn = original_open(db_path)
        conn.set_trace_callback(statements.append)
        if failure == "database":
            conn.execute(
                "CREATE TRIGGER reject_log BEFORE INSERT ON logs "
                "BEGIN SELECT RAISE(ABORT, 'insert failure'); END;",
            )
        return conn

    # Create the tables before installing the failure trigger.
    initial = original_open(path)
    db.setup_table(initial)
    initial.close()
    monkeypatch.setattr(db, "open_db", traced_open)
    if failure == "index":
        monkeypatch.setattr(
            db,
            "insert_file_index",
            Mock(
                side_effect=sqlite3.OperationalError("index failure"),
            ),
        )
    if failure in ("database", "index"):
        with pytest.raises(sqlite3.DatabaseError):
            fetch_module.fetch(path, archive=False)
    else:
        assert fetch_module.fetch(path, archive=False) == (
            FetchResult(0, 0, 1) if failure else FetchResult(1, 1)
        )
    if not failure:
        start = next(
            i for i, sql in enumerate(statements) if "INSERT INTO logs" in sql
        )
        end = next(
            i
            for i in range(start, len(statements))
            if statements[i] == "COMMIT"
        )
        assert any(
            "INSERT INTO file_index" in sql for sql in statements[start:end]
        )
        # The outer context also commits an empty transaction.
        assert statements[start:].count("COMMIT") == 2
    conn = original_open(path)
    try:
        assert db.count_all_ids(conn.cursor()) == (0 if failure else 1)
        assert conn.execute(
            "SELECT file, size FROM file_index",
        ).fetchall() == ([] if failure else [(filename, 100)])
    finally:
        conn.close()


@pytest.mark.parametrize(
    "content",
    [b"", b"\r\n \t\n", b'00:00 log=2009020100gm-00a9-0000-00000000">\n'],
)
def test_fetch_records_valid_list_with_no_new_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    content: bytes,
) -> None:
    path = tmp_path / "fetch.db"
    filename = "scc20250101.html.gz"
    conn = db.open_db(path)
    try:
        db.setup_table(conn)
        with io.BytesIO(
            b'00:00 log=2009020100gm-00a9-0000-00000000">',
        ) as source:
            db.insert_log_entries(
                conn.cursor(),
                iter_log_entries("scc.html", source),
            )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setattr(
        fetch_module,
        "fetch_file_index_text",
        Mock(return_value=f"list([{{file:'{filename}',size:123}}]);"),
    )
    monkeypatch.setattr(
        fetch_module,
        "fetch_log_file_content",
        Mock(return_value=gzip.compress(content)),
    )
    assert fetch_module.fetch(path, archive=False) == FetchResult(0, 1)
    conn = db.open_db(path)
    try:
        assert conn.execute(
            "SELECT file, size FROM file_index",
        ).fetchall() == [
            (filename, 123),
        ]
        assert db.count_all_ids(conn.cursor()) == 1
    finally:
        conn.close()


@pytest.mark.parametrize(
    "invalid_content",
    [b"", gzip.compress(b"<html>Service unavailable</html>")],
)
def test_fetch_retries_invalid_body_with_unchanged_file_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_content: bytes,
) -> None:
    path = tmp_path / "fetch.db"
    filename = "scc20250101.html.gz"
    monkeypatch.setattr(
        fetch_module,
        "fetch_file_index_text",
        Mock(return_value=f"list([{{file:'{filename}',size:123}}]);"),
    )
    body_fetch = Mock(
        side_effect=[
            Mock(content=invalid_content),
            Mock(
                content=gzip.compress(
                    b'00:00 log=2009020100gm-00a9-0000-00000000">\n',
                ),
            ),
        ],
    )
    session = Mock()
    session.__enter__ = Mock(return_value=Mock(get=body_fetch))
    session.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(
        fetch_module,
        "create_session",
        Mock(return_value=session),
    )
    assert fetch_module.fetch(path, archive=False) == FetchResult(0, 0, 1)
    conn = db.open_db(path)
    try:
        assert conn.execute("SELECT * FROM file_index").fetchall() == []
        assert db.count_all_ids(conn.cursor()) == 0
        db.update_fetch_attempt_time(
            conn.cursor(),
            fetch_module.FETCH_KIND_LATEST,
            datetime.now(UTC)
            - fetch_module.MIN_FETCH_INTERVAL
            - timedelta(seconds=1),
        )
        conn.commit()
    finally:
        conn.close()
    assert fetch_module.fetch(path, archive=False) == FetchResult(1, 1)
    assert body_fetch.call_count == 2
    conn = db.open_db(path)
    try:
        assert conn.execute(
            "SELECT file, size FROM file_index",
        ).fetchall() == [
            (filename, 123),
        ]
        assert db.count_all_ids(conn.cursor()) == 1
    finally:
        conn.close()


@pytest.mark.parametrize("archive", [False, True])
@pytest.mark.parametrize(
    "failure",
    [408, 429, 500, 503, 599, "connection", "timeout"],
)
@pytest.mark.parametrize(
    "retry_after",
    ["3600", "Wed, 21 Oct 2026 07:28:00 GMT"],
)
def test_fetch_stops_and_resumes_after_temporary_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: int | str,
    retry_after: str,
    *,
    archive: bool,
) -> None:
    path = tmp_path / "fetch.db"
    filenames = [f"scc2025010{i}.html.gz" for i in range(1, 4)]
    contents = [
        gzip.compress(
            f'00:00 log=2025010{i}00gm-00a9-0000-00000000">\n'.encode(),
        )
        for i in range(1, 4)
    ]
    monkeypatch.setattr(
        fetch_module,
        "fetch_file_index_text",
        Mock(
            return_value="list(["
            + ",".join(f"{{file:'{name}',size:123}}" for name in filenames)
            + "]);",
        ),
    )
    responses = []
    for content in contents:
        response = Response()
        response.status_code = 200
        response._content = content  # noqa: SLF001
        responses.append(response)
    error: Exception
    if isinstance(failure, int):
        response = Response()
        response.status_code = failure
        response.headers["Retry-After"] = retry_after
        error = HTTPError(f"HTTP {failure}", response=response)
    elif failure == "connection":
        error = NiquestsConnectionError("connection failed")
    else:
        error = Timeout("request timed out")
    session = Mock(spec_set=Session)
    session.get.side_effect = [responses[0], error, *responses[1:]]
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session
    monkeypatch.setattr(fetch_module, "create_session", factory)
    kind = (
        fetch_module.FETCH_KIND_ARCHIVE
        if archive
        else fetch_module.FETCH_KIND_LATEST
    )

    assert fetch_module.fetch(path, archive=archive) == FetchResult(
        1,
        1,
        1,
        stopped=True,
    )
    assert session.get.call_count == 2
    output = capsys.readouterr().out
    assert "fetch stopped" in output
    assert "run fetch again later" in output
    if isinstance(failure, int):
        assert f"Retry-After: {retry_after}" in output
    conn = db.open_db(path)
    try:
        assert db.count_all_ids(conn.cursor()) == 1
        assert conn.execute(
            "SELECT file, size FROM file_index",
        ).fetchall() == [
            (filenames[0], 123),
        ]
        assert isinstance(fetch_module.fetch(path, archive=archive), timedelta)
        assert session.get.call_count == 2
        db.update_fetch_attempt_time(
            conn.cursor(),
            kind,
            datetime.now(UTC)
            - fetch_module.MIN_FETCH_INTERVAL
            - timedelta(seconds=1),
        )
        conn.commit()
    finally:
        conn.close()
    assert fetch_module.fetch(path, archive=archive) == FetchResult(2, 2)
    assert [call.args[0] for call in session.get.call_args_list[2:]] == [
        f"{fetch_module.LOG_DOWNLOAD_URL}{name}" for name in filenames[1:]
    ]
    conn = db.open_db(path)
    try:
        assert db.count_all_ids(conn.cursor()) == 3
        assert dict(conn.execute("SELECT file, size FROM file_index")) == (
            dict.fromkeys(filenames, 123)
        )
    finally:
        conn.close()


@pytest.mark.parametrize("failure", [None, "http", "body", "temporary"])
def test_fetch_empty_or_failed_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    index = {f"scc2025010{i}.html": 123 for i in range(1, 4)}
    monkeypatch.setattr(
        fetch_module,
        "fetch_file_index_text",
        Mock(return_value="list([]);"),
    )
    monkeypatch.setattr(
        fetch_module,
        "parse_file_index",
        Mock(return_value=index if failure else {}),
    )
    response = Response()
    response.status_code = 429 if failure == "temporary" else 404
    error = (
        ExternalResponseParseError("invalid body")
        if failure == "body"
        else HTTPError("request failed", response=response)
    )
    body_fetch = Mock(side_effect=error)
    monkeypatch.setattr(fetch_module, "fetch_log_file_content", body_fetch)
    result = fetch_module.fetch(tmp_path / "fetch.db", archive=False)
    expected = (
        FetchResult(0, 0, 1, stopped=True)
        if failure == "temporary"
        else FetchResult(0, 0, 3 if failure else 0)
    )
    assert result == expected
    assert body_fetch.call_count == expected.num_failed
