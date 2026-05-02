#!/usr/bin/env python3
# Copyright (c) 2012-2025, Stephen J. Leary
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

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
