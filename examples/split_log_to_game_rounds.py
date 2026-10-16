# SPDX-FileCopyrightText: 2026 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

"""Split local mjlog XML into rounds."""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def split_log_to_game_rounds(log_content: str) -> list[list[str]]:
    root = ET.fromstring(log_content)  # noqa: S314
    if root.tag != "mjloggm":
        msg = "invalid root tag, expected <mjloggm>"
        raise ValueError(msg)

    rounds: list[list[str]] = []
    current_round: list[str] = []
    game_ended = False

    for elem in root:
        tagname = elem.tag

        if game_ended:
            # After game end, only connection-related tags (UN/BYE)
            # are allowed.
            if tagname not in ("UN", "BYE"):
                msg = f"unexpected element <{tagname}> after game end"
                raise ValueError(msg)
            continue

        if tagname in ("SHUFFLE", "TAIKYOKU", "GO"):
            # Skip tags that are not part of round content
            continue

        if tagname == "INIT":
            # A new round starts at INIT.
            if current_round:
                # If there is an ongoing round, close it first.
                rounds.append(current_round)
                current_round = []

            # Remove legacy 'shuffle' attribute if present
            elem.attrib.pop("shuffle", None)

        elif not current_round:
            if tagname in ("UN", "BYE"):
                # Before the first INIT, participant and connection
                # information does not belong to a round.
                continue
            msg = f"unexpected element <{tagname}> before first INIT"
            raise ValueError(msg)

        if tagname in ("AGARI", "RYUUKYOKU") and "owari" in elem.attrib:
            # Game ends when 'owari' attribute is present.
            current_round.append(ET.tostring(elem, encoding="unicode"))
            rounds.append(current_round)
            current_round = []
            game_ended = True
            continue

        # Append the element to the current round
        current_round.append(ET.tostring(elem, encoding="unicode"))

    if not game_ended:
        # If no 'owari' was found, the log is incomplete
        msg = "log ended without 'owari' attribute"
        raise ValueError(msg)

    return rounds


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "xml_path",
        type=Path,
        nargs="?",
        default=Path(__file__).with_name("log.xml"),
        help="Input XML file (default: log.xml next to this script).",
    )
    args = parser.parse_args()
    try:
        content = args.xml_path.read_text(encoding="utf-8")
        rounds = split_log_to_game_rounds(content)
    except (OSError, UnicodeDecodeError, ET.ParseError, ValueError) as error:
        parser.exit(1, f"Error: {error}\n")
    print(json.dumps(rounds, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
