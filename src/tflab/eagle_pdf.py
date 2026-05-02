#!/usr/bin/env python3
# Copyright (C) 2016-2026 S.J. Leary
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://www.gnu.org/licenses/>.

"""
Generate PDF from Eagle schematic files without requiring Eagle to be installed.
Uses eagle2svg to convert .sch to SVG, then svg2rlg/reportlab to convert to PDF.
Generates a multi-page PDF with one page per schematic sheet.
"""

import sys
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def check_dependencies():
    """Check if required Python packages are installed."""
    try:
        import eagle2svg
    except ImportError:
        print("Error: eagle2svg not installed. Install with: pip install eagle2svg")
        sys.exit(1)

    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPDF
    except ImportError:
        print("Error: svglib or reportlab not installed. Install with: pip install svglib reportlab")
        sys.exit(1)


def count_sheets(sch_file):
    """Count the number of sheets in an Eagle schematic file."""
    try:
        tree = ET.parse(sch_file)
        root = tree.getroot()
        # Count <sheet> elements in the schematic
        sheets = root.findall('.//sheets/sheet')
        return len(sheets)
    except Exception as e:
        print(f"Warning: Could not count sheets in {sch_file}: {e}")
        return 1  # Default to 1 sheet


def eagle_to_svg(sch_file, svg_file, sheet=1):
    """Convert Eagle schematic to SVG using eagle2svg.

    Args:
        sch_file: Path to Eagle schematic file
        svg_file: Output SVG file path
        sheet: Sheet number (1-indexed, will be converted to 0-indexed for eagle2svg)
    """
    try:
        # Find eagle2svg executable in the same venv as this script
        venv_dir = Path(sys.executable).parent
        eagle2svg_bin = venv_dir / "eagle2svg"

        if not eagle2svg_bin.exists():
            # Fall back to searching in PATH
            eagle2svg_bin = "eagle2svg"

        # eagle2svg uses 0-based indexing, so subtract 1
        sheet_index = sheet - 1
        cmd = [str(eagle2svg_bin), sch_file, str(sheet_index)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # eagle2svg writes to stdout
        with open(svg_file, 'w') as f:
            f.write(result.stdout)

        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting to SVG: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"Error converting to SVG: {e}")
        import traceback
        traceback.print_exc()
        return False


def svg_to_pdf(svg_file, pdf_file):
    """Convert SVG to PDF using svglib and reportlab."""
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPDF

        drawing = svg2rlg(svg_file)
        if drawing is None:
            print(f"Error: Could not load SVG file {svg_file}")
            return False

        renderPDF.drawToFile(drawing, pdf_file)
        return True
    except Exception as e:
        print(f"Error converting SVG to PDF: {e}")
        return False


def combine_pdfs(pdf_files, output_pdf):
    """Combine multiple PDF files into a single multi-page PDF."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from PyPDF2 import PdfReader, PdfWriter

        writer = PdfWriter()

        for pdf_file in pdf_files:
            reader = PdfReader(pdf_file)
            for page in reader.pages:
                writer.add_page(page)

        with open(output_pdf, 'wb') as f:
            writer.write(f)

        return True
    except ImportError:
        print("Warning: PyPDF2 not installed. Falling back to single SVG conversion.")
        # Fall back to converting all SVGs into a single PDF
        return combine_svgs_to_pdf(pdf_files, output_pdf)
    except Exception as e:
        print(f"Error combining PDFs: {e}")
        return False


def combine_svgs_to_pdf(svg_files, output_pdf):
    """Convert multiple SVG files into a single multi-page PDF."""
    try:
        from svglib.svglib import svg2rlg
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter

        # For multi-page PDF, we need to use canvas directly
        from reportlab.graphics import renderPDF
        from io import BytesIO
        import PyPDF2

        # This will fail gracefully if PyPDF2 is available
        raise ImportError("Use PyPDF2 method")

    except:
        # Simple fallback: just use the first sheet
        print("Warning: Cannot create multi-page PDF without PyPDF2")
        return False


def generate_pdf(sch_file, pdf_file, sheet=None):
    """Generate PDF from Eagle schematic file.

    Args:
        sch_file: Path to Eagle schematic file
        pdf_file: Output PDF file path
        sheet: Sheet number to render (1-indexed), or None to render all sheets
    """
    if not os.path.exists(sch_file):
        print(f"Error: Schematic file not found: {sch_file}")
        return False

    # Count sheets in schematic
    num_sheets = count_sheets(sch_file)
    print(f"Found {num_sheets} sheet(s) in schematic")

    # If specific sheet requested, generate just that one
    if sheet is not None:
        if sheet < 1 or sheet > num_sheets:
            print(f"Error: Sheet {sheet} out of range (1-{num_sheets})")
            return False

        # Create temporary SVG file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as tmp_svg:
            svg_file = tmp_svg.name

        try:
            print(f"Converting sheet {sheet} to SVG...")
            if not eagle_to_svg(sch_file, svg_file, sheet):
                return False

            print(f"Converting SVG to PDF: {pdf_file}...")
            if not svg_to_pdf(svg_file, pdf_file):
                return False

            print(f"Successfully generated: {pdf_file}")
            return True
        finally:
            if os.path.exists(svg_file):
                os.remove(svg_file)

    # Generate all sheets and combine into multi-page PDF
    temp_pdfs = []
    temp_svgs = []

    try:
        print(f"Generating multi-page PDF with {num_sheets} sheets...")

        # Generate SVG and PDF for each sheet
        for sheet_num in range(1, num_sheets + 1):
            print(f"  Processing sheet {sheet_num}/{num_sheets}...")

            # Create temporary SVG file
            tmp_svg = tempfile.NamedTemporaryFile(mode='w', suffix=f'_sheet{sheet_num}.svg', delete=False)
            svg_file = tmp_svg.name
            tmp_svg.close()
            temp_svgs.append(svg_file)

            # Convert to SVG
            if not eagle_to_svg(sch_file, svg_file, sheet_num):
                print(f"  Failed to generate SVG for sheet {sheet_num}")
                return False

            # Create temporary PDF file
            tmp_pdf = tempfile.NamedTemporaryFile(mode='wb', suffix=f'_sheet{sheet_num}.pdf', delete=False)
            pdf_temp = tmp_pdf.name
            tmp_pdf.close()
            temp_pdfs.append(pdf_temp)

            # Convert SVG to PDF
            if not svg_to_pdf(svg_file, pdf_temp):
                print(f"  Failed to generate PDF for sheet {sheet_num}")
                return False

        # Combine all PDFs into one
        print(f"Combining {len(temp_pdfs)} pages into {pdf_file}...")
        if not combine_pdfs(temp_pdfs, pdf_file):
            print("Failed to combine PDFs")
            return False

        print(f"Successfully generated multi-page PDF: {pdf_file}")
        return True

    finally:
        # Clean up temporary files
        for temp_file in temp_svgs + temp_pdfs:
            if os.path.exists(temp_file):
                os.remove(temp_file)


def main():
    if len(sys.argv) < 3:
        print("Usage: generate_schematic_pdf.py <input.sch> <output.pdf> [sheet_number]")
        print("  sheet_number: schematic sheet to render (default: all sheets)")
        print("                use a number (1, 2, 3...) to render a specific sheet")
        sys.exit(1)

    check_dependencies()

    sch_file = sys.argv[1]
    pdf_file = sys.argv[2]
    sheet = int(sys.argv[3]) if len(sys.argv) > 3 else None  # None = all sheets

    if generate_pdf(sch_file, pdf_file, sheet):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
