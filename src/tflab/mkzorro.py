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

"""Generate Zorro expansion card AutoConfig ROM nibbles for the Amiga bus.

The first two nibbles (the ER_TYPE byte) are emitted as-is; from the third
nibble onward each nibble is bit-inverted, as required by the AutoConfig
protocol.
"""

import argparse
import sys

VERSIONS = {"Z2": 0xC0, "Z3": 0x80}
SIZES = {
    "64K": 0x01, "128K": 0x02, "256K": 0x03, "512K": 0x04,
    "1M": 0x05, "2M": 0x06, "4M": 0x07, "8M": 0x00,
}


def _autoint(x):
    return int(x, 0)


class _Emitter:
    def __init__(self):
        self.address = 0

    def nybble(self, x):
        if self.address >= 2:
            x = ~x & 0xF
        print("{:X}".format(x & 0x0F))
        self.address += 1

    def byte(self, x):
        self.nybble(x >> 4)
        self.nybble(x & 0x0F)

    def short(self, x):
        self.byte(x >> 8)
        self.byte(x & 0xFF)

    def long(self, x):
        self.short(x >> 16)
        self.short(x & 0xFFFF)


def main():
    p = argparse.ArgumentParser(description="Generate Zorro card AutoConfig ROM nibbles.")
    p.add_argument("--version", choices=VERSIONS.keys(), default="Z2", help="Zorro bus version")
    p.add_argument("--size", choices=SIZES.keys(), default="64K", help="Card memory size")
    p.add_argument("--manuid", type=_autoint, default=5080, help="Manufacturer ID (decimal or 0x...)")
    p.add_argument("--serial", type=_autoint, default=4060, help="Serial number")
    p.add_argument("--product", type=_autoint, default=148, help="Product code")
    p.add_argument("--flags", type=_autoint, default=0x80, help="ER_FLAGS byte")
    p.add_argument("--rom-vector", type=_autoint, default=0, help="Diag/init ROM offset")
    args = p.parse_args()

    e_type = VERSIONS[args.version] | SIZES[args.size]

    em = _Emitter()
    em.byte(e_type)
    em.byte(args.product)
    em.byte(args.flags)
    em.byte(0x00)             # reserved
    em.short(args.manuid)
    em.long(args.serial)
    em.short(args.rom_vector)
    em.long(0x00)             # reserved
    return 0


if __name__ == "__main__":
    sys.exit(main())
