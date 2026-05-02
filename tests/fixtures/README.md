# Test fixtures

These EagleCAD source files are used as inputs for the regression tests in
the parent directory.

| File          | Origin |
|---------------|--------|
| `tf536.sch`   | Copied from <https://github.com/terriblefire/tf536_public> — Stephen J. Leary's TF536 (Terrible Fire 030 Accelerator) board, multi-sheet Spartan-6 schematic. |
| `tf536.net`   | Eagle-generated golden netlist export of `tf536.sch`. Used as the reference output for `eagle-netlist` regression. |

A separate TF4060 fixture is needed for `eagle-pcf` — the current
`eagle-pcf` source has a TF4060-board-specific bad-pins list hard-coded,
so it can't sensibly run against TF536 data.

All fixtures are GPL-licensed (matching the parent project).
