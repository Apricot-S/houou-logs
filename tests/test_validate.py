# SPDX-FileCopyrightText: 2026 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from houou_logs import db
from houou_logs import validate as validate_module


@pytest.mark.parametrize(
    "content",
    [
        b"not gzip",
        gzip.compress(b"log")[:-4],
        gzip.compress(b"\xff"),
        gzip.compress(b"<broken"),
        gzip.compress(b"<other />"),
        gzip.compress(b"<mjloggm />"),
    ],
)
def test_expected_invalid_content_is_rejected(content: bytes) -> None:
    assert not validate_module.is_valid_log_content("log-id", content)


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError, MemoryError])
@pytest.mark.parametrize(
    "stage",
    ["gzip.decompress", "validate_log_structure"],
)
def test_validate_unexpected_error_preserves_saved_content(
    db_path: Path,
    error_type: type[Exception],
    stage: str,
) -> None:
    log_id = "2025010100gm-00a9-0000-00000000"
    content = valid_log()
    with db.open_db(db_path) as conn:
        db.setup_table(conn)
        insert_processed_log(conn.cursor(), log_id, content)
    with (
        patch(f"houou_logs.validate.{stage}", side_effect=error_type),
        pytest.raises(error_type),
    ):
        validate_module.validate(db_path)
    with db.open_db(db_path) as conn:
        row = conn.execute(
            "SELECT is_processed, was_error, log FROM logs WHERE id = ?",
            (log_id,),
        ).fetchone()
    assert row == (1, 0, content)


def compress_log(content: str) -> bytes:
    return gzip.compress(content.encode("utf-8"), mtime=0)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('<mjloggm><AGARI owari="" /></mjloggm>', True),
        ('<mjloggm><RYUUKYOKU owari="0" /><UN /><BYE /></mjloggm>', True),
        (
            (
                "<mjloggm><GO /><SHUFFLE /><TAIKYOKU /><UN />"
                '<INIT shuffle="legacy" /><T1 /><AGARI /><INIT />'
                '<RYUUKYOKU owari="0" /><UN /><BYE /></mjloggm>'
            ),
            True,
        ),
        ('<mjloggm><INIT /><unknown /><AGARI owari="0" /></mjloggm>', True),
        ('<other><AGARI owari="0" /></other>', False),
        ('<mjloggm xmlns="urn:test"><AGARI owari="0" /></mjloggm>', False),
        ('<mjloggm><AGARI owari="0" /><INIT /></mjloggm>', False),
        ('<mjloggm><AGARI owari="0" /><GO /></mjloggm>', False),
        ('<mjloggm><AGARI owari="0" /><AGARI owari="0" /></mjloggm>', False),
        ('<mjloggm><INIT owari="0" /></mjloggm>', False),
        ('<mjloggm><UN><AGARI owari="0" /></UN></mjloggm>', False),
        ("<mjloggm><AGARI /></mjloggm>", False),
        ('<mjloggm><AGARI owari="0" />', False),
        ('<mjloggm><AGARI owari="0" /><UN></mjloggm>', False),
        ('<mjloggm><AGARI owari="0" /></mjloggm>trailing', False),
        ('<mjloggm><AGARI owari="0" /></mjloggm><other />', False),
        ("<mjloggm />", False),
        ("", False),
    ],
)
def test_validation_checks_log_structure(
    content: str,
    *,
    expected: bool,
) -> None:
    assert (
        validate_module.is_valid_log_content(
            "log-id",
            compress_log(content),
        )
        == expected
    )


def test_validation_does_not_serialize_elements() -> None:
    with patch("houou_logs.validate.ET.tostring") as serialize:
        assert validate_module.is_valid_log_content("log-id", valid_log())
    serialize.assert_not_called()


def test_validation_rejects_invalid_utf8_after_game_end() -> None:
    content = gzip.compress(b'<mjloggm><AGARI owari="0" /></mjloggm>\xff')
    assert not validate_module.is_valid_log_content("log-id", content)


@pytest.mark.parametrize("content", [None, b"", gzip.compress(b"")])
def test_validation_rejects_missing_or_empty_content(
    content: bytes | None,
) -> None:
    assert not validate_module.is_valid_log_content("log-id", content)


