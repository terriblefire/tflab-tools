# tflab-tools

A small collection of hardware / FPGA bench tools by Stephen J. Leary.

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

## Commands

After install, the following commands are available on `$PATH`:

| Command      | Description |
|--------------|-------------|
| `bin2mif`    | Convert binary file(s) to MIF-style hex output (configurable word width and endianness). |
| `bin2vrlg`   | Convert a binary file to a Verilog `bootrom` module. |
| `mkzorro`    | Generate Amiga Zorro AutoConfig ROM nibbles (Z2/Z3, configurable size, manufacturer ID, serial, product code). |
| `hp1661-vcd` | Capture data from an HP 1660-series logic analyser and write a VCD file. |
| `eagle-netlist` | Generate a netlist from an EagleCAD `.sch` file. *(extra: `[eagle]`)* |
| `eagle-pcf`     | Convert an Eagle netlist to an FPGA PCF (pin constraints) file. *(extra: `[eagle]`)* |
| `eagle-pdf`     | Render an EagleCAD schematic to multi-page PDF. *(extra: `[eagle]`)* |

Each command supports `--help`.

## hp1661-vcd

Captures acquisition data from an HP 1660C/CS/CP-series logic analyser,
discovers labels automatically, and writes a standard VCD file.

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

## Library use

The `tflab` Python module exposes the HP 1660-series driver:

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

## License

BSD 2-Clause. See `LICENSE`.
