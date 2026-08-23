# Pikkolo Mesh Stick — Rev A

A USB-stick-form Meshtastic node: RP2040 + SX1262, US915, ~20 × 75 mm, 2-layer, 2.0 mm
FR-4, plugging straight into a USB-A port on PCB edge fingers. Dual antenna feed
(printed IFA or SMA whip) selected at build time by a single 0 Ω resistor.

The schematic is captured and verified. Layout has not started.

## Resume on a new machine

```sh
git clone <this repo> pikkolo && cd pikkolo
python3 setup.py                    # registers the KiCad libraries. Quit KiCad first.
cd mesh
python3 mesh_design.py              # regenerate mesh.kicad_sch
python3 verify_netlist.py           # must print "0 discrepancies"
```

`setup.py` writes KiCad's **global** library tables and sets two path variables
(`ZLIB`, `KICAD_3RD_PARTY`), backing up whatever was there into `build/`. It clones the
esden footprint collection (~330 MB) on first run. It refuses to run while KiCad is
open, because KiCad rewrites its config on exit and would discard the variables.

Requires KiCad 10 and Python 3. Paths are auto-detected on macOS, Linux and Windows;
override with `KICAD_CONFIG_HOME`, `KICAD_SHARE_DIR`, `KICAD_CLI` if needed.

## Layout

```
mesh/                    the KiCad project
  mesh.kicad_pro/_sch/_pcb
  mesh_design.py         schematic source — all connectivity lives here
  schlib.py              minimal KiCad 10 schematic writer
  verify_netlist.py      diffs KiCad's exported netlist against intent
  intended_netlist.json  generated; the diff target
kicad-lib/               personal KiCad library, registered globally by setup.py
  zach.kicad_sym         PE4259-63, GD25Q32E, SK9822-EC20, +3V3_RF, VLED
  zach.pretty/           LED_SK9822-EC20_2020
docs/
  SCHEMATIC-NOTES.md     ** read this first **
  BOM-COVERAGE.md        every BOM line vs. what's in the libraries
  research/              full RF + pinout research output
  meshtastic-rp2040-lora-variant.h   the firmware pinout this design is pinned to
setup.py
```

## Current state

- 87 placements, 235 connections, 61 nets
- `kicad-cli sch erc`: **0 errors**, 3 understood warnings
- netlist verification: **61 intended / 61 exported / 0 discrepancies**

## Things that will bite you if you skip the notes

- **SK9822-EC20 is not pin-compatible with APA102-2020.** The 5050 parts are; the 2020
  parts are not. Using KiCad's stock APA102 footprint puts VDD on the data-out pad.
- **The RF switch needs two control lines** — SX1262 DIO2 *and* GPIO17. The BOM's
  "ctrl = GP17" is half of it.
- **Stock Meshtastic firmware will not bring this board up.** The TCXO line is commented
  out, there is no user button, and there is no SK9822 driver at all.
- **The SS14 in the original BOM cannot do its job** — it drops ~0.2 V at this current,
  not the ~0.6 V the level-shift math needed. Replaced with a 74HCT2G34.

Details, sources and fixes for all of these are in `docs/SCHEMATIC-NOTES.md`.
