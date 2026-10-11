# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from niquests import Session
from niquests.exceptions import RequestException

from houou_logs import db
from houou_logs.download import (
    build_url,
    compress_log_content,
    download,
    fetch_log_content_for_download,
    iter_undownloaded_log_id_batches,
    validate_db_path,
    validate_length,
    validate_limit,
    validate_players,
)
from houou_logs.exceptions import LogFetchError, UserInputError


def test_validate_db_path_when_file_exists(tmp_path: Path) -> None:
    db_file = tmp_path / "test.db"
    db_file.write_text("dummy content")
    validate_db_path(db_file)


def test_validate_db_path_when_file_does_not_exist(tmp_path: Path) -> None:
    db_file = tmp_path / "not_exist.db"
    with pytest.raises(UserInputError):
        validate_db_path(db_file)


@pytest.mark.parametrize("players", [4, 3])
def test_validate_players_accepts_valid_counts(players: int) -> None:
    validate_players(players)


@pytest.mark.parametrize("players", [2, 5])
def test_validate_players_rejects_out_of_range(players: int) -> None:
    with pytest.raises(UserInputError):
        validate_players(players)


@pytest.mark.parametrize("length", ["t", "h"])
def test_validate_length_accepts_valid_mode(length: str) -> None:
    validate_length(length)


@pytest.mark.parametrize("length", ["", "i"])
def test_validate_length_rejects_invalid_mode(length: str) -> None:
    with pytest.raises(UserInputError):
        validate_length(length)


@pytest.mark.parametrize("limit", [1, 100])
def test_validate_limit_accepts_valid_counts(limit: int) -> None:
    validate_limit(limit)


@pytest.mark.parametrize("limit", [0, -1])
def test_validate_limit_rejects_out_of_range(limit: int) -> None:
    with pytest.raises(UserInputError):
        validate_limit(limit)


def test_build_url() -> None:
    assert (
        build_url("2024060600gm-00b9-0000-88e70833")
        == "https://tenhou.net/0/log/?2024060600gm-00b9-0000-88e70833"
    )


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
    [LogFetchError("failed"), RequestException()],
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
