# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from unittest.mock import Mock

import pytest

from houou_logs import session as session_module
from houou_logs.session import create_session


def test_create_session() -> None:
    session = create_session()
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"  # noqa: E501
    assert session.headers["User-Agent"] == user_agent
    session.close()


def test_first_request_is_not_delayed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_request = Mock()
    mock_sleep = Mock()
    monkeypatch.setattr(
        session_module.niquests.Session,
        "request",
        mock_request,
    )
    monkeypatch.setattr(session_module, "monotonic", Mock(return_value=10.0))
    monkeypatch.setattr(session_module, "sleep", mock_sleep)

    with create_session() as session:
        session.get("https://example.com/first")

    mock_sleep.assert_not_called()
    mock_request.assert_called_once()


def test_second_request_is_delayed_until_one_second_after_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_request = Mock()
    mock_sleep = Mock()
    mock_monotonic = Mock(side_effect=[10.0, 10.2, 11.0])
    monkeypatch.setattr(
        session_module.niquests.Session,
        "request",
        mock_request,
    )
    monkeypatch.setattr(session_module, "monotonic", mock_monotonic)
    monkeypatch.setattr(session_module, "sleep", mock_sleep)

    with create_session() as session:
        session.get("https://example.com/first")
        session.get("https://example.com/second")

    mock_sleep.assert_called_once_with(pytest.approx(0.8))
    assert mock_request.call_count == 2


def test_second_request_is_not_delayed_after_one_second(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_request = Mock()
    mock_sleep = Mock()
    mock_monotonic = Mock(side_effect=[10.0, 11.0, 11.0])
    monkeypatch.setattr(
        session_module.niquests.Session,
        "request",
        mock_request,
    )
    monkeypatch.setattr(session_module, "monotonic", mock_monotonic)
    monkeypatch.setattr(session_module, "sleep", mock_sleep)

    with create_session() as session:
        session.get("https://example.com/first")
        session.get("https://example.com/second")

    mock_sleep.assert_not_called()
    assert mock_request.call_count == 2


def test_failed_request_still_limits_next_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_request = Mock(side_effect=[OSError("failed"), Mock()])
    mock_sleep = Mock()
    mock_monotonic = Mock(side_effect=[10.0, 10.25, 11.0])
    monkeypatch.setattr(
        session_module.niquests.Session,
        "request",
        mock_request,
    )
    monkeypatch.setattr(session_module, "monotonic", mock_monotonic)
    monkeypatch.setattr(session_module, "sleep", mock_sleep)

    with create_session() as session:
        with pytest.raises(OSError, match="failed"):
            session.get("https://example.com/first")
        session.get("https://example.com/second")

    mock_sleep.assert_called_once_with(0.75)
    assert mock_request.call_count == 2


def test_request_limit_is_independent_between_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_request = Mock()
    mock_sleep = Mock()
    monkeypatch.setattr(
        session_module.niquests.Session,
        "request",
        mock_request,
    )
    monkeypatch.setattr(session_module, "monotonic", Mock(return_value=10.0))
    monkeypatch.setattr(session_module, "sleep", mock_sleep)

    with create_session() as first_session, create_session() as second_session:
        first_session.get("https://example.com/first")
        second_session.get("https://example.com/second")

    mock_sleep.assert_not_called()
    assert mock_request.call_count == 2
