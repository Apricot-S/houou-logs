# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs


class UserInputError(Exception):
    """Raised when arguments are invalid or out of allowed range."""


class ExternalResponseParseError(Exception):
    """The server response does not match the expected data format."""


class LogFetchError(RuntimeError):
    """The server response does not contain a downloadable log."""


class InvalidLogContentError(ValueError):
    """The XML log does not satisfy the expected log structure."""
