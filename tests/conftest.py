# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from pathlib import Path

import pytest


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"
