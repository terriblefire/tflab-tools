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
HP 1660 series logic analyser -> text listing.

Connects to the analyzer, downloads the current acquisition, and prints
each sample on its own line with the value of every discovered label.
Works for both STATE and TIMING acquisitions (the underlying acquire()
dispatches through SLISt or TLISt as appropriate).

Usage:
    hp1661-list [connection options] [output.txt]

Connection options (mirror hp1661-vcd):
    --lan HOST        Connect via TCP (default: 192.168.10.10)
    --serial PORT     Connect via serial (e.g. /dev/tty.usbserial-1440)
    --baud RATE       Serial baud rate (default: 19200)
    --gpib            Use GPIB via USBTMC

Listing options:
    --machine {1,2}   Machine number (default: 1)
    --base {hex,bin,dec,oct}  Number base for multi-bit labels (default: hex)
    --start N         First line relative to trigger (default: full range)
    --count N         Maximum number of lines (default: all)
    --time            Include a time column (TIMING mode acquisitions)
"""

import argparse
import socket
import sys

from tflab.hp1660 import HP1660, SocketTransport, VisaTransport


def _bits_to_int(bits):
    n = 0
    for b in bits:
        n = (n << 1) | (b & 1)
    return n


def _format_value(bits, base):
    if not bits:
        return ''
    if len(bits) == 1:
        return str(bits[0])
    if base == 'bin':
        return ''.join(str(b) for b in bits)
    n = _bits_to_int(bits)
    if base == 'dec':
        return str(n)
    if base == 'oct':
        return oct(n)[2:]
    nibbles = (len(bits) + 3) // 4
    return f'{n:0{nibbles}x}'


def _column_width(label, base):
    if label.width == 1:
        natural = 1
    elif base == 'bin':
        natural = label.width
    elif base == 'dec':
        natural = len(str((1 << label.width) - 1))
    elif base == 'oct':
        natural = len(oct((1 << label.width) - 1)) - 2
    else:  # hex
        natural = (label.width + 3) // 4
    return max(natural, len(label.name))


def _format_time(ps_signed):
    """Format a signed picosecond value as a short string with a unit."""
    sign = '-' if ps_signed < 0 else ' '
    p = abs(ps_signed)
    if p == 0:
        return '       0   '
    if p >= 1_000_000_000:
        return f'{sign}{p / 1_000_000_000:9.3f}ms'
    if p >= 1_000_000:
        return f'{sign}{p / 1_000_000:9.3f}us'
    if p >= 1_000:
        return f'{sign}{p / 1_000:9.3f}ns'
    return f'{sign}{p:9d}ps'


def _format_state_tag(line):
    """STATE-mode tag column: just the relative state count."""
    return f'{line:>11d} '


def write_listing(acq, out, base='hex', start=None, count=None,
                  with_time=False, mode=None, machine=None, name=None):
    rows = acq.rows

    # Header comment so the reader can see what they're looking at.
    if mode or machine is not None or name:
        bits = []
        if machine is not None:
            bits.append(f'machine={machine}')
        if mode:
            bits.append(f'mode={mode}')
        if name:
            bits.append(f'name={name!r}')
        bits.append(f'samples={len(rows)}')
        if rows:
            bits.append(f'trigger@{acq.trigger_row}')
        out.write('# ' + ' '.join(bits) + '\n')

    if not rows:
        out.write('(no samples)\n')
        return

    trig = acq.trigger_row
    first_line = -trig if start is None else start
    last_line = (len(rows) - 1) - trig
    if count is not None:
        last_line = min(last_line, first_line + count - 1)

    widths = [_column_width(l, base) for l in acq.labels]
    period_ps = acq.sample_period_ps
    timing_mode = bool(mode and mode.upper().startswith('TIM')) and period_ps > 0
    tag_label = 'time' if timing_mode else 'tag'
    tag_width = 12

    # Header
    parts = [f'{"line":>8}']
    if with_time:
        parts.append(f'{tag_label:>{tag_width}}')
    for l, w in zip(acq.labels, widths):
        parts.append(f'{l.name:>{w}}')
    header = '  '.join(parts)
    out.write(header + '\n')
    out.write('-' * len(header) + '\n')

    for line in range(first_line, last_line + 1):
        ri = line + trig
        if ri < 0 or ri >= len(rows):
            continue
        cols = [f'{line:>8d}']
        if with_time:
            cols.append(_format_time(line * period_ps) if timing_mode
                        else _format_state_tag(line))
        for l, w in zip(acq.labels, widths):
            v = _format_value(acq.extract(rows[ri], l), base)
            cols.append(f'{v:>{w}}')
        marker = '  <-- TRIGGER' if line == 0 else ''
        out.write('  '.join(cols) + marker + '\n')


def _open_la(args):
    if args.gpib:
        import pyvisa
        rm = pyvisa.ResourceManager('@py')
        resources = rm.list_resources('USB?*')
        if not resources:
            print('No USBTMC devices found', file=sys.stderr)
            sys.exit(1)
        inst = rm.open_resource(resources[0])
        return HP1660(VisaTransport(inst)), ('gpib', inst)
    if args.serial:
        import serial
        port = serial.Serial(args.serial, args.baud, timeout=10)
        return HP1660(port), ('serial', port)
    host = args.lan or '192.168.10.10'
    sock = socket.socket()
    sock.settimeout(30)
    sock.connect((host, 5025))
    return HP1660(SocketTransport(sock)), ('lan', sock)


def _close(handle):
    kind, h = handle
    try:
        h.close()
    except Exception:
        pass


def main():
    p = argparse.ArgumentParser(description='HP 1661 listing -> text')
    p.add_argument('output', nargs='?',
                   help='Output file (default: stdout)')
    p.add_argument('--lan', default=None, help='LAN host')
    p.add_argument('--serial', help='Serial port path')
    p.add_argument('--baud', type=int, default=19200)
    p.add_argument('--gpib', action='store_true',
                   help='Use GPIB via USBTMC')
    p.add_argument('--machine', type=int, default=None, choices=(1, 2),
                   help='Machine number (default: auto — only active machine, '
                        'or 1 if both are active)')
    p.add_argument('--base', default='hex',
                   choices=('hex', 'bin', 'dec', 'oct'),
                   help='Number base for multi-bit labels')
    p.add_argument('--start', type=int, default=None,
                   help='First line number relative to trigger')
    p.add_argument('--count', type=int, default=None,
                   help='Maximum number of lines to output')
    p.add_argument('--time', action='store_true',
                   help='Include a time column')
    args = p.parse_args()

    la, handle = _open_la(args)
    try:
        # Discover active machines first — this is the canonical entry
        # point for "what's configured on this analyzer right now".
        machines = la.get_machines()
        if not machines:
            print('no active machines (both report TYPE OFF)', file=sys.stderr)
            _close(handle)
            sys.exit(3)

        if args.machine is None:
            chosen = machines[0]
            if len(machines) > 1:
                print(f'(multiple active machines: '
                      f'{", ".join(str(m.machine) for m in machines)}; '
                      f'using {chosen.machine}; pass --machine to override)',
                      file=sys.stderr)
        else:
            chosen = next((m for m in machines if m.machine == args.machine), None)
            if chosen is None:
                print(f'machine {args.machine} is OFF; active machines: '
                      f'{", ".join(str(m.machine) for m in machines)}',
                      file=sys.stderr)
                _close(handle)
                sys.exit(3)

        # MachineInfo.type is the truth for STATE vs TIMING — drives the
        # tag-column rendering in write_listing().
        acq = la.acquire(machine=chosen.machine)
    except Exception as e:
        print(f'acquire failed: {e}', file=sys.stderr)
        _close(handle)
        sys.exit(2)

    kwargs = dict(base=args.base, start=args.start, count=args.count,
                  with_time=args.time, mode=chosen.type,
                  machine=chosen.machine, name=chosen.name)
    if args.output and args.output != '-':
        with open(args.output, 'w') as f:
            write_listing(acq, f, **kwargs)
    else:
        write_listing(acq, sys.stdout, **kwargs)

    _close(handle)


if __name__ == '__main__':
    main()
