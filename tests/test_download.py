# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import pytest

from houou_logs.download import validate_length, validate_players
from houou_logs.exceptions import UserInputError


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
