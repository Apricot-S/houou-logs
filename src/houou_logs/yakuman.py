# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from datetime import UTC, datetime
from pathlib import Path

from houou_logs.exceptions import UserInputError

YAKUMAN_LOGS_AVAILABLE_FROM = datetime(2006, 10, 1, tzinfo=UTC)


def validate_yakuman_log_date(year: int, month: int, now: datetime) -> None:
    if not (1 <= month <= 12):  # noqa: PLR2004
        msg = "month must be between 1 and 12"
        raise UserInputError(msg)

    target_date = datetime(year, month, 1, tzinfo=UTC)

    if target_date < YAKUMAN_LOGS_AVAILABLE_FROM:
        msg = f"yakuman logs are available starting from {YAKUMAN_LOGS_AVAILABLE_FROM.year}/{YAKUMAN_LOGS_AVAILABLE_FROM.month}"  # noqa: E501
        raise UserInputError(msg)

    if target_date > now:
        msg = "future dates are not allowed"
        raise UserInputError(msg)


def yakuman(db_path: Path, year: int, month: int, now: datetime) -> int:
    validate_yakuman_log_date(year, month, now)
    return 0
