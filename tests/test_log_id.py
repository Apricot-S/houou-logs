# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from pathlib import Path

from houou_logs.log_id import extract_log_entries


def test_extract_log_entries_skips_extension_log(tmp_path: Path) -> None:
    filename = "not_html.log"
    fake_file = tmp_path / filename
    fake_file.write_bytes(b"not a html")

    with fake_file.open(mode="br") as f:
        entries = extract_log_entries(filename, f)

    assert entries == []
