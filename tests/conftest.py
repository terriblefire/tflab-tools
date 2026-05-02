# Copyright (C) 2016-2026 S.J. Leary
# Released under GPL-2.0-or-later — see LICENSE in the repo root.

from pathlib import Path

import pytest


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def tf536_sch():
    return FIXTURES / "tf536.sch"


@pytest.fixture(scope="session")
def tf536_net_golden():
    return FIXTURES / "tf536.net"
