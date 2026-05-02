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
HP 1661C Logic Analyser -> VCD file converter.

Usage:
    hp1661_vcd.py [options] [output.vcd]

Options:
    --lan HOST        Connect via TCP (default: 192.168.10.10)
    --serial PORT     Connect via serial (e.g. /dev/tty.usbserial-1440)
    --baud RATE       Serial baud rate (default: 19200)
    --save-config F   Save label config to JSON after discovery
    --load-config F   Load label config from JSON (skip discovery)
"""

import argparse
import socket
import sys
import time

from tflab.hp1660 import HP1660, SocketTransport, VisaTransport, FormatConfig, Acquisition


def main():
    p = argparse.ArgumentParser(description='HP 1661C -> VCD')
    p.add_argument('output', nargs='?', default='capture.vcd')
    p.add_argument('--lan', default=None, help='LAN host')
    p.add_argument('--serial', help='Serial port path')
    p.add_argument('--baud', type=int, default=19200)
    p.add_argument('--gpib', action='store_true', help='Use GPIB via USBTMC')
    p.add_argument('--save-config', help='Save label config to JSON')
    p.add_argument('--load-config', help='Load label config from JSON')
    args = p.parse_args()

    t0 = time.time()

    if args.gpib:
        import pyvisa
        rm = pyvisa.ResourceManager('@py')
        resources = rm.list_resources('USB?*')
        if not resources:
            print("No USBTMC devices found"); sys.exit(1)
        inst = rm.open_resource(resources[0])
        la = HP1660(VisaTransport(inst))
    elif args.serial:
        import serial
        port = serial.Serial(args.serial, args.baud, timeout=10)
        la = HP1660(port)
    else:
        host = args.lan or '192.168.10.10'
        sock = socket.socket()
        sock.settimeout(30)
        sock.connect((host, 5025))
        la = HP1660(SocketTransport(sock))

    print(la.idn(), flush=True)

    # Labels
    if args.load_config:
        cfg = FormatConfig.load(args.load_config)
        labels = cfg.labels
        print(f"Loaded {len(labels)} labels from {args.load_config}", flush=True)
    else:
        print("Discovering labels...", flush=True)
        labels = la.discover_labels()

    for l in labels:
        print(f"  {l.name:8s} w={l.width}", flush=True)

    if args.save_config:
        cfg = la.get_format()
        cfg.save(args.save_config)
        print(f"Saved config to {args.save_config}", flush=True)

    # Data
    print("Downloading data...", flush=True)
    la.cmd(':SYSTEM:DATA?')
    data = la.read_block()
    parsed = la._parse_data(data)
    parsed['labels'] = labels
    acq = Acquisition(**parsed)
    print(f"  {len(acq.rows)} rows @ {acq.sample_period_ps}ps trigger@{acq.trigger_row}", flush=True)

    acq.to_vcd(args.output)

    if args.gpib:
        inst.close()
    elif args.serial:
        port.close()
    else:
        sock.close()

    print(f"Done in {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
