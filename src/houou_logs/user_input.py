# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs


class UserInputError(Exception):
    """Raised when arguments are invalid or out of allowed range."""


def validate_offset(offset: int) -> None:
    if offset < 0:
        msg = f"invalid offset of export: {offset}"
        raise UserInputError(msg)
