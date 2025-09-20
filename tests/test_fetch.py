# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from datetime import UTC, datetime

import pytest

from houou_logs.fetch import should_fetch


@pytest.mark.parametrize(
    ("last_fetch_time", "expected"),
    [
        (datetime(2025, 9, 20, 10, 0, 0, 0, tzinfo=UTC), True),
        (datetime(2025, 9, 20, 10, 40, 0, 0, tzinfo=UTC), False),
        (datetime(2025, 9, 20, 10, 39, 59, 999_999, tzinfo=UTC), True),
    ],
)
def test_should_fetch(last_fetch_time: datetime, *, expected: bool) -> None:
    now = datetime(2025, 9, 20, 11, 0, 0, 0, tzinfo=UTC)
    assert should_fetch(last_fetch_time, now=now) == expected
