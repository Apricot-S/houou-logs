# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from io import BytesIO
from typing import override
from unittest.mock import Mock

import niquests
import pytest
from niquests.adapters import BaseAdapter

from houou_logs import session as session_module
from houou_logs.session import create_session


def test_create_session() -> None:
    session = create_session()
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36 Edg/155.0.0.0"  # noqa: E501
    assert session.headers["User-Agent"] == user_agent
    session.close()


def test_first_request_is_not_delayed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_send = Mock()
    mock_sleep = Mock()
    monkeypatch.setattr(
        session_module.niquests.Session,
        "send",
        mock_send,
    )
    monkeypatch.setattr(session_module, "monotonic", Mock(return_value=10.0))
    monkeypatch.setattr(session_module, "sleep", mock_sleep)

    with create_session() as session:
        session.get("https://example.com/first")

    mock_sleep.assert_not_called()
    mock_send.assert_called_once()


def test_second_request_is_delayed_until_one_second_after_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_send = Mock()
    mock_sleep = Mock()
    mock_monotonic = Mock(side_effect=[10.0, 10.2, 11.0])
    monkeypatch.setattr(
        session_module.niquests.Session,
        "send",
        mock_send,
    )
    monkeypatch.setattr(session_module, "monotonic", mock_monotonic)
    monkeypatch.setattr(session_module, "sleep", mock_sleep)

    with create_session() as session:
        session.get("https://example.com/first")
        session.get("https://example.com/second")

    mock_sleep.assert_called_once_with(pytest.approx(0.8))
    assert mock_send.call_count == 2


def test_second_request_is_not_delayed_after_one_second(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_send = Mock()
    mock_sleep = Mock()
    mock_monotonic = Mock(side_effect=[10.0, 11.0, 11.0])
    monkeypatch.setattr(
        session_module.niquests.Session,
        "send",
        mock_send,
    )
    monkeypatch.setattr(session_module, "monotonic", mock_monotonic)
    monkeypatch.setattr(session_module, "sleep", mock_sleep)

    with create_session() as session:
        session.get("https://example.com/first")
        session.get("https://example.com/second")

    mock_sleep.assert_not_called()
    assert mock_send.call_count == 2


def test_failed_request_still_limits_next_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_send = Mock(side_effect=[OSError("failed"), Mock()])
    mock_sleep = Mock()
    mock_monotonic = Mock(side_effect=[10.0, 10.25, 11.0])
    monkeypatch.setattr(
        session_module.niquests.Session,
        "send",
        mock_send,
    )
    monkeypatch.setattr(session_module, "monotonic", mock_monotonic)
    monkeypatch.setattr(session_module, "sleep", mock_sleep)

    with create_session() as session:
        with pytest.raises(OSError, match="failed"):
            session.get("https://example.com/first")
        session.get("https://example.com/second")

    mock_sleep.assert_called_once_with(0.75)
    assert mock_send.call_count == 2


def test_request_limit_is_independent_between_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_send = Mock()
    mock_sleep = Mock()
    monkeypatch.setattr(
        session_module.niquests.Session,
        "send",
        mock_send,
    )
    monkeypatch.setattr(session_module, "monotonic", Mock(return_value=10.0))
    monkeypatch.setattr(session_module, "sleep", mock_sleep)

    with create_session() as first_session, create_session() as second_session:
        first_session.get("https://example.com/first")
        second_session.get("https://example.com/second")

    mock_sleep.assert_not_called()
    assert mock_send.call_count == 2


@pytest.mark.parametrize("redirect_count", [1, 3])
def test_redirects_respect_request_interval(
    monkeypatch: pytest.MonkeyPatch,
    redirect_count: int,
) -> None:
    now = 10.0
    sent_at: list[float] = []

    def advance_time(seconds: float) -> None:
        nonlocal now
        now += seconds

    class RedirectAdapter(BaseAdapter):
        @override
        def send(
            self,
            request: niquests.PreparedRequest,
            *args,
            **kwargs,
        ) -> niquests.Response:
            sent_at.append(now)
            response = niquests.Response()
            response.request = request
            response.url = request.url
            response.raw = BytesIO(b"")
            response.status_code = 200
            if len(sent_at) <= redirect_count:
                response.status_code = 302
                response.headers["Location"] = f"/redirect/{len(sent_at)}"
            return response

        @override
        def close(self) -> None:
            pass

    mock_sleep = Mock(side_effect=advance_time)
    monkeypatch.setattr(session_module, "monotonic", lambda: now)
    monkeypatch.setattr(session_module, "sleep", mock_sleep)

    with create_session() as session:
        session.mount("https://", RedirectAdapter())
        response = session.get("https://example.com/start")

    assert response.status_code == 200
    assert len(response.history) == redirect_count
    interval = session_module.MIN_REQUEST_INTERVAL_SECONDS
    assert sent_at == [10.0 + interval * i for i in range(redirect_count + 1)]
    assert mock_sleep.call_count == redirect_count
