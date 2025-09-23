# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",  # noqa: E501
}

TIMEOUT = (
    5.0,  # connect timeout
    5.0,  # read timeout
)


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session
