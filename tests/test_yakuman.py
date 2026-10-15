# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from houou_logs import db
from houou_logs import yakuman as yakuman_module
from houou_logs.db import LogEntry
from houou_logs.exceptions import ExternalResponseParseError, UserInputError
from houou_logs.yakuman import (
    build_url,
    iter_entries,
    iter_ids,
    parse_id,
    validate_yakuman_log_date,
)


@pytest.mark.parametrize("year", [-1, 0, 10000, 10001])
def test_validate_yakuman_log_date_year_out_of_range(year: int) -> None:
    fixed_now = datetime(2025, 9, 15, tzinfo=UTC)
    with pytest.raises(
        UserInputError,
        match="year must be between 1 and 9999",
    ):
        validate_yakuman_log_date(year, 1, fixed_now)


def test_validate_yakuman_log_date_min_year_before_available_from() -> None:
    fixed_now = datetime(2025, 9, 15, tzinfo=UTC)
    with pytest.raises(
        UserInputError,
        match="available starting from 2006/10",
    ):
        validate_yakuman_log_date(1, 1, fixed_now)


def test_validate_yakuman_log_date_max_year_is_future() -> None:
    fixed_now = datetime(2025, 9, 15, tzinfo=UTC)
    with pytest.raises(UserInputError, match="future dates are not allowed"):
        validate_yakuman_log_date(9999, 1, fixed_now)


def test_validate_yakuman_log_date_max_year_is_valid() -> None:
    fixed_now = datetime(9999, 12, 31, tzinfo=UTC)
    validate_yakuman_log_date(9999, 12, fixed_now)


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


def test_iter_ids_new_format() -> None:
    text = """total=580570;
updated="2025/02/01 00:12";
ykm=['01/31 23:57','etra','[1,[12,14,15,116,118],[50794,47721,49674],12]',[39],'2025013123gm-0001-0000-12b924e3&tw=2&ts=4','01/31 23:40','åŽŸçˆ†','[137,[24,25,26,28,30,31,60,61,63,73,74,75,109,110],[],109]',[41],'2025013123gm-0089-0000-a148333d&tw=1&ts=9'];
sw();
"""  # noqa: E501
    ids = [
        ("01/31 23:57", "2025013123gm-0001-0000-12b924e3"),
        ("01/31 23:40", "2025013123gm-0089-0000-a148333d"),
    ]
    assert list(iter_ids(text)) == ids


def test_iter_ids_new_format_empty() -> None:
    text = """total=580570;
updated="2025/02/01 00:12";
ykm=[];
sw();
"""
    assert list(iter_ids(text)) == []


def test_iter_ids_new_format_raises_error_when_ykm_not_found() -> None:
    text = """total=580570;
updated="2025/02/01 00:12";
['01/31 23:57','etra','[1,[12,14,15,116,118],[50794,47721,49674],12]',[39],'2025013123gm-0001-0000-12b924e3&tw=2&ts=4','01/31 23:40','åŽŸçˆ†','[137,[24,25,26,28,30,31,60,61,63,73,74,75,109,110],[],109]',[41],'2025013123gm-0089-0000-a148333d&tw=1&ts=9'];
sw();
"""  # noqa: E501

    with pytest.raises(ExternalResponseParseError):
        list(iter_ids(text))


def test_iter_ids_raises_error_when_ykm_is_malformed() -> None:
    text = """total=580570;
updated="2025/02/01 00:12";
ykm=[foo];
sw();
"""

    with pytest.raises(
        ExternalResponseParseError,
        match="failed to parse ykm array",
    ):
        list(iter_ids(text))


def test_iter_ids_new_format_rejects_invalid_length() -> None:
    text = """total=580570;
updated="2025/02/01 00:12";
ykm=['01/31 23:57','etra'];
sw();
"""

    with pytest.raises(
        ExternalResponseParseError,
        match="invalid new ykm array length",
    ):
        list(iter_ids(text))


def test_iter_ids_new_format_rejects_invalid_entry() -> None:
    text = """total=580570;
updated="2025/02/01 00:12";
ykm=['01/31 23:57','etra','[1]',[39],123];
sw();
"""

    with pytest.raises(
        ExternalResponseParseError,
        match="invalid new ykm array entry",
    ):
        list(iter_ids(text))


def test_iter_ids_old_format() -> None:
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
    assert list(iter_ids(text)) == ids


def test_iter_ids_old_format_rejects_invalid_entry() -> None:
    text = """total=451693;
updated="2008/02/01 01:17";
ykm=[
['01/31 23:58','りょぬの']
,['01/31 23:52','mej2',[9,[20,22,23,56,58,59,65,66,67,81,83],[24064],59],[40],'2008013123gm-0009-0000-5ab263c2',1,5]
];
sw();
"""  # noqa: E501

    with pytest.raises(ExternalResponseParseError, match="invalid old ykm"):
        list(iter_ids(text))


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


def test_parse_id_accepts_legacy_yakuman_log_id_without_hour() -> None:
    year = 2007
    date = "04/16 08:15"
    log_id = "20070416gm-0041-0000-56a0738f"
    entry = LogEntry(
        log_id,
        "2007-04-16T08:15",
        4,
        is_tonpu=True,
        is_processed=False,
        was_error=False,
        log=None,
    )

    assert parse_id(year, date, log_id) == entry


