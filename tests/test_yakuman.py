# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs


from datetime import UTC, datetime

import pytest

from houou_logs.yakuman import (
    UserInputError,
    validate_yakuman_log_date,
)


def test_validate_yakuman_log_date_month_0_is_invalid() -> None:
    fixed_now = datetime(2025, 9, 15, tzinfo=UTC)
    with pytest.raises(UserInputError):
        validate_yakuman_log_date(2020, 0, fixed_now)


def test_validate_yakuman_log_date_month_13_is_invalid() -> None:
    fixed_now = datetime(2025, 9, 15, tzinfo=UTC)
    with pytest.raises(UserInputError):
        validate_yakuman_log_date(2020, 13, fixed_now)


def test_validate_yakuman_log_date_before_available_from() -> None:
    fixed_now = datetime(2025, 9, 15, tzinfo=UTC)
    with pytest.raises(UserInputError):
        validate_yakuman_log_date(2006, 9, fixed_now)


def test_validate_yakuman_log_date_at_available_from() -> None:
    fixed_now = datetime(2025, 9, 15, tzinfo=UTC)
    validate_yakuman_log_date(2006, 10, fixed_now)


def test_validate_yakuman_log_date_future_date() -> None:
    fixed_now = datetime(2025, 9, 15, tzinfo=UTC)
    with pytest.raises(UserInputError):
        validate_yakuman_log_date(2025, 10, fixed_now)


def test_validate_yakuman_log_date_current_month() -> None:
    fixed_now = datetime(2025, 9, 15, tzinfo=UTC)
    validate_yakuman_log_date(2025, 9, fixed_now)
