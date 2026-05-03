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
HP 1660 series logic analyser -> VCD file converter.

Works for STATE and TIMING acquisitions; the active machine is
auto-detected via HP1660.get_machines() (override with --machine).

Usage:
    hp1661-vcd [options] [output.vcd]

Options:
    --lan HOST        Connect via TCP (default: 192.168.10.10)
    --serial PORT     Connect via serial (e.g. /dev/tty.usbserial-1440)
    --baud RATE       Serial baud rate (default: 19200)
    --gpib            Use GPIB via USBTMC
    --machine {1,2}   Machine number (default: auto)
    --save-config F   Save label config to JSON after discovery
    --load-config F   Load label config from JSON (skip discovery)
"""

import argparse
import socket
import sys
import time

from tflab.hp1660 import HP1660, SocketTransport, VisaTransport, FormatConfig, Acquisition


def _open_la(args):
    if args.gpib:
        import pyvisa
        rm = pyvisa.ResourceManager('@py')
        resources = rm.list_resources('USB?*')
        if not resources:
            print('No USBTMC devices found', file=sys.stderr); sys.exit(1)
        inst = rm.open_resource(resources[0])
        return HP1660(VisaTransport(inst)), inst
    if args.serial:
        import serial
        port = serial.Serial(args.serial, args.baud, timeout=10)
        return HP1660(port), port
    host = args.lan or '192.168.10.10'
    sock = socket.socket()
    sock.settimeout(30)
    sock.connect((host, 5025))
    return HP1660(SocketTransport(sock)), sock


def _pick_machine(la, requested):
    """Use get_machines() to find the active machine; honour --machine if
    given, else auto-pick. Exits with a clear message if invalid."""
    machines = la.get_machines()
    if not machines:
        print('no active machines (both report TYPE OFF)', file=sys.stderr)
        sys.exit(3)
    if requested is None:
        chosen = machines[0]
        if len(machines) > 1:
            others = ', '.join(str(m.machine) for m in machines)
            print(f'(multiple active machines: {others}; using {chosen.machine}; '
                  f'pass --machine to override)', file=sys.stderr)
        return chosen
    chosen = next((m for m in machines if m.machine == requested), None)
    if chosen is None:
        active = ', '.join(str(m.machine) for m in machines)
        print(f'machine {requested} is OFF; active: {active}', file=sys.stderr)
        sys.exit(3)
    return chosen


def main():
    p = argparse.ArgumentParser(description='HP 1660 -> VCD')
    p.add_argument('output', nargs='?', default='capture.vcd')
    p.add_argument('--lan', default=None, help='LAN host')
    p.add_argument('--serial', help='Serial port path')
    p.add_argument('--baud', type=int, default=19200)
    p.add_argument('--gpib', action='store_true', help='Use GPIB via USBTMC')
    p.add_argument('--machine', type=int, default=None, choices=(1, 2),
                   help='Machine number (default: auto-detected)')
    p.add_argument('--save-config', help='Save label config to JSON')
    p.add_argument('--load-config', help='Load label config from JSON')
    args = p.parse_args()

    t0 = time.time()
    la, handle = _open_la(args)

    print(la.idn(), flush=True)
    chosen = _pick_machine(la, args.machine)
    print(f"Machine {chosen.machine} ({chosen.type}) name={chosen.name!r} pods={chosen.pods}",
          flush=True)

    # Labels — STATE and TIMING are both handled by discover_labels
    # (it dispatches via acq_mode internally).
    if args.load_config:
        cfg = FormatConfig.load(args.load_config)
        labels = cfg.labels
        print(f"Loaded {len(labels)} labels from {args.load_config}", flush=True)
    else:
        print("Discovering labels...", flush=True)
        labels = la.discover_labels(chosen.machine)

    for l in labels:
        print(f"  {l.name:8s} w={l.width}", flush=True)

    if args.save_config:
        cfg = la.get_format(chosen.machine)
        cfg.save(args.save_config)
        print(f"Saved config to {args.save_config}", flush=True)

    # Data download — :SYSTEM:DATA? returns the same binary block format
    # for STATE and TIMING. The block contains data for whatever pods are
    # assigned; machine-specific extraction is driven by per-machine
    # labels (label.pod_masks indexes into the row's pods list).
    print("Downloading data...", flush=True)
    la.cmd(':SYSTEM:DATA?')
    data = la.read_block()
    parsed = la._parse_data(data)
    parsed['labels'] = labels
    parsed['mode'] = chosen.type
    acq = Acquisition(**parsed)
    print(f"  {len(acq.rows)} rows @ {acq.sample_period_ps}ps trigger@{acq.trigger_row}",
          flush=True)

    acq.to_vcd(args.output)

    try:
        handle.close()
    except Exception:
        pass

    print(f"Done in {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
