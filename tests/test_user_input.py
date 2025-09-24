# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import pytest

from houou_logs.user_input import UserInputError, validate_offset


@pytest.mark.parametrize("offset", [0, 1])
def test_validate_offset_accepts_valid_offset(offset: int) -> None:
    validate_offset(offset)


def test_validate_offset_rejects_out_of_range() -> None:
    with pytest.raises(UserInputError):
        validate_offset(-1)
