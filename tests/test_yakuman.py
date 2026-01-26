# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from datetime import UTC, datetime

import pytest

from houou_logs.db import LogEntry
from houou_logs.exceptions import UserInputError
from houou_logs.yakuman import (
    build_url,
    extract_ids,
    parse_id,
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


def test_build_url() -> None:
    assert build_url(2025, 1) == "https://tenhou.net/sc/2025/01/ykm.js"


def test_extract_ids_new_format() -> None:
    text = """total=580570;
updated="2025/02/01 00:12";
ykm=['01/31 23:57','etra','[1,[12,14,15,116,118],[50794,47721,49674],12]',[39],'2025013123gm-0001-0000-12b924e3&tw=2&ts=4','01/31 23:40','åŽŸçˆ†','[137,[24,25,26,28,30,31,60,61,63,73,74,75,109,110],[],109]',[41],'2025013123gm-0089-0000-a148333d&tw=1&ts=9'];
sw();
"""  # noqa: E501
    ids = [
        ("01/31 23:57", "2025013123gm-0001-0000-12b924e3"),
        ("01/31 23:40", "2025013123gm-0089-0000-a148333d"),
    ]
    assert extract_ids(text) == ids


def test_extract_ids_new_format_empty() -> None:
    text = """total=580570;
updated="2025/02/01 00:12";
ykm=[];
sw();
"""
    assert extract_ids(text) == []


def test_extract_ids_new_format_raises_error_when_ykm_not_found() -> None:
    text = """total=580570;
updated="2025/02/01 00:12";
['01/31 23:57','etra','[1,[12,14,15,116,118],[50794,47721,49674],12]',[39],'2025013123gm-0001-0000-12b924e3&tw=2&ts=4','01/31 23:40','åŽŸçˆ†','[137,[24,25,26,28,30,31,60,61,63,73,74,75,109,110],[],109]',[41],'2025013123gm-0089-0000-a148333d&tw=1&ts=9'];
sw();
"""  # noqa: E501

    with pytest.raises(RuntimeError):
        extract_ids(text)


def test_extract_ids_old_format() -> None:
    text = """total=451693;

updated="2008/02/01 01:17";

ykm=[

['01/31 23:58','りょぬの',[193,[104,106,128,129,131],[48746,50730,35151],131],[39],'2008013123gm-00c1-0000-6ec331ef',1,4]

,['01/31 23:52','mej2',[9,[20,22,23,56,58,59,65,66,67,81,83],[24064],59],[40],'2008013123gm-0009-0000-5ab263c2',1,5]

];

sw();


"""  # noqa: E501
    ids = [
        ("01/31 23:58", "2008013123gm-00c1-0000-6ec331ef"),
        ("01/31 23:52", "2008013123gm-0009-0000-5ab263c2"),
    ]
    assert extract_ids(text) == ids


def test_parse_id_new_format() -> None:
    year = 2025
    date = "01/31 23:57"
    log_id = "2025013123gm-0001-0000-12b924e3"

    entry = LogEntry(
        "2025013123gm-0001-0000-12b924e3",
        "2025-01-31T23:57",
        4,
        is_tonpu=True,
        is_processed=False,
        was_error=False,
        log=None,
    )

    assert parse_id(year, date, log_id) == entry


def test_parse_id_old_format() -> None:
    year = 2006
    date = "10/31 23:58"
    log_id = "20061031gm-0001-0000-110c699e"

    entry = LogEntry(
        "20061031gm-0001-0000-110c699e",
        "2006-10-31T23:58",
        4,
        is_tonpu=True,
        is_processed=False,
        was_error=False,
        log=None,
    )

    assert parse_id(year, date, log_id) == entry
