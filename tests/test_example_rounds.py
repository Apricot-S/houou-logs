# SPDX-FileCopyrightText: 2026 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "split_log_to_game_rounds",
    Path(__file__).resolve().parents[1]
    / "examples"
    / "split_log_to_game_rounds.py",
)
assert _SPEC is not None
assert _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
split_log_to_game_rounds = _MODULE.split_log_to_game_rounds


def test_preamble_does_not_create_round() -> None:
    xml = (
        '<mjloggm><UN n0="name"/><BYE who="1"/><GO/><SHUFFLE/>'
        '<TAIKYOKU/><INIT shuffle="legacy" seed="0"/>'
        '<AGARI owari="0"/><UN/><BYE/></mjloggm>'
    )
    assert split_log_to_game_rounds(xml) == [
        ['<INIT seed="0" />', '<AGARI owari="0" />'],
    ]


def test_round_boundaries_preserve_double_ron_and_connections() -> None:
    xml = (
        "<mjloggm><INIT/><T0/><UN/><BYE/><AGARI/><AGARI/>"
        '<UN/><INIT/><RYUUKYOKU/><INIT/><RYUUKYOKU owari="0"/>'
        "</mjloggm>"
    )
    assert split_log_to_game_rounds(xml) == [
        [
            "<INIT />",
            "<T0 />",
            "<UN />",
            "<BYE />",
            "<AGARI />",
            "<AGARI />",
            "<UN />",
        ],
        ["<INIT />", "<RYUUKYOKU />"],
        ["<INIT />", '<RYUUKYOKU owari="0" />'],
    ]


@pytest.mark.parametrize(
    "event",
    [
        "<T0/>",
        "<D0/>",
        '<AGARI owari="0"/>',
        '<RYUUKYOKU owari="0"/>',
        "<unknown/>",
    ],
)
def test_round_event_before_init_is_rejected(event: str) -> None:
    with pytest.raises(ValueError, match="before first INIT"):
        split_log_to_game_rounds(f"<mjloggm><UN/>{event}</mjloggm>")


@pytest.mark.parametrize("events", ["", "<UN/><BYE/>", "<INIT/><AGARI/>"])
def test_missing_game_end_is_rejected(events: str) -> None:
    with pytest.raises(ValueError, match="without 'owari'"):
        split_log_to_game_rounds(f"<mjloggm>{events}</mjloggm>")


@pytest.mark.parametrize("event", ["<INIT/>", "<GO/>", "<AGARI/>"])
def test_event_after_game_end_is_rejected(event: str) -> None:
    with pytest.raises(ValueError, match="after game end"):
        split_log_to_game_rounds(
            f'<mjloggm><INIT/><AGARI owari="0"/><UN/>{event}</mjloggm>',
        )


def test_double_ron_ending_game_stays_in_final_round() -> None:
    first_agari = (
        '<AGARI ba="0,1" '
        'hai="14,16,22,25,26,27,32,34,47,51,52,98,101,105" '
        'machi="27" ten="40,12000,2" yaku="1,1,52,3,54,2,53,0" '
        'doraHai="21" doraHaiUra="115" who="0" fromWho="3" '
        'sc="408,130,263,0,374,0,145,-120" />'
    )
    final_agari = (
        '<AGARI ba="0,0" hai="19,23,27,40,42,60,66,68,128,129,130" '
        'm="2089" machi="27" ten="30,2000,0" yaku="19,1,52,1" '
        'doraHai="21" who="2" fromWho="3" '
        'sc="538,0,263,0,374,20,25,-20" '
        'owari="538,74.0,263,-4.0,394,29.0,5,-99.0" />'
    )
    xml = (
        "<mjloggm><INIT/><RYUUKYOKU/><INIT/>"
        '<REACH who="3" step="1"/><G27/>'
        f"{first_agari}{final_agari}</mjloggm>"
    )

    assert split_log_to_game_rounds(xml) == [
        ["<INIT />", "<RYUUKYOKU />"],
        [
            "<INIT />",
            '<REACH who="3" step="1" />',
            "<G27 />",
            first_agari,
            final_agari,
        ],
    ]


def test_invalid_root_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid root tag"):
        split_log_to_game_rounds('<other><INIT/><AGARI owari="0"/></other>')
