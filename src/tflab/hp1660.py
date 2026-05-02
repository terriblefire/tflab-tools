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
HP 1660-series Logic Analyser interface.

Supports HP 1660C/CS/CP, 1661C/CS, 1662C/CS, 1663C/CS over any
transport with read(n)/write(data) methods (TCP socket, serial port, etc).

Usage:
    # TCP
    import socket
    sock = socket.socket()
    sock.connect(('192.168.10.10', 5025))
    la = HP1660(SocketTransport(sock))

    # Serial
    import serial
    la = HP1660(serial.Serial('/dev/ttyUSB0', 9600))

    # Use
    print(la.idn())
    acq = la.acquire()
    acq.to_vcd('capture.vcd')
"""

import json
import struct
import time
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

class SocketTransport:
    """Wrap a socket to provide read/write/settimeout interface."""

    def __init__(self, sock):
        self.sock = sock

    def read(self, n):
        return self.sock.recv(n)

    def write(self, data):
        self.sock.sendall(data)

    def settimeout(self, t):
        self.sock.settimeout(t)


class VisaTransport:
    """Wrap a PyVISA resource for use with HP1660.

    VISA handles framing differently — queries return complete responses,
    and block reads use read_raw(). This transport bypasses the byte-by-byte
    protocol in HP1660 and provides direct query/read_block methods.
    """

    def __init__(self, resource):
        self.inst = resource
        self.inst.timeout = 30000  # ms
        self._direct = True  # flag for HP1660 to use direct mode

    def read(self, n):
        return self.inst.read_bytes(n)

    def write(self, data):
        self.inst.write_raw(data)

    def settimeout(self, t):
        self.inst.timeout = int(t * 1000)

    @property
    def timeout(self):
        return self.inst.timeout / 1000


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Label:
    name: str
    polarity: str
    clock_bits: int
    pod_masks: list
    width: int

    def to_dict(self):
        return {'name': self.name, 'polarity': self.polarity,
                'clock_bits': self.clock_bits, 'pod_masks': self.pod_masks}

    @staticmethod
    def from_dict(d):
        clock_bits = d.get('clock_bits', 0)
        pod_masks = d.get('pod_masks', [])
        width = bin(clock_bits).count('1') + sum(bin(m).count('1') for m in pod_masks)
        return Label(name=d['name'], polarity=d.get('polarity', 'POSITIVE'),
                     clock_bits=clock_bits, pod_masks=pod_masks, width=width)


@dataclass
class FormatConfig:
    """Complete format configuration for one machine."""
    machine: int
    mode: str  # 'TIMING' or 'STATE'
    acq_mode: str  # e.g. 'CONVENTIONAL,FULL'
    labels: list  # list of Label
    thresholds: dict  # pod_num -> voltage string
    pods: list  # assigned pod numbers

    def to_dict(self):
        return {
            'machine': self.machine,
            'mode': self.mode,
            'acq_mode': self.acq_mode,
            'labels': [l.to_dict() for l in self.labels],
            'thresholds': self.thresholds,
            'pods': self.pods,
        }

    @staticmethod
    def from_dict(d):
        labels = [Label.from_dict(l) for l in d.get('labels', [])]
        return FormatConfig(
            machine=d.get('machine', 1), mode=d.get('mode', 'TIMING'),
            acq_mode=d.get('acq_mode', ''), labels=labels,
            thresholds=d.get('thresholds', {}), pods=d.get('pods', []))

    def save(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load(filename):
        with open(filename) as f:
            return FormatConfig.from_dict(json.load(f))


@dataclass
class TriggerTerm:
    """Pattern recognizer term (A-J)."""
    term_id: str  # 'A'..'J'
    patterns: dict  # label_name -> pattern string (e.g. '#HDD', '#BXXXX1101')

    def to_dict(self):
        return {'term_id': self.term_id, 'patterns': self.patterns}

    @staticmethod
    def from_dict(d):
        return TriggerTerm(term_id=d['term_id'], patterns=d.get('patterns', {}))


@dataclass
class TriggerLevel:
    """One sequence level in the trigger."""
    level: int
    find_qualifier: str  # e.g. 'A', '((A OR B) AND C)'
    find_mode: str  # e.g. 'OCCURRENCE,1' or 'GT,10E-6'
    branch_qualifier: str  # e.g. 'ANYSTATE'
    branch_to: int
    timer1_control: str  # OFF/START/PAUSE/CONTINUE
    timer2_control: str

    def to_dict(self):
        return {
            'level': self.level,
            'find_qualifier': self.find_qualifier,
            'find_mode': self.find_mode,
            'branch_qualifier': self.branch_qualifier,
            'branch_to': self.branch_to,
            'timer1_control': self.timer1_control,
            'timer2_control': self.timer2_control,
        }

    @staticmethod
    def from_dict(d):
        return TriggerLevel(
            level=d['level'],
            find_qualifier=d.get('find_qualifier', 'ANYSTATE'),
            find_mode=d.get('find_mode', 'OCCURRENCE,1'),
            branch_qualifier=d.get('branch_qualifier', 'ANYSTATE'),
            branch_to=d.get('branch_to', 1),
            timer1_control=d.get('timer1_control', 'OFF'),
            timer2_control=d.get('timer2_control', 'OFF'))


@dataclass
class TriggerConfig:
    """Complete trigger configuration for one machine."""
    machine: int
    mode: str  # 'TIMING' or 'STATE'
    acquisition: str  # 'AUTOMATIC' or 'MANUAL'
    sample_period: str  # e.g. '4.00000E-09'
    position: str  # e.g. 'CENTER', 'START', 'END', 'POSTSTORE,50'
    num_levels: int
    trigger_level: int  # which level is the trigger
    terms: list  # list of TriggerTerm
    levels: list  # list of TriggerLevel
    ranges: list  # list of (label, start, stop) tuples
    timers: dict  # timer_num -> time value string

    def to_dict(self):
        return {
            'machine': self.machine,
            'mode': self.mode,
            'acquisition': self.acquisition,
            'sample_period': self.sample_period,
            'position': self.position,
            'num_levels': self.num_levels,
            'trigger_level': self.trigger_level,
            'terms': [t.to_dict() for t in self.terms],
            'levels': [l.to_dict() for l in self.levels],
            'ranges': self.ranges,
            'timers': self.timers,
        }

    @staticmethod
    def from_dict(d):
        return TriggerConfig(
            machine=d.get('machine', 1),
            mode=d.get('mode', 'TIMING'),
            acquisition=d.get('acquisition', 'AUTOMATIC'),
            sample_period=d.get('sample_period', ''),
            position=d.get('position', 'CENTER'),
            num_levels=d.get('num_levels', 1),
            trigger_level=d.get('trigger_level', 1),
            terms=[TriggerTerm.from_dict(t) for t in d.get('terms', [])],
            levels=[TriggerLevel.from_dict(l) for l in d.get('levels', [])],
            ranges=d.get('ranges', []),
            timers=d.get('timers', {}))

    def save(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load(filename):
        with open(filename) as f:
            return TriggerConfig.from_dict(json.load(f))


@dataclass
class Acquisition:
    n_pods: int
    sample_period_ps: int
    trigger_row: int
    rows: list
    labels: list

    def extract(self, row, label):
        """Extract bit values for a label from a data row."""
        clk_word, pods = row
        bits = []
        if label.clock_bits:
            for bit in range(15, -1, -1):
                if label.clock_bits & (1 << bit):
                    bits.append((clk_word >> bit) & 1)
        for i, mask in enumerate(label.pod_masks):
            if not mask:
                continue
            pv = pods[i] if i < len(pods) else 0
            for bit in range(15, -1, -1):
                if mask & (1 << bit):
                    bits.append((pv >> bit) & 1)
        return bits

    def to_vcd(self, filename):
        """Write acquisition data to a VCD file."""
        rows = self.rows
        if not rows:
            return
        ps = self.sample_period_ps
        ts_val, ts_unit = (ps // 1000, "ns") if ps >= 1000 else (ps, "ps")
        ids = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

        with open(filename, 'w') as f:
            f.write(f"$date {time.strftime('%Y-%m-%d %H:%M:%S')} $end\n")
            f.write("$version HP1660 $end\n")
            f.write(f"$timescale {ts_val} {ts_unit} $end\n")
            f.write("$scope module la $end\n")

            sid = {}
            for i, l in enumerate(self.labels):
                c = ids[i] if i < len(ids) else ids[i // len(ids)] + ids[i % len(ids)]
                sid[l.name] = c
                f.write(f"$var wire {l.width} {c} {l.name} $end\n")

            f.write("$upscope $end\n$enddefinitions $end\n")

            prev = {}
            for ri, row in enumerate(rows):
                f.write(f"#{ri}\n")
                if ri == self.trigger_row:
                    f.write("$comment TRIGGER $end\n")
                for l in self.labels:
                    c = sid[l.name]
                    bits = self.extract(row, l)
                    if not bits:
                        continue
                    if l.width == 1:
                        v = f"{bits[0]}{c}"
                    else:
                        v = f"b{''.join(str(b) for b in bits)} {c}"
                    if v != prev.get(l.name):
                        f.write(v + '\n')
                        prev[l.name] = v


# ---------------------------------------------------------------------------
# HP1660
# ---------------------------------------------------------------------------

# Preamble byte offsets (1-indexed in manual, 0-indexed here relative to
# preamble start at section offset 16)
_POD_ROW_OFFSETS = {8: 10, 7: 12, 6: 14, 5: 16, 4: 18, 3: 20, 2: 22, 1: 24}
_COLUMN_SKIP = frozenset({
    'RELATIVE', 'HEXADECIMAL', 'BINARY', 'DECIMAL', 'OCTAL',
    'ASCII', 'TWOS', 'ONES', 'TAGS', 'MACHINE1', 'MACHINE2',
})


class HP1660:
    """HP 1660-series logic analyser interface."""

    def __init__(self, transport):
        """
        Args:
            transport: object with read(n)->bytes, write(data), settimeout(t)
        """
        self._t = transport
        self._mode_cache = {}
        self.cmd('*CLS')
        self.cmd(':SYSTEM:HEADER OFF')
        self.cmd('SELECT 1')
        self.query('*OPC?')

    # -- SCPI primitives --------------------------------------------------

    def cmd(self, command):
        """Send a command (no response expected)."""
        if hasattr(self._t, '_direct'):
            self._t.inst.write(command)
        else:
            self._t.write((command + '\r\n').encode('ascii'))

    def query(self, command, timeout=5):
        """Send a command and read one line response."""
        if hasattr(self._t, '_direct'):
            try:
                return self._t.inst.query(command).strip()
            except Exception:
                return ''
        self._t.write((command + '\r\n').encode('ascii'))
        old = self._timeout()
        self._settimeout(timeout)
        buf = b''
        try:
            while True:
                ch = self._t.read(1)
                if not ch or ch == b'\n':
                    break
                buf += ch
        except (TimeoutError, OSError):
            pass
        self._settimeout(old)
        return buf.decode('ascii', errors='replace').strip()

    def read_block(self):
        """Read IEEE 488.2 definite-length block data (#NLLLL<data>)."""
        if hasattr(self._t, '_direct'):
            raw = self._t.inst.read_raw()
            # Strip any header text before #
            idx = raw.find(b'#')
            if idx >= 0:
                nd = int(raw[idx+1:idx+2])
                data_start = idx + 2 + nd
                return raw[data_start:]
            return raw
        while True:
            c = self._t.read(1)
            if c == b'#':
                break
        nd = int(self._t.read(1))
        length = int(self._t.read(nd))
        data = bytearray()
        old = self._timeout()
        self._settimeout(30)
        while len(data) < length:
            try:
                data.extend(self._t.read(min(65536, length - len(data))))
            except (TimeoutError, OSError):
                if len(data) > length * 0.99:
                    break
                raise
        self._settimeout(old)
        return bytes(data)

    def _settimeout(self, t):
        if hasattr(self._t, 'settimeout'):
            self._t.settimeout(t)
        elif hasattr(self._t, 'timeout'):
            self._t.timeout = t

    def _timeout(self):
        try:
            if hasattr(self._t, 'sock'):
                return self._t.sock.gettimeout()
            return self._t.timeout
        except Exception:
            return 30

    # -- Identity / errors ------------------------------------------------

    def idn(self):
        return self.query('*IDN?')

    def errors(self):
        """Drain the error queue. Returns list of (code, message) tuples."""
        errs = []
        for _ in range(20):
            resp = self.query(':SYSTEM:ERROR? STRING')
            if not resp:
                break
            parts = resp.split(',', 1)
            try:
                code = int(parts[0])
            except ValueError:
                break
            msg = parts[1].strip().strip('"') if len(parts) > 1 else ''
            if code == 0:
                break
            errs.append((code, msg))
        return errs

    # -- Machine state ----------------------------------------------------

    def acq_mode(self, machine=1):
        """Return acquisition mode string, or '' if machine is off."""
        if machine in self._mode_cache:
            return self._mode_cache[machine]
        resp = self.query(f':MACHINE{machine}:ASSIGN?')
        if not resp or resp == 'NONE':
            self._mode_cache[machine] = ''
            return ''
        resp = self.query(f':MACHINE{machine}:TLIST:COLUMN? 0')
        if resp:
            self._mode_cache[machine] = 'TIMING'
            return 'TIMING'
        resp = self.query(f':MACHINE{machine}:SLIST:COLUMN? 0')
        if resp:
            self._mode_cache[machine] = 'STATE'
            return 'STATE'
        self._mode_cache[machine] = ''
        return ''

    # -- Pods -------------------------------------------------------------

    def get_pods(self, machine=1):
        """Return list of pod numbers assigned to this machine."""
        resp = self.query(f':MACHINE{machine}:ASSIGN?')
        if not resp:
            return []
        return [int(p.strip()) for p in resp.split(',') if p.strip().isdigit()]

    def set_pods(self, pods, machine=1):
        """Assign pods to a machine. Pods are assigned in pairs."""
        pod_str = ','.join(str(p) for p in pods) if pods else 'NONE'
        self.cmd(f':MACHINE{machine}:ASSIGN {pod_str}')

    # -- Thresholds -------------------------------------------------------

    def get_threshold(self, pod, machine=1):
        """Return threshold voltage string for a pod (e.g. 'TTL', '1.60')."""
        mode = self.acq_mode(machine)
        fc = 'TFORMAT' if mode == 'TIMING' else 'SFORMAT'
        return self.query(f':MACHINE{machine}:{fc}:THRESHOLD{pod}?')

    def set_threshold(self, pod, value, machine=1):
        """Set threshold for a pod. Value: 'TTL', 'ECL', or voltage float."""
        mode = self.acq_mode(machine)
        fc = 'TFORMAT' if mode == 'TIMING' else 'SFORMAT'
        self.cmd(f':MACHINE{machine}:{fc}:THRESHOLD{pod} {value}')

    def get_thresholds(self, machine=1):
        """Return dict of pod_num -> threshold string for all assigned pods."""
        pods = self.get_pods(machine)
        result = {}
        for pod in pods:
            result[pod] = self.get_threshold(pod, machine)
        return result

    def set_thresholds(self, thresholds, machine=1):
        """Set thresholds from a dict of pod_num -> value."""
        for pod, value in thresholds.items():
            self.set_threshold(pod, value, machine)

    # -- Labels -----------------------------------------------------------

    def _label_names(self, machine=1):
        """Enumerate label names via column queries. Returns list of unique names."""
        mode = self.acq_mode(machine)
        if not mode:
            return []
        lc = 'TLIST' if mode == 'TIMING' else 'SLIST'

        seen = set()
        names = []
        for col in range(60):
            resp = self.query(f':MACHINE{machine}:{lc}:COLUMN? {col}')
            if not resp:
                break
            name = None
            for p in resp.split(','):
                p = p.strip().strip('"').strip()
                if p and p not in _COLUMN_SKIP and not p.isdigit():
                    name = p
                    break
            if not name:
                continue
            if name in seen:
                break
            seen.add(name)
            names.append(name)
        return names

    def _fmt_cmd(self, machine=1):
        """Return the format subsystem prefix for the machine's mode."""
        mode = self.acq_mode(machine)
        return 'TFORMAT' if mode == 'TIMING' else 'SFORMAT'

    def discover_labels(self, machine=1):
        """Discover all active labels on the given machine."""
        mode = self.acq_mode(machine)
        if not mode:
            return []
        lc = 'TLIST' if mode == 'TIMING' else 'SLIST'
        fc = 'TFORMAT' if mode == 'TIMING' else 'SFORMAT'

        # Enumerate column names
        skip = _COLUMN_SKIP
        seen = set()
        names = []
        for col in range(30):
            resp = self.query(f':MACHINE{machine}:{lc}:COLUMN? {col}')
            if not resp:
                continue
            name = None
            for p in resp.split(','):
                p = p.strip().strip('"').strip()
                if p and p not in skip and not p.isdigit():
                    name = p
                    break
            if not name:
                continue
            if name in seen:
                break
            seen.add(name)
            names.append(name)

        # Query label assignments
        labels = []
        for name in names:
            resp = self.query(f":MACHINE{machine}:{fc}:LABEL? '{name}'")
            label = self._parse_label(resp)
            if label:
                labels.append(label)

        return labels

    def get_label(self, name, machine=1):
        """Query a single label's assignment. Returns Label or None."""
        fc = self._fmt_cmd(machine)
        resp = self.query(f":MACHINE{machine}:{fc}:LABEL? '{name}'")
        return self._parse_label(resp)

    def set_label(self, name, polarity, clock_bits, pod_masks, machine=1):
        """Create or update a label."""
        fc = self._fmt_cmd(machine)
        masks = ','.join(str(m) for m in pod_masks)
        self.cmd(f":MACHINE{machine}:{fc}:LABEL '{name}', {polarity}, {clock_bits}, {masks}")

    def remove_label(self, name, machine=1):
        """Remove a single label."""
        fc = self._fmt_cmd(machine)
        self.cmd(f":MACHINE{machine}:{fc}:REMOVE '{name}'")

    def remove_all_labels(self, machine=1):
        """Remove all labels."""
        fc = self._fmt_cmd(machine)
        self.cmd(f":MACHINE{machine}:{fc}:REMOVE ALL")

    # -- Full format config -----------------------------------------------

    def get_format(self, machine=1):
        """Read complete format configuration for a machine."""
        mode = self.acq_mode(machine)
        if not mode:
            return None
        fc = self._fmt_cmd(machine)

        acq = ''
        if mode == 'TIMING':
            acq = self.query(f':MACHINE{machine}:TFORMAT:ACQMODE?')

        pods = self.get_pods(machine)
        thresholds = self.get_thresholds(machine)
        labels = self.discover_labels(machine)

        return FormatConfig(machine=machine, mode=mode, acq_mode=acq,
                            labels=labels, thresholds=thresholds, pods=pods)

    def set_format(self, config):
        """Write complete format configuration to a machine.

        Removes all existing labels, then creates the ones from config.
        Also sets thresholds and acquisition mode.
        """
        m = config.machine
        fc = self._fmt_cmd(m)

        if config.acq_mode and config.mode == 'TIMING':
            self.cmd(f':MACHINE{m}:TFORMAT:ACQMODE {config.acq_mode}')

        self.set_thresholds(config.thresholds, m)
        self.remove_all_labels(m)

        for label in config.labels:
            self.set_label(label.name, label.polarity,
                           label.clock_bits, label.pod_masks, m)

    def update_labels(self, labels, machine=1):
        """Update specific labels without touching others.

        Creates or overwrites the given labels. Does not remove
        labels that aren't in the list.
        """
        for label in labels:
            if isinstance(label, Label):
                self.set_label(label.name, label.polarity,
                               label.clock_bits, label.pod_masks, machine)
            elif isinstance(label, dict):
                l = Label.from_dict(label)
                self.set_label(l.name, l.polarity,
                               l.clock_bits, l.pod_masks, machine)

    @staticmethod
    def _parse_label(resp):
        if not resp:
            return None
        parts = resp.split(',')
        if len(parts) < 3:
            return None
        name = parts[0].strip().strip('"').strip()
        polarity = parts[1].strip()
        try:
            clock_bits = int(parts[2].strip())
            pod_masks = [int(p.strip()) for p in parts[3:]]
        except ValueError:
            return None
        width = bin(clock_bits).count('1') + sum(bin(m).count('1') for m in pod_masks)
        if width == 0:
            return None
        return Label(name=name, polarity=polarity, clock_bits=clock_bits,
                     pod_masks=pod_masks, width=width)

    # -- Trigger ----------------------------------------------------------

    def _trig_cmd(self, machine=1):
        mode = self.acq_mode(machine)
        return 'TTRIGGER' if mode == 'TIMING' else 'STRIGGER'

    def get_trigger(self, machine=1):
        """Read complete trigger configuration."""
        mode = self.acq_mode(machine)
        if not mode:
            return None
        tc = self._trig_cmd(machine)

        # Sequence info
        seq_resp = self.query(f':MACHINE{machine}:{tc}:SEQUENCE?')
        num_levels, trigger_level = 1, 1
        if seq_resp:
            parts = seq_resp.split(',')
            num_levels = int(parts[0].strip()) if parts else 1
            trigger_level = int(parts[1].strip()) if len(parts) > 1 else 1

        # Acquisition mode
        acq = self.query(f':MACHINE{machine}:{tc}:ACQUISITION?')

        # Sample period (timing only)
        speriod = ''
        if mode == 'TIMING':
            speriod = self.query(f':MACHINE{machine}:{tc}:SPERIOD?')

        # Trigger position
        position = self.query(f':MACHINE{machine}:{tc}:TPOSITION?')

        # Timers
        timers = {}
        for t in (1, 2):
            resp = self.query(f':MACHINE{machine}:{tc}:TIMER{t}?')
            if resp:
                timers[t] = resp

        # Ranges
        ranges = []
        resp = self.query(f':MACHINE{machine}:{tc}:RANGE?')
        if resp:
            parts = resp.split(',')
            if len(parts) >= 3:
                label = parts[0].strip().strip('"').strip()
                ranges.append((label, parts[1].strip(), parts[2].strip()))

        # Terms — query each term for each label
        label_names = self._label_names(machine)
        terms = []
        for term_id in 'ABCDEFGHIJ':
            patterns = {}
            for lname in label_names:
                resp = self.query(f":MACHINE{machine}:{tc}:TERM? {term_id},'{lname}'")
                if resp:
                    parts = resp.split(',')
                    if len(parts) >= 3:
                        pat = parts[2].strip().strip('"')
                        if pat and not all(c in 'Xx.' for c in pat.replace('#B', '').replace('#H', '').replace('#Q', '')):
                            patterns[lname] = pat
            if patterns:
                terms.append(TriggerTerm(term_id=term_id, patterns=patterns))

        # Levels
        levels = []
        for lev in range(1, num_levels + 1):
            find_resp = self.query(f':MACHINE{machine}:{tc}:FIND{lev}?')
            branch_resp = self.query(f':MACHINE{machine}:{tc}:BRANCH{lev}?')

            find_qual, find_mode = 'ANYSTATE', 'OCCURRENCE,1'
            if find_resp:
                # Response: qualifier,mode_info
                parts = find_resp.split(',', 1)
                find_qual = parts[0].strip().strip("'\"")
                find_mode = parts[1].strip() if len(parts) > 1 else ''

            branch_qual, branch_to = 'ANYSTATE', 1
            if branch_resp:
                parts = branch_resp.rsplit(',', 1)
                branch_qual = parts[0].strip().strip("'\"")
                branch_to = int(parts[1].strip()) if len(parts) > 1 else 1

            t1 = self.query(f':MACHINE{machine}:{tc}:TCONTROL{lev}? 1')
            t2 = self.query(f':MACHINE{machine}:{tc}:TCONTROL{lev}? 2')

            levels.append(TriggerLevel(
                level=lev, find_qualifier=find_qual, find_mode=find_mode,
                branch_qualifier=branch_qual, branch_to=branch_to,
                timer1_control=t1 or 'OFF', timer2_control=t2 or 'OFF'))

        return TriggerConfig(
            machine=machine, mode=mode, acquisition=acq or '',
            sample_period=speriod, position=position or '',
            num_levels=num_levels, trigger_level=trigger_level,
            terms=terms, levels=levels, ranges=ranges, timers=timers)

    def set_trigger(self, config):
        """Write complete trigger configuration."""
        m = config.machine
        tc = self._trig_cmd(m)

        # Clear first
        self.cmd(f':MACHINE{m}:{tc}:CLEAR ALL')

        # Acquisition mode
        if config.acquisition:
            self.cmd(f':MACHINE{m}:{tc}:ACQUISITION {config.acquisition}')

        # Sample period
        if config.sample_period:
            self.cmd(f':MACHINE{m}:{tc}:SPERIOD {config.sample_period}')

        # Sequence levels
        self.cmd(f':MACHINE{m}:{tc}:SEQUENCE {config.num_levels}')

        # Terms
        for term in config.terms:
            for label, pattern in term.patterns.items():
                self.cmd(f":MACHINE{m}:{tc}:TERM {term.term_id},'{label}','{pattern}'")

        # Ranges
        for label, start, stop in config.ranges:
            self.cmd(f":MACHINE{m}:{tc}:RANGE '{label}','{start}','{stop}'")

        # Timers
        for num, value in config.timers.items():
            self.cmd(f':MACHINE{m}:{tc}:TIMER{num} {value}')

        # Levels
        for level in config.levels:
            self.cmd(f":MACHINE{m}:{tc}:FIND{level.level} '{level.find_qualifier}', {level.find_mode}")
            self.cmd(f":MACHINE{m}:{tc}:BRANCH{level.level} '{level.branch_qualifier}', {level.branch_to}")
            self.cmd(f':MACHINE{m}:{tc}:TCONTROL{level.level} 1, {level.timer1_control}')
            self.cmd(f':MACHINE{m}:{tc}:TCONTROL{level.level} 2, {level.timer2_control}')

        # Position
        if config.position:
            self.cmd(f':MACHINE{m}:{tc}:TPOSITION {config.position}')

    def set_term(self, term_id, label, pattern, machine=1):
        """Set a single term pattern for a label."""
        tc = self._trig_cmd(machine)
        self.cmd(f":MACHINE{machine}:{tc}:TERM {term_id},'{label}','{pattern}'")

    def set_find(self, level, qualifier, mode, machine=1):
        """Set the find (proceed) qualifier for a sequence level."""
        tc = self._trig_cmd(machine)
        self.cmd(f":MACHINE{machine}:{tc}:FIND{level} '{qualifier}', {mode}")

    def set_branch(self, level, qualifier, to_level, machine=1):
        """Set the branch qualifier for a sequence level."""
        tc = self._trig_cmd(machine)
        self.cmd(f":MACHINE{machine}:{tc}:BRANCH{level} '{qualifier}', {to_level}")

    def set_sample_period(self, period, machine=1):
        """Set the sample period (timing mode). E.g. '4E-9' for 4ns."""
        tc = self._trig_cmd(machine)
        self.cmd(f':MACHINE{machine}:{tc}:SPERIOD {period}')

    def set_trigger_position(self, position, machine=1):
        """Set trigger position. E.g. 'CENTER', 'START', 'END', 'POSTSTORE,50'."""
        tc = self._trig_cmd(machine)
        self.cmd(f':MACHINE{machine}:{tc}:TPOSITION {position}')

    # -- Acquisition ------------------------------------------------------

    def run(self):
        """Start acquisition (non-blocking)."""
        self.cmd(':START')

    def stop(self):
        """Stop acquisition."""
        self.cmd(':STOP')

    def triggered(self):
        """Check if trigger has fired. Returns True/False."""
        resp = self.query(':MESR1?')
        try:
            return (int(resp) & 4) != 0
        except ValueError:
            return False

    def complete(self):
        """Check if acquisition is complete. Returns True/False."""
        resp = self.query(':MESR1?')
        try:
            return (int(resp) & 1) != 0
        except ValueError:
            return False

    def wait(self, timeout=30):
        """Wait for acquisition to complete. Returns True if complete, False on timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.complete():
                return True
            time.sleep(0.2)
        return False

    def single(self, timeout=30):
        """Run a single acquisition and wait. Returns True if complete, False on timeout."""
        self.run()
        return self.wait(timeout)

    def acquire(self, machine=1):
        """Discover labels and download acquisition data. Returns Acquisition."""
        labels = self.discover_labels(machine)
        self.cmd(':SYSTEM:DATA?')
        raw = self.read_block()
        parsed = self._parse_data(raw)
        parsed['labels'] = labels
        return Acquisition(**parsed)

    @staticmethod
    def _parse_data(data):
        b = 16  # preamble start (after 16-byte section header)
        n_pod_pairs = data[b + 3]
        sample_period_ps = struct.unpack_from('>q', data, b + 16)[0]

        row_counts = {}
        trigger_rows = {}
        for pod, poff in _POD_ROW_OFFSETS.items():
            row_counts[pod] = struct.unpack_from('>H', data, b + 84 + poff)[0]
            trigger_rows[pod] = struct.unpack_from('>H', data, b + 110 + poff)[0]

        n_pods = n_pod_pairs * 2
        row_width = 2 + n_pods * 2
        max_rows = max(row_counts.values()) if row_counts else 0
        acq_start = b + 160

        rows = []
        for r in range(max_rows):
            off = acq_start + r * row_width
            if off + row_width > len(data):
                break
            clk = struct.unpack_from('>H', data, off)[0]
            pods = [struct.unpack_from('>H', data, off + 2 + p * 2)[0] for p in range(n_pods)]
            rows.append((clk, pods))

        return {
            'n_pods': n_pods,
            'sample_period_ps': sample_period_ps,
            'trigger_row': max(trigger_rows.values()) if trigger_rows else 0,
            'rows': rows,
        }
