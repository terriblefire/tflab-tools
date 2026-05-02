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