def valid_log() -> bytes:
    return compress_log(
        """
        <mjloggm ver="2.3">
            <INIT seed="0,0,0,0,0,0" ten="25000,25000,25000,25000" />
            <AGARI owari="25000,0,25000,0,25000,0,25000,0" />
        </mjloggm>
        """,
    )


def insert_processed_log(
    cursor: sqlite3.Cursor,
    log_id: str,
    log: bytes,
) -> None:
    db.insert_log_entries(
        cursor,
        [
            db.LogEntry(
                id=log_id,
                date="2025-01-01",
                num_players=4,
                is_tonpu=False,
                is_processed=True,
                was_error=False,
                log=log,
            ),
        ],
    )


def test_validate_continues_after_resetting_invalid_log(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = db.open_db(db_path)
    try:
        db.setup_table(conn)
        cursor = conn.cursor()
        insert_processed_log(
            cursor,
            "2025010100gm-00a9-0000-00000000",
            valid_log(),
        )
        insert_processed_log(
            cursor,
            "2025010101gm-00a9-0000-00000000",
            b"not gzip data",
        )
        insert_processed_log(
            cursor,
            "2025010102gm-00a9-0000-00000000",
            valid_log(),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(validate_module, "VALIDATE_BATCH_SIZE", 2)

    assert validate_module.validate(db_path) == (True, 2, 3)

    conn = db.open_db(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, is_processed, was_error, log
            FROM logs
            ORDER BY id ASC;
            """,
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    assert rows[0][1:] == (1, 0, valid_log())
    assert rows[1] == (
        "2025010101gm-00a9-0000-00000000",
        0,
        0,
        None,
    )
    assert rows[2][1:] == (1, 0, valid_log())


@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt])
@pytest.mark.parametrize("stage", ["validation", "reset"])
def test_validate_interrupted_batch_preserves_committed_batches(
    db_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[BaseException],
    stage: str,
) -> None:
    log_ids = [f"log-{index}" for index in range(6)]
    contents = [
        b"invalid",
        valid_log(),
        b"invalid",
        b"invalid",
        b"invalid",
        valid_log(),
    ]
    with db.open_db(db_path) as conn:
        db.setup_table(conn)
        for log_id, content in zip(log_ids, contents, strict=True):
            insert_processed_log(conn.cursor(), log_id, content)

    monkeypatch.setattr(validate_module, "VALIDATE_BATCH_SIZE", 2)
    original_validate = validate_module.is_valid_log_content
    original_reset = db.reset_log_content

    def check_content(log_id: str, content: bytes | None) -> bool:
        # Checking a batch must not hold a write lock.
        if log_id == log_ids[1]:
            with sqlite3.connect(db_path, timeout=0) as observer:
                observer.execute("BEGIN IMMEDIATE")
                observer.rollback()
        if stage == "validation" and log_id == log_ids[3]:
            raise error_type
        return original_validate(log_id, content)

    def reset_content(cursor: sqlite3.Cursor, log_id: str) -> None:
        original_reset(cursor, log_id)
        if stage == "reset" and log_id == log_ids[2]:
            raise error_type

    monkeypatch.setattr(validate_module, "is_valid_log_content", check_content)
    monkeypatch.setattr(db, "reset_log_content", reset_content)
    with pytest.raises(error_type):
        validate_module.validate(db_path)

    with db.open_db(db_path) as conn:
        rows = conn.execute(
            "SELECT is_processed, was_error, log FROM logs ORDER BY id",
        ).fetchall()
    assert rows[0] == (0, 0, None)
    assert rows[1:] == [(1, 0, content) for content in contents[1:]]

    # A rerun checks interrupted and previously unreached entries.
    monkeypatch.setattr(
        validate_module,
        "is_valid_log_content",
        original_validate,
    )
    monkeypatch.setattr(db, "reset_log_content", original_reset)
    assert validate_module.validate(db_path) == (True, 2, 6)
    with db.open_db(db_path) as conn:
        rows = conn.execute(
            "SELECT is_processed, was_error, log FROM logs ORDER BY id",
        ).fetchall()
    assert rows == [
        (1, 0, content) if content == valid_log() else (0, 0, None)
        for content in contents
    ]
