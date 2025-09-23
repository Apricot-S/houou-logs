# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import pytest

from houou_logs.download import (
    build_url,
    validate_length,
    validate_limit,
    validate_players,
)
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
