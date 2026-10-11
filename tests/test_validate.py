# SPDX-FileCopyrightText: 2026 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import gzip
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pytest
from examples.split_log_to_game_rounds import split_log_to_game_rounds

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
def test_validation_matches_round_splitting(
    content: str,
    *,
    expected: bool,
) -> None:
    try:
        previous_result = bool(
            split_log_to_game_rounds(content),
        )
    except (ET.ParseError, ValueError):
        previous_result = False
    assert previous_result == expected
    assert validate_module.is_valid_log_content(
        "log-id",
        compress_log(content),
    ) == (previous_result)


def test_validation_does_not_split_or_serialize_elements() -> None:
    with (
        patch(
            "examples.split_log_to_game_rounds.split_log_to_game_rounds",
        ) as split,
        patch("houou_logs.validate.ET.tostring") as serialize,
    ):
        assert validate_module.is_valid_log_content("log-id", valid_log())
    split.assert_not_called()
    serialize.assert_not_called()


def test_validation_rejects_invalid_utf8_after_game_end() -> None:
    content = gzip.compress(b'<mjloggm><AGARI owari="0" /></mjloggm>\xff')
    assert not validate_module.is_valid_log_content("log-id", content)


@pytest.mark.parametrize("content", [None, b"", gzip.compress(b"")])
def test_validation_rejects_missing_or_empty_content(
    content: bytes | None,
) -> None:
    assert not validate_module.is_valid_log_content("log-id", content)


def test_round_splitting_preserves_existing_output() -> None:
    content = (
        '<mjloggm><GO /><INIT shuffle="legacy" /><T1 />'
        '<AGARI /><INIT /><RYUUKYOKU owari="0" />'
        "<UN /><BYE /></mjloggm>"
    )
    assert split_log_to_game_rounds(content) == [
        ["<INIT />", "<T1 />", "<AGARI />"],
        ["<INIT />", '<RYUUKYOKU owari="0" />'],
    ]


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
