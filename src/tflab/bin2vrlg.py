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
import math
import os
import sys

HEADER = """module bootrom
(
        input\t\tclk,\t// bus clock
        input [%i:0]\taddress,\t// address in
        output reg [7:0]\tdata\t// data out
);

always @(posedge clk) begin
\tcase (address)
"""

FOOTER = """\tendcase
end

endmodule"""


def main():
    parser = argparse.ArgumentParser(description="Convert a binary file to a Verilog bootrom module.")
    parser.add_argument("-f", "--filename", required=True)
    args = parser.parse_args()

    size = os.path.getsize(args.filename)
    if size <= 0:
        sys.stderr.write(f"ERROR: empty or missing file: {args.filename}\n")
        return 1

    addrw = max(1, int(math.ceil(math.log(size, 2))))
    out = [HEADER % (addrw - 1,)]
    default = 0

    with open(args.filename, "rb") as f:
        for loc, b in enumerate(iter(lambda: f.read(1), b"")):
            value = b[0]
            if value != default:
                out.append("\t\t%i'd%d:\tdata\t<=\t8'h%02x;\n" % (addrw, loc, value))

    out.append("\t\tdefault:\tdata\t<=\t8'd0;\n")
    out.append(FOOTER)
    print("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
