# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from pathlib import Path

from houou_logs.exceptions import UserInputError


def validate_players(players: int) -> None:
    if players not in (4, 3):
        msg = f"invalid number of players: {players}."
        raise UserInputError(msg)


def download(db_path: Path, players: int, length: str, limit: int) -> int:
    validate_players(players)

    return 0
