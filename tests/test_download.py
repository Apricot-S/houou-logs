# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest
from niquests import Session
from niquests.exceptions import RequestException

from houou_logs import db
from houou_logs.download import (
    build_url,
    compress_log_content,
    download,
    fetch_log_content,
    fetch_log_content_for_download,
    iter_undownloaded_log_id_batches,
)
from houou_logs.exceptions import LogFetchError, TemporaryLogFetchError
from houou_logs.session import TIMEOUT


@pytest.mark.parametrize(
    "content",
    [
        b'<mjloggm ver="2.3"><AGARI owari="1" /></mjloggm>',
        b'\xef\xbb\xbf \r\n<?xml version="1.0"?>\n<mjloggm/>',
        b'<mjloggm\tver="2.3"/>',
        b'<mjloggm><UN n0="raw & invalid"/></mjloggm>',
        b'<mjloggm><UN n0="\xff"/>',
        b'<mjloggm ver="2.3"><UN',
    ],
)
def test_fetch_log_content_uses_bytes_without_decoding(content: bytes) -> None:
    response = Mock(status_code=200, content=content)
    type(response).text = PropertyMock(side_effect=AssertionError("decoded"))
    session = Mock(spec_set=Session)
    session.get.return_value = response

    assert fetch_log_content(session, "https://example.com") is content
    session.get.assert_called_once_with("https://example.com", timeout=TIMEOUT)


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"mjlog is unavailable",
        b"<html><body>mjlog unavailable</body></html>",
        b"<html><mjloggm/></html>",
        b"<!-- <mjloggm/> -->",
        b"<mjloggm-error/>",
        b"<mjloggmExtra/>",
        b"</mjloggm>",
    ],
)
def test_fetch_log_content_rejects_non_log_response(content: bytes) -> None:
    session = Mock(spec_set=Session)
    session.get.return_value = Mock(status_code=200, content=content)
    with pytest.raises(LogFetchError, match="no log content"):
        fetch_log_content(session, "https://example.com")


def test_fetch_log_content_rejects_missing_content() -> None:
    session = Mock(spec_set=Session)
    session.get.return_value = Mock(status_code=200, content=None)
    with pytest.raises(LogFetchError, match="content could not be retrieved"):
        fetch_log_content(session, "https://example.com")


def test_fetch_log_content_rejects_http_error() -> None:
    session = Mock(spec_set=Session)
    session.get.return_value = Mock(status_code=404, content=b"<mjloggm/>")
    with pytest.raises(LogFetchError, match="HTTP 404"):
        fetch_log_content(session, "https://example.com")


def test_build_url() -> None:
    assert (
        build_url("2024060600gm-00b9-0000-88e70833")
        == "https://tenhou.net/0/log/?2024060600gm-00b9-0000-88e70833"
    )


def test_download_commits_each_log_before_next_request(db_path: Path) -> None:
    log_ids = [f"202501010{i}gm-00a9-0000-00000000" for i in range(2)]
    content = b'<mjloggm><AGARI owari="1"/></mjloggm>'
    with db.open_db(db_path) as conn:
        db.setup_table(conn)
        db.insert_log_entries(
            conn.cursor(),
            [
                db.LogEntry(
                    log_id,
                    "2025-01-01",
                    4,
                    is_tonpu=False,
                    is_processed=False,
                    was_error=False,
                    log=None,
                )
                for log_id in log_ids
            ],
        )

    def get(url: str, *, timeout: tuple[float, float]) -> Mock:
        assert timeout == TIMEOUT
        if url == build_url(log_ids[1]):
            with db.open_db(db_path) as reader:
                row = reader.execute(
                    "SELECT is_processed, was_error, log FROM logs "
                    "WHERE id = ?",
                    (log_ids[0],),
                ).fetchone()
            assert row[:2] == (1, 0)
            assert gzip.decompress(row[2]) == content
            msg = "interrupted after first commit"
            raise RuntimeError(msg)
        return Mock(status_code=200, content=content)

    with patch("houou_logs.download.create_session") as create:
        create.return_value.__enter__.return_value.get.side_effect = get
        with pytest.raises(RuntimeError, match="interrupted"):
            download(db_path, None, None, None)

    with db.open_db(db_path) as conn:
        assert conn.execute(
            "SELECT is_processed FROM logs WHERE id = ?",
            (log_ids[1],),
        ).fetchone() == (0,)


def test_iter_undownloaded_log_id_batches_respects_limit() -> None:
    mock_cursor = Mock()
    mock_cursor.fetchall.side_effect = [
        [("2009010100gm-00a9-0000-00000000",)],
        [("2009010101gm-00a9-0000-00000000",)],
    ]

    actual = list(
        iter_undownloaded_log_id_batches(
            mock_cursor,
            None,
            None,
            2,
            1,
        ),
    )

    expected = [
        ["2009010100gm-00a9-0000-00000000"],
        ["2009010101gm-00a9-0000-00000000"],
    ]
    assert actual == expected
    assert mock_cursor.execute.call_count == 2


