# Copyright (C) 2016-2026 S.J. Leary
# Released under GPL-2.0-or-later — see LICENSE in the repo root.
"""
Regression test: eagle-netlist on tf536.sch must reproduce the golden
Eagle-exported netlist exactly, modulo the export-time line.
"""

import re
import subprocess
import sys


_TIMESTAMP_RE = re.compile(r"^Exported from .* at .*$", re.MULTILINE)


def _normalize(text):
    return _TIMESTAMP_RE.sub("Exported from <fixture> at <timestamp>", text)


def test_eagle_netlist_matches_golden(tf536_sch, tf536_net_golden, tmp_path):
    out = tmp_path / "tf536.net"
    result = subprocess.run(
        [sys.executable, "-m", "tflab.eagle_netlist", str(tf536_sch), str(out)],
        capture_output=True,
        text=True,
    )
    # eagle-netlist's main() doesn't return non-zero for empty argv,
    # but a successful run should produce the file.
    assert out.exists(), (
        f"eagle-netlist did not produce output\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    produced = _normalize(out.read_text())
    expected = _normalize(tf536_net_golden.read_text())

    assert produced == expected, (
        "eagle-netlist output differs from golden TF536 netlist "
        "(beyond the timestamp line)."
    )
