# SPDX-FileCopyrightText: 2026 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from pathlib import Path

from houou_logs.exceptions import UserInputError


def validate_db_path(db_path: Path) -> None:
    if not db_path.is_file():
        msg = f"database file is not found: {db_path}"
        raise UserInputError(msg)


def validate_players(players: int) -> None:
    if players not in (4, 3):
        msg = f"invalid number of players: {players}"
        raise UserInputError(msg)


def validate_length(length: str) -> None:
    if length not in ("t", "h"):
        msg = f"invalid length of game: {length}"
        raise UserInputError(msg)


def validate_limit(limit: int) -> None:
    if limit <= 0:
        msg = f"invalid limit: {limit}"
        raise UserInputError(msg)