def test_fetch_log_content_for_download_success() -> None:
    mock_session = Mock(spec_set=Session)
    content = b"<mjloggm></mjloggm>"

    with patch("houou_logs.download.fetch_log_content", return_value=content):
        was_error, actual = fetch_log_content_for_download(
            mock_session,
            "2024060600gm-00b9-0000-88e70833",
        )

    assert not was_error
    assert actual == content


@pytest.mark.parametrize(
    "error",
    [
        LogFetchError("failed"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"),
    ],
)
def test_fetch_log_content_for_download_fetch_error(error: Exception) -> None:
    mock_session = Mock(spec_set=Session)

    with patch(
        "houou_logs.download.fetch_log_content",
        side_effect=error,
    ):
        was_error, actual = fetch_log_content_for_download(
            mock_session,
            "2024060600gm-00b9-0000-88e70833",
        )

    assert was_error
    assert actual == b""


def test_compress_log_content_success() -> None:
    was_error, compressed_content = compress_log_content(
        "2024060600gm-00b9-0000-88e70833",
        b"<mjloggm></mjloggm>",
    )

    assert not was_error
    assert compressed_content is not None


def test_compress_log_content_compress_error() -> None:
    with patch("houou_logs.download.gzip.compress", side_effect=OSError):
        was_error, compressed_content = compress_log_content(
            "2024060600gm-00b9-0000-88e70833",
            b"log",
        )

    assert was_error
    assert compressed_content is None


@pytest.mark.parametrize("error_type", [RuntimeError, TypeError, MemoryError])
@pytest.mark.parametrize("stage", ["fetch_log_content", "gzip.compress"])
def test_download_unexpected_error_preserves_unprocessed_log(
    db_path: Path,
    error_type: type[Exception],
    stage: str,
) -> None:
    log_id = "2025010100gm-00a9-0000-00000000"
    with db.open_db(db_path) as conn:
        db.setup_table(conn)
        db.insert_log_entries(
            conn.cursor(),
            [
                db.LogEntry(
                    log_id,
                    "2025-01-01",
                    4,
                    is_tonpu=False,
                    is_processed=False,
                    was_error=False,
                    log=None,
                ),
            ],
        )
    with (
        patch("houou_logs.download.create_session"),
        patch("houou_logs.download.fetch_log_content", return_value=b"log"),
        patch(f"houou_logs.download.{stage}", side_effect=error_type),
        pytest.raises(error_type),
    ):
        download(db_path, None, None, None)
    with db.open_db(db_path) as conn:
        row = conn.execute(
            "SELECT is_processed, was_error, log FROM logs WHERE id = ?",
            (log_id,),
        ).fetchone()
    assert row == (0, 0, None)


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504, 599])
@pytest.mark.parametrize(
    "retry_after",
    [None, "120", "Wed, 21 Oct 2026 07:28:00 GMT"],
)
def test_download_stops_and_can_resume(
    db_path: Path,
    status: int,
    retry_after: str | None,
) -> None:
    log_ids = [f"202501010{i}gm-00a9-0000-00000000" for i in range(3)]
    content = b"<mjloggm/>"
    with db.open_db(db_path) as conn:
        db.setup_table(conn)
        db.insert_log_entries(
            conn.cursor(),
            [
                db.LogEntry(
                    log_id,
                    "2025-01-01",
                    4,
                    is_tonpu=False,
                    is_processed=False,
                    was_error=False,
                    log=None,
                )
                for log_id in log_ids
            ],
        )
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    with (
        patch("houou_logs.download.create_session") as create,
        patch(
            "houou_logs.download.tqdm.write",
        ) as write,
    ):
        session = create.return_value.__enter__.return_value
        session.get.side_effect = [
            Mock(status_code=200, content=content),
            Mock(status_code=status, headers=headers),
        ]
        assert download(db_path, None, None, None) == 1
        assert session.get.call_count == 2
        assert f"HTTP {status}" in write.call_args.args[0]
        if retry_after is not None:
            assert f"Retry-After: {retry_after}" in write.call_args.args[0]
    with db.open_db(db_path) as conn:
        rows = conn.execute(
            "SELECT is_processed, was_error, log FROM logs ORDER BY id",
        ).fetchall()
    assert rows[0][:2] == (1, 0)
    assert gzip.decompress(rows[0][2]) == content
    assert rows[1:] == [(0, 0, None), (0, 0, None)]
    with patch("houou_logs.download.create_session") as create:
        session = create.return_value.__enter__.return_value
        session.get.return_value = Mock(status_code=200, content=content)
        assert download(db_path, None, None, None) == 2
        assert [call.args[0] for call in session.get.call_args_list] == [
            build_url(log_id) for log_id in log_ids[1:]
        ]


def test_network_error_is_retryable() -> None:
    session = Mock(spec_set=Session)
    session.get.side_effect = RequestException("connection failed")
    with pytest.raises(TemporaryLogFetchError, match="connection failed"):
        fetch_log_content_for_download(session, "log-id")


def test_permanent_http_error_is_recorded() -> None:
    session = Mock(spec_set=Session)
    session.get.return_value = Mock(status_code=404)
    assert fetch_log_content_for_download(session, "log-id") == (True, b"")
