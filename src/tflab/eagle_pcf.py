#!/usr/bin/env python3
"""
Generate PCF (Physical Constraints File) from Eagle netlist.
Converts netlist format to FPGA pin constraint format.
"""

import sys
import re
from pathlib import Path

pcfheader = """# Copyright (C) 2020-2022, Stephen J. Leary
# All rights reserved.
#
# This file is part of TF4060 (Terrible Fire 060 Accelerator)
#
# TF4060 is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# TF4060 is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with TF4060. If not, see <http://www.gnu.org/licenses/>.

"""


def generate_pcf(netlist_file, output_file, target_chip):
    """Generate PCF file from netlist for specified target chip."""

    currentNet = None

    exclude = ["GND", "VCC33", "VCC12", "CRESET_B", "CDONE", "SS", "SDO", "SDI", "SCK"]
    busre = re.compile(r'(\d+$)')
    notbus = ["IRQ2", "IACK2", "IRQ4", "IACK4"]

    bad_pins = ['5', '6', '13', '14', '27', '30', '35', '36', '40', '46', '50', '51', '53', '54',
                '57', '58', '59', '72', '77', '86', '89', '92', '100', '103', '108', '109', '111',
                '123', '126', '127', '131', '132', '133', '140']

    errors = []
    translate = {'AA': 'A', '_D': 'D', '_R!W': 'RW'}

    pcf_output = ""

    with open(netlist_file) as f:
        content = f.readlines()
        for line in content:
            tokens = line.split()
            if len(tokens) == 0:
                continue

            # Skip header lines
            if tokens[0] in ['Netlist', 'Exported', 'EAGLE', 'Net']:
                continue

            # Netlist format:
            # First line of net: Net Part Pad Pin Sheet (5 tokens)
            # Continuation lines:     Part Pad Pin Sheet (4 tokens)
            if len(tokens) == 5:
                currentNet = tokens[0].replace("/", "")
                chip = tokens[1]
                pad = tokens[2]
            elif len(tokens) == 4:
                chip = tokens[0]
                pad = tokens[1]
            else:
                continue

            if (currentNet is not None) and currentNet not in exclude:
                if chip == target_chip:
                    if currentNet in notbus:
                        netname = currentNet
                    else:
                        netname = busre.sub(r'[\1]', currentNet)
                        items = netname.split('[')
                        if items[0] in translate.keys():
                            items[0] = translate[items[0]]
                        netname = '['.join(items)

                    if pad in bad_pins:
                        errors.append((chip, "Bad PIN for device: %s %s" % (netname, pad)))
                        continue

                    pcf_output += 'set_io --warn-no-port %s %s\n' % (netname, pad)

    if errors:
        print("Errors found:")
        for error in errors:
            print("  ERROR:", error[0], error[1])
        sys.exit(1)

    # Write output file
    with open(output_file, 'w') as f:
        f.write(pcfheader)
        f.write(pcf_output)

    print(f"PCF written to {output_file}")


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <input.net> <output.pcf> <target_chip>")
        sys.exit(1)

    netlist_file = sys.argv[1]
    output_file = sys.argv[2]
    target_chip = sys.argv[3]

    if not Path(netlist_file).exists():
        print(f"Error: Input file '{netlist_file}' not found")
        sys.exit(1)

    print(f"Generating PCF for {target_chip} from {netlist_file}...")
    generate_pcf(netlist_file, output_file, target_chip)


if __name__ == '__main__':
    main()