@pytest.mark.parametrize(
    ("year", "date", "prefix"),
    [
        (2025, "02/31 99:99", "2025023199"),
        (2025, "02/31 00:00", "2025023100"),
        (2025, "00/01 00:00", "2025000100"),
        (2025, "13/01 00:00", "2025130100"),
        (2025, "01/00 00:00", "2025010000"),
        (2025, "01/01 24:00", "2025010124"),
        (2025, "01/01 99:99", "2025010199"),
        (2025, "01/01 23:60", "2025010123"),
        (2025, "02/29 00:00", "2025022900"),
        (1900, "02/29 00:00", "1900022900"),
        (2025, "01/01 00:00", "2025010124"),
        (2025, "02/31 00:00", "20250231"),
        (0, "01/01 00:00", "0000010100"),
    ],
)
def test_parse_id_rejects_invalid_datetime(
    year: int,
    date: str,
    prefix: str,
) -> None:
    with pytest.raises(ExternalResponseParseError, match="invalid log date"):
        parse_id(year, date, f"{prefix}gm-0001-0000-12345678")


@pytest.mark.parametrize("prefix", ["2024022923", "20240229"])
def test_parse_id_accepts_leap_day(prefix: str) -> None:
    entry = parse_id(2024, "02/29 23:59", f"{prefix}gm-0001-0000-12345678")
    assert entry.date == "2024-02-29T23:59"


@pytest.mark.parametrize("prefix", ["2024010123", "2025010223", "20250102"])
def test_parse_id_rejects_mismatched_date(prefix: str) -> None:
    with pytest.raises(ExternalResponseParseError, match="does not match"):
        parse_id(2025, "01/01 23:59", f"{prefix}gm-0001-0000-12345678")


def test_iter_entries_skips_invalid_datetime(
    capsys: pytest.CaptureFixture[str],
) -> None:
    ids = [
        ("02/31 99:99", "2025023199gm-0001-0000-12345678"),
        ("01/01 23:59", "2025010223gm-0001-0000-12345678"),
        ("01/01 23:59", "20250101gm-0001-0000-12345678"),
    ]
    entries = list(iter_entries(2025, ids))
    assert [entry.date for entry in entries] == ["2025-01-01T23:59"]
    output = capsys.readouterr().out
    assert "invalid log date" in output
    assert "does not match" in output


def test_parse_id_rejects_invalid_yakuman_log_id() -> None:
    with pytest.raises(
        ExternalResponseParseError,
        match="invalid yakuman log ID: invalid",
    ):
        parse_id(2007, "04/16 08:15", "invalid")


def test_parse_id_rejects_invalid_yakuman_log_date() -> None:
    with pytest.raises(
        ExternalResponseParseError,
        match="invalid yakuman log date: invalid",
    ):
        parse_id(2007, "invalid", "2007041610gm-00c1-0000-75574173")


def test_iter_entries_skips_invalid_yakuman_log_id() -> None:
    ids = [
        ("04/16 08:15", "invalid"),
        ("04/16 10:27", "2007041610gm-00c1-0000-75574173"),
    ]

    assert list(iter_entries(2007, iter(ids))) == [
        parse_id(2007, "04/16 10:27", "2007041610gm-00c1-0000-75574173"),
    ]


@pytest.mark.parametrize("failure", [False, True])
def test_yakuman_iterator_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    failure: bool,
) -> None:
    path = tmp_path / "yakuman.db"
    existing_id = "2025010100gm-00a9-0000-00000000"
    new_id = "2025010101gm-00a9-0000-00000000"
    with closing(db.open_db(path)) as conn, conn:
        db.setup_table(conn)
        db.insert_log_entries(
            conn.cursor(),
            [
                parse_id(2025, "01/01 00:00", existing_id),
            ],
        )
    array: list = ["01/01 00:00", "name", "data", [], new_id] * 2
    array += [
        "01/01 00:00",
        "name",
        "data",
        [],
        123 if failure else existing_id,
    ]
    monkeypatch.setattr(yakuman_module, "create_session", MagicMock())
    monkeypatch.setattr(
        yakuman_module,
        "fetch_yakuman_log_ids_text",
        Mock(
            return_value=f"ykm={array!r};",
        ),
    )
    # Verify a valid entry is yielded before the later structural error.
    ids = iter_ids(f"ykm={array!r};")
    assert next(ids) == ("01/01 00:00", new_id)
    now = datetime(2025, 2, 1, tzinfo=UTC)
    if failure:
        with pytest.raises(
            ExternalResponseParseError,
            match="invalid new ykm array entry",
        ):
            yakuman_module.yakuman(path, 2025, 1, now)
    else:
        assert yakuman_module.yakuman(path, 2025, 1, now) == 1
    with closing(db.open_db(path)) as conn:
        actual = {row[0] for row in conn.execute("SELECT id FROM logs")}
        assert actual == ({existing_id} if failure else {existing_id, new_id})
