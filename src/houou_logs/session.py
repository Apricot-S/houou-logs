# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from time import monotonic, sleep
from typing import override

import niquests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0",  # noqa: E501
}

TIMEOUT = (
    5.0,  # connect timeout
    5.0,  # read timeout
)

MIN_REQUEST_INTERVAL_SECONDS = 1.0


class TenhouSession(niquests.Session):
    def __init__(self) -> None:
        super().__init__(headers=HEADERS)
        self._last_request_started_at: float | None = None

    @override
    def request(
        self,
        method: str,
        url: str,
        *args,
        **kwargs,
    ) -> niquests.Response:
        if self._last_request_started_at is not None:
            now = monotonic()
            elapsed = now - self._last_request_started_at
            remaining = MIN_REQUEST_INTERVAL_SECONDS - elapsed
            if remaining > 0:
                sleep(remaining)

        self._last_request_started_at = monotonic()
        return super().request(method, url, *args, **kwargs)


def create_session() -> niquests.Session:
    return TenhouSession()
