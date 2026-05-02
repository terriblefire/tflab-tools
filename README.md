# tflab-tools

A small collection of hardware / FPGA bench tools by Stephen J. Leary.

## Install

```sh
pip install .
# or, with serial-port support for hp1661-vcd:
pip install '.[serial]'
# or, with EagleCAD tooling support:
pip install '.[eagle]'
# or all extras:
pip install '.[serial,eagle]'
```

For development:

```sh
pip install -e .
```

## Commands

After install, the following commands are available on `$PATH`:

| Command      | Description |
|--------------|-------------|
| `bin2mif`    | Convert binary file(s) to MIF-style hex output (configurable word width and endianness). |
| `bin2vrlg`   | Convert a binary file to a Verilog `bootrom` module. |
| `mkzorro`    | Generate Amiga Zorro AutoConfig ROM nibbles (Z2/Z3, configurable size, manufacturer ID, serial, product code). |
| `hp1661-vcd` | Capture data from an HP 1660-series logic analyser over LAN or serial and write a VCD file. |
| `eagle-netlist` | Generate a netlist from an EagleCAD `.sch` file. *(extra: `[eagle]`)* |
| `eagle-pcf`     | Convert an Eagle netlist to an FPGA PCF (pin constraints) file. *(extra: `[eagle]`)* |
| `eagle-pdf`     | Render an EagleCAD schematic to multi-page PDF. *(extra: `[eagle]`)* |

Each command supports `--help` (where applicable; some Eagle tools currently take positional args only — pass none to see usage).

## Library use

The `tflab` Python module exposes the HP 1660-series driver:

```python
from tflab import HP1660, SocketTransport
import socket

s = socket.socket()
s.connect(("192.168.10.10", 5025))
la = HP1660(SocketTransport(s))
print(la.idn())
acq = la.acquire()
acq.to_vcd("capture.vcd")
```

## License

BSD 2-Clause. See `LICENSE`.
