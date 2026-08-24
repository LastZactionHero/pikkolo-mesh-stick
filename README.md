# Pikkolo Mesh Stick — Rev B

A USB-stick Meshtastic node: RP2040 + SX1262, US915, ~20 × 75 mm, plugging straight into a
laptop on a **USB-C male plug**. Two status LEDs, an SMA antenna feed, and no BLE — the
USB-C connection is the only way to configure it, which is why it is a plug and not a
socket.

The schematic is captured and verified. Layout has not started, and it should not start
until `ready_to_route.py` is green — see below.

## Moving to another machine

```sh
git clone <this repo> pikkolo && cd pikkolo
python3 setup.py --skip-vendor      # registers the KiCad libraries. Quit KiCad first.
cd mesh
python3 doctor.py                   # did the toolchain resolve on THIS machine?
python3 mesh_design.py               # regenerate mesh.kicad_sch
python3 ready_to_route.py            # the gate: what is true, and what is left
```

`doctor.py` is the one to run first after a move. It checks the things that fail
silently: kicad-cli present and version 10, the config and shared-support directories
found, `ZLIB` set and pointing at *this* clone, every symbol library the design
references resolving, every footprint resolving, and the personal library present.
A missing library table does not announce itself — it just makes every footprint vanish.

`--skip-vendor` skips the 330 MB esden clone. The design references only KiCad's stock
libraries and `zach:`, so nothing here needs it; drop the flag if you use that collection
in other projects.

Nothing in the repo carries an absolute path. Symbols are flattened into
`mesh.kicad_sch`, so they travel with the file; footprints resolve through the `${ZLIB}`
path variable that `setup.py` writes, so they follow the clone wherever it lands.

`setup.py` writes KiCad's **global** library tables and sets two path variables (`ZLIB`,
`KICAD_3RD_PARTY`), backing up whatever was there into `build/`. It clones the esden
footprint collection (~330 MB) on first run. It refuses to run while KiCad is open,
because KiCad rewrites its config on exit and would discard the variables.

⚠️ It **replaces** the global tables rather than merging, so any other project's libraries
registered globally will be dropped. They are recoverable from
`build/kicad-config-backup/`.

Requires KiCad 10 and Python 3. Paths are auto-detected on macOS, Linux and Windows;
override with `KICAD_CONFIG_HOME`, `KICAD_SHARE_DIR`, `KICAD_CLI`.

## The tools

The schematic is generated, so it is also checkable. Each script answers one question:

| | |
|---|---|
| `mesh_design.py` | the source of truth — all connectivity, with the reasoning in comments |
| `verify_netlist.py` | *is the netlist what I meant?* — diffs KiCad's export against intent |
| `check_design.py` | *is that netlist a sane board?* — footprints resolve, no orphan nets, every supply decoupled, symbol pins match footprint pads |
| `bom.py` | *can I order it?* — grouped BOM, `--csv` or `--jlc` to export |
| `ready_to_route.py` | **the gate** — runs the above, plus the checks none of them cover, and names the gates a script cannot close |
| `project_setup.py` | writes the RF / Power / USB net classes into the project file |
| `doctor.py` | *did this machine load everything?* — run first after moving computers |

`verify_netlist.py` is the one that matters most. A generated schematic fails by having a
stub land a fraction off-grid or two labels quietly merge, and it catches exactly that. It
earned its keep twice during Rev B — a mirrored RF chain that had shorted alternate nodes,
and an LED wired cathode-to-GPIO.

## Current state

```
verify_netlist.py   60 intended / 60 exported / 0 discrepancies
kicad-cli sch erc   0 errors, 1 warning (understood, on an allow-list with its reason)
check_design.py     81 parts, 60 nets, 0 FAIL
bom.py              50 distinct line items, 81 placements
ready_to_route.py   4 of 6 mechanical gates PASS
```

The two failing gates are the honest ones: **the BOM is not sourced** (48 of 50 lines have
no part number) and **six design decisions are still open** — layer count, discrete RF
network vs the Johanson IPD, antenna feed, flash MPN, one rail or two, and whether the
ferrite earns its place. `mesh_design.py` holds those as `None` in `STACKUP` and
`DECISIONS`, so the gate fails on them and they cannot be forgotten into a fab order.

## Layout

```
mesh/                    the KiCad project
  mesh.kicad_pro/_sch/_pcb
  mesh_design.py         schematic source — connectivity, STACKUP, DECISIONS
  schlib.py              minimal KiCad 10 schematic writer
  layout.py              drawing shapes: series chains, shunts, parallel branches
  verify_netlist.py  check_design.py  bom.py  ready_to_route.py  project_setup.py
  intended_netlist.json  generated; the diff target
kicad-lib/               personal library, registered globally by setup.py
  zach.kicad_sym         PE4259-63, GD25Q32E, SK9822-EC20, +3V3_RF, VLED
  zach.pretty/           SK9822-EC20 land, and RP2040 / SX1262 footprints forked to put
                         ground vias through their exposed pads
docs/
  SCHEMATIC-NOTES.md     ** read this first **
  BOM-COVERAGE.md        library coverage per part
  research/              RF + pinout research output
setup.py
```

## Things that will bite you if you skip the notes

- **A USB-C plug takes ONE Rd, on A5 only.** Putting 5.1 k on both CC and VCONN is the
  Debug Accessory signature — the host will not enumerate it as a device.
- **Board thickness is 0.8 mm and is not a free choice.** The straddle-mount plug's tongue
  *is* the board edge. It also means stock 1.6 mm-slotted SMA footprints do not fit.
- **The RF switch needs two control lines** — SX1262 DIO2 *and* GPIO17, complementary.
- **Stock Meshtastic will not bring this board up.** The TCXO line is commented out
  upstream, and `BUTTON_PIN` is −1. A forked variant is required.
- **The TX matching network may be the SX1261 topology.** It is under review; the Johanson
  IPD would replace it and ten discretes at once.
- **2f₀ is the one harmonic FCC does *not* restrict.** 3f₀, 4f₀ and 5f₀ land in §15.205
  restricted bands and need ~63 dB.

Details, sources and fixes are in `docs/SCHEMATIC-NOTES.md`.
