# Copyright (C) 2016-2026 S.J. Leary
# Released under GPL-2.0-or-later — see LICENSE in the repo root.
"""
Smoke test: eagle-pdf must turn tf536.sch into a valid multi-page PDF
with one page per schematic sheet.
"""

import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest


pypdf = pytest.importorskip("pypdf", reason="pypdf required to validate PDF output")


def _count_sheets(sch_path):
    return len(ET.parse(sch_path).getroot().findall(".//sheets/sheet"))


def test_eagle_pdf_produces_valid_multipage_pdf(tf536_sch, tmp_path):
    out = tmp_path / "tf536.pdf"
    sheets = _count_sheets(tf536_sch)
    assert sheets > 1, "TF536 fixture should be multi-sheet"

    result = subprocess.run(
        [sys.executable, "-m", "tflab.eagle_pdf", str(tf536_sch), str(out)],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, (
        f"eagle-pdf failed (exit {result.returncode})\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert out.exists() and out.stat().st_size > 0, "no PDF was written"

    header = out.read_bytes()[:4]
    assert header == b"%PDF", f"output is not a PDF (header: {header!r})"

    reader = pypdf.PdfReader(str(out))
    assert len(reader.pages) == sheets, (
        f"expected {sheets} pages (one per schematic sheet), "
        f"got {len(reader.pages)}"
    )
