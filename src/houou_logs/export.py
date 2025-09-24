# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from pathlib import Path

from houou_logs.download import (
    validate_length,
    validate_limit,
    validate_players,
)
from houou_logs.user_input import validate_offset


def export(
    db_path: Path,
    output_dir: Path,
    players: int | None,
    length: str | None,
    limit: int | None,
    offset: int,
) -> int:
    if players is not None:
        validate_players(players)
    if length is not None:
        validate_length(length)
    if limit is not None:
        validate_limit(limit)
    validate_offset(offset)

    output_dir.mkdir(parents=True, exist_ok=True)

    return 0
