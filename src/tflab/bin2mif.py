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

import argparse
import os.path
import sys
from struct import unpack

WIDTHS = {8: "B", 16: "H", 32: "L", 64: "Q"}


def get_endian(arg):
    a = arg.lower()
    if a in ("little", "l"):
        return "<"
    if a in ("big", "b"):
        return ">"
    sys.stderr.write('ERROR: invalid endian parameter. Values are "big","b","little" or "l"\n')
    return None


def main():
    parser = argparse.ArgumentParser(description="Convert binary file(s) to MIF-style hex output.")
    parser.add_argument("-w", "--width", default=8, type=int, choices=WIDTHS.keys(), help="Word width in bits")
    parser.add_argument("-e", "--endian", default="big", help="Endianness of the data (big/little/b/l)")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()

    endian = get_endian(args.endian)
    if endian is None:
        return 2

    width = args.width
    read_len = width // 8
    width_format = "%0" + str(read_len * 2) + "x"

    for filename in args.files:
        if not os.path.exists(filename):
            sys.stderr.write(f"ERROR: input file not found: {filename}\n")
            return 1

        with open(filename, "rb") as f:
            while True:
                chunk = f.read(read_len)
                if len(chunk) < read_len:
                    break
                n = unpack(endian + WIDTHS[width], chunk)
                print(width_format % (n[0] % (1 << width)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
