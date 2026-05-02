# tflab-tools

[![tests](https://github.com/terriblefire/tflab-tools/actions/workflows/tests.yml/badge.svg)](https://github.com/terriblefire/tflab-tools/actions/workflows/tests.yml)

A small collection of hardware / FPGA bench tools by Stephen J. Leary.

Eight command-line utilities and a Python library for talking to HP 1660-series
logic analysers. The package is organised so the core install is pure-Python
and dependency-free; transport- and EDA-specific dependencies live in optional
extras.

## Install

```sh
pip install .
# or, with serial-port support for hp1661-vcd:
pip install '.[serial]'
# or, with GPIB/USBTMC support:
pip install '.[gpib]'
# or, with EagleCAD tooling support:
pip install '.[eagle]'
# or all extras:
pip install '.[serial,gpib,eagle]'
```

For development:

```sh
pip install -e .
```

> The `[eagle]` extra includes a vendored copy of a patched
> [`eagle2svg`](https://github.com/terriblefire/eagle2svg) (Bus rendering,
> Plain section fix, multi-line text fix, 5% margin) under `tflab._eagle2svg`.
> See `src/tflab/_eagle2svg/NOTICE.md` for the BSD attribution.

## Commands

After install, the following commands are available on `$PATH`:

| Command         | Description |
|-----------------|-------------|
| `bin2mif`       | Convert binary file(s) to MIF-style hex output (configurable word width and endianness). |
| `bin2vrlg`      | Convert a binary file to a Verilog `bootrom` module. |
| `mkzorro`       | Generate Amiga Zorro AutoConfig ROM nibbles (Z2/Z3, configurable size, manufacturer ID, serial, product code). |
| `hp1661-vcd`    | Capture data from an HP 1660-series logic analyser and write a VCD file. |
| `eagle-netlist` | Generate a netlist from an EagleCAD `.sch` file. *(extra: `[eagle]`)* |
| `eagle-pcf`     | Convert an Eagle netlist to an FPGA PCF (pin constraints) file. *(extra: `[eagle]`)* |
| `eagle-pdf`     | Render an EagleCAD schematic to multi-page PDF. *(extra: `[eagle]`)* |

Each command supports `--help` (the Eagle tools print a usage line when invoked
without arguments).

---

## bin2mif

Convert one or more binary files into MIF-style hex (one word per line, lower
case, fixed width). Useful for initialising on-chip ROM/RAM contents in FPGA
toolchains that consume MIF or compatible formats.

```sh
bin2mif [-h] [-w {8,16,32,64}] [-e ENDIAN] FILE [FILE ...]
```

| Flag              | Default | Description |
|-------------------|---------|-------------|
| `-w`, `--width`   | `8`     | Word width in bits. |
| `-e`, `--endian`  | `big`   | Byte order. Accepts `big`/`b` or `little`/`l`. |

Output is written to stdout, one word per line, padded to the full width.
Any trailing partial word is silently dropped.

```sh
$ printf '\x00\x01\x02\xff' > rom.bin
$ bin2mif -w 8 rom.bin
00
01
02
ff
$ bin2mif -w 16 -e little rom.bin
0100
ff02
$ bin2mif -w 16 -e big rom.bin > rom.mif
```

---

## bin2vrlg

Convert a binary file into a synthesisable Verilog `bootrom` module — a
clocked address → data ROM with one `case` arm per non-zero byte.

```sh
bin2vrlg [-h] -f FILENAME
```

Output goes to stdout. The address bus width is calculated from the file size
(`ceil(log2(size))`); zero bytes are emitted via the `default` arm to keep
the source file compact.

```sh
$ printf '\x00\x01\x02\xff' > rom.bin
$ bin2vrlg -f rom.bin
module bootrom
(
        input           clk,            // bus clock
        input [1:0]     address,        // address in
        output reg [7:0] data           // data out
);

always @(posedge clk) begin
        case (address)
                2'd1:   data    <=      8'h01;
                2'd2:   data    <=      8'h02;
                2'd3:   data    <=      8'hff;
                default: data   <=      8'd0;
        endcase
end

endmodule
```

---

## mkzorro

Generate the AutoConfig ROM nibble stream for an Amiga Zorro II/III expansion
card. Output is one hex nibble per line on stdout, with the nibble inversion
required by the AutoConfig protocol applied automatically (every nibble after
the ER_TYPE byte is bit-inverted).

```sh
mkzorro [-h] [--version {Z2,Z3}] [--size {64K,128K,256K,512K,1M,2M,4M,8M}]
        [--manuid MANUID] [--serial SERIAL] [--product PRODUCT]
        [--flags FLAGS] [--rom-vector ROM_VECTOR]
```

| Flag            | Default | Description |
|-----------------|---------|-------------|
| `--version`     | `Z2`    | Zorro bus version (Z2 = 0xC0, Z3 = 0x80 in ER_TYPE). |
| `--size`        | `64K`   | Card memory size code. |
| `--manuid`      | `5080`  | Manufacturer ID. Accepts decimal or `0x...`. |
| `--serial`      | `4060`  | Serial number. Accepts decimal or `0x...`. |
| `--product`     | `148`   | Product code. |
| `--flags`       | `0x80`  | ER_FLAGS byte. |
| `--rom-vector`  | `0`     | Diag/init ROM offset. |

Running with no arguments produces the default Terrible Fire control card ROM:

```sh
$ mkzorro | tr '\n' ' '
C 1 6 B 7 F F F E C 2 7 F F F F F 0 2 3 F F F F F F F F F F F F
```

For a Z3 card with 1 MB of address space:

```sh
$ mkzorro --version Z3 --size 1M | head -2
8
5
```

---

## hp1661-vcd

Captures acquisition data from an HP 1660C/CS/CP-series logic analyser,
discovers labels automatically, and writes a standard VCD file consumable by
GTKWave, ModelSim, Surfer, etc.

```sh
hp1661-vcd [-h] [--lan LAN] [--serial SERIAL] [--baud BAUD] [--gpib]
           [--save-config SAVE_CONFIG] [--load-config LOAD_CONFIG]
           [output]
```

`output` defaults to `capture.vcd`.

### Transport options

```sh
# GPIB via USBTMC (fastest — ~5s, requires UsbGpib or similar adapter)
hp1661-vcd --gpib capture.vcd

# LAN via TCP port 5025 (~3s)
hp1661-vcd --lan 192.168.10.10 capture.vcd

# Serial (~80s at 19200 baud)
hp1661-vcd --serial /dev/tty.usbserial-1440 --baud 19200 capture.vcd
```

### Saving/loading label configurations

Label discovery hits the analyser with a chain of SCPI queries; if you're
iterating on captures it's worth saving the result and reusing it.

```sh
# Save the current LA label config to JSON
hp1661-vcd --gpib --save-config la_config.json capture.vcd

# Reuse saved labels (skip label discovery)
hp1661-vcd --gpib --load-config la_config.json capture.vcd
```

### GPIB setup

Requires a USB-GPIB adapter such as [UsbGpib](https://github.com/xyphro/UsbGpib).

1. Flash the `TestAndMeasurement.bin` firmware to the adapter
2. Connect GPIB cable between adapter and LA
3. Set LA controller to HP-IB (front panel: System > External I/O > Controller > HP-IB)
4. Install the gpib extra: `pip install '.[gpib]'`

The adapter enumerates as a USBTMC device. PyVISA discovers it automatically.

**Note:** The HP 1660-series requires `SELECT 1` before machine-level commands
over GPIB. The driver handles this automatically.

---

## eagle-netlist

Extract a flat netlist from an EagleCAD schematic (`.sch`) file. Output format
matches Eagle's native netlist export, so it slots straight into downstream
tools that already understand that format (including `eagle-pcf` below).

```sh
eagle-netlist <input.sch> <output.net>
```

Works without Eagle installed — parses the XML directly with `lxml`. Library,
deviceset, device and gate/pin → pad mappings are resolved from the embedded
library definitions in the schematic.

---

## eagle-pcf

Convert an Eagle netlist (as produced by `eagle-netlist` or Eagle itself) into
a Lattice / Project IceStorm PCF (Physical Constraints File) suitable for
`nextpnr`, `arachne-pnr`, etc.

```sh
eagle-pcf <input.net> <output.pcf> <target_chip>
```

The third positional argument is the FPGA part being targeted; it's used to
look up the package pin map.

---

## eagle-pdf

Render an EagleCAD schematic to a multi-page PDF (one PDF page per schematic
sheet). Uses a vendored, patched [`eagle2svg`](https://github.com/terriblefire/eagle2svg)
(under `tflab._eagle2svg`) to convert each sheet to SVG, then `svglib` +
`reportlab` to assemble the PDF.

```sh
eagle-pdf <input.sch> <output.pdf> [sheet_number]
```

If `sheet_number` is omitted every sheet in the schematic is rendered. The
vendored `eagle2svg` adds, on top of upstream v0.1.5:

- Bus rendering (the upstream's `Bus` class is a stub)
- Plain-section parsing fix (text annotations, wires, circles etc. now appear)
- Multi-line text alignment fix
- 5% whitespace margin for breathing room

Eagle does **not** need to be installed — the schematic XML is parsed directly.

---

## Library use

The `tflab` Python module exposes the HP 1660-series driver. The `HP1660`
class is transport-agnostic — pass any object with `read(n)`/`write(data)`
methods (and optionally `settimeout(t)`/`timeout`) and it just works.

```python
from tflab import HP1660, SocketTransport
import socket

# LAN
s = socket.socket()
s.connect(("192.168.10.10", 5025))
la = HP1660(SocketTransport(s))
```

```python
# GPIB
import pyvisa
from tflab import HP1660, VisaTransport

rm = pyvisa.ResourceManager("@py")
inst = rm.open_resource(rm.list_resources("USB?*")[0])
la = HP1660(VisaTransport(inst))
```

```python
# Serial
import serial
from tflab import HP1660

la = HP1660(serial.Serial("/dev/ttyUSB0", 19200, timeout=10))
```

```python
# Use — same API regardless of transport
print(la.idn())

# Capture acquisition data + VCD
acq = la.acquire()
acq.to_vcd("capture.vcd")

# Read/write labels
la.set_label("DATA", "POSITIVE", 0, [0, 0, 65535, 65535, 0, 0])
la.remove_label("OLD")
labels = la.discover_labels()

# Read/write full format config
cfg = la.get_format()
cfg.save("config.json")
cfg = FormatConfig.load("config.json")
la.set_format(cfg)

# Read/write trigger config
trig = la.get_trigger()
trig.save("trigger.json")
la.set_trigger(TriggerConfig.load("trigger.json"))

# Individual trigger controls
la.set_term("A", "ADDR", "#HDD0000")
la.set_find(1, "A", "OCCURRENCE, 1")
la.set_sample_period("4E-9")
la.set_trigger_position("CENTER")
la.run()
la.stop()
```

### Public classes

| Symbol           | Purpose |
|------------------|---------|
| `HP1660`         | Main driver (transport-agnostic SCPI + acquisition + VCD export). |
| `SocketTransport`| Wraps a `socket.socket` for the LAN transport. |
| `VisaTransport`  | Wraps a PyVISA resource for GPIB/USBTMC; uses VISA-native framing. |
| `FormatConfig`   | Channel labels + thresholds + pod assignment, JSON serialisable. |
| `Label`          | A single label (name, polarity, clock bits, pod masks, width). |
| `TriggerConfig`  | Full trigger setup (terms, sequence levels, ranges, timers, position), JSON serialisable. |
| `TriggerTerm`    | Pattern recogniser term `A`–`J`. |
| `TriggerLevel`   | One sequence level (find/branch/timer controls). |
| `Acquisition`    | Captured rows + sample period + trigger row + `to_vcd(path)`. |

---

## Layout

```
tflab/
├── pyproject.toml
├── README.md
├── LICENSE                         GPL-2.0-or-later
└── src/tflab/
    ├── __init__.py                 re-exports the public API
    ├── hp1660.py                   logic-analyser driver (library)
    ├── hp1661_vcd.py               hp1661-vcd entry point
    ├── bin2mif.py                  bin2mif entry point
    ├── bin2vrlg.py                 bin2vrlg entry point
    ├── mkzorro.py                  mkzorro entry point
    ├── eagle_netlist.py            eagle-netlist entry point
    ├── eagle_pcf.py                eagle-pcf entry point
    ├── eagle_pdf.py                eagle-pdf entry point
    └── _eagle2svg/                 vendored eagle2svg fork (BSD; see NOTICE.md)
```

### Adding a new tool

1. Drop a new `src/tflab/foo.py` with a `def main():` that returns an int
   exit code.
2. Add an entry to `[project.scripts]` in `pyproject.toml`:
   ```toml
   foo = "tflab.foo:main"
   ```
3. `pip install -e .` — the `foo` command is now on `$PATH`.

If the tool needs third-party dependencies, add them to a new
`[project.optional-dependencies]` extra rather than to `dependencies`, so the
core install stays minimal.

## Releasing

Releases are tag-driven. CI publishes via PyPI **trusted publishing** (OIDC) —
no API tokens stored anywhere.

### One-time setup (per environment)

Register a *pending publisher* on each index, then it becomes a normal
publisher after the first upload.

| Field             | Value                              |
|-------------------|------------------------------------|
| PyPI Project Name | `tflab-tools`                      |
| Owner             | `terriblefire`                     |
| Repository name   | `tflab-tools`                      |
| Workflow name     | `release.yml`                      |
| Environment name  | `pypi` (PyPI) / `testpypi` (TestPyPI) |

URLs:
- PyPI: <https://pypi.org/manage/account/publishing/> → "Add a new pending publisher"
- TestPyPI: <https://test.pypi.org/manage/account/publishing/>

Then create the matching environments in the GitHub repo (Settings →
Environments → New environment): `pypi` and `testpypi`. Optional but
recommended: protect the `pypi` environment with required reviewers so
production releases need an approval click.

### Cutting a release

```sh
# Dry-run via TestPyPI first
git tag v0.2.0-rc1 && git push --tags
# verify at https://test.pypi.org/p/tflab-tools

# Real release
git tag v0.2.0 && git push --tags
# lands at https://pypi.org/p/tflab-tools
```

The workflow routes `*-rc*` / `*-test*` tags to TestPyPI and clean
`vX.Y.Z` tags to PyPI. Bump `version` in `pyproject.toml` and
`src/tflab/__init__.py` before tagging.

## License

Copyright (C) 2016-2026 S.J. Leary.

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version. See `LICENSE` for the full text.

The vendored `tflab._eagle2svg` module is a copy of a patched
[`eagle2svg`](https://github.com/terriblefire/eagle2svg) and remains under its
upstream BSD license — see `src/tflab/_eagle2svg/NOTICE.md`.
