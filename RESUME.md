# Resume prompt

Paste this into Claude Code on the other machine, from inside the cloned repo.

---

I'm picking up a KiCad project mid-flight on a new machine. Repo:
https://github.com/LastZactionHero/pikkolo-mesh-stick

It's the **Pikkolo Mesh Stick Rev A** — a USB-stick Meshtastic node, RP2040 + SX1262,
US915, ~20 × 75 mm, 2-layer, 2.0 mm FR-4, plugs into a USB-A port on PCB edge fingers.
Dual antenna feed (printed IFA or SMA) selected by one 0 Ω resistor.

Please start by reading, in this order:
1. `README.md`
2. `docs/SCHEMATIC-NOTES.md` — the important one; it has the findings that corrected
   the draft BOM and the reasoning behind the RF section
3. `mesh/mesh_design.py` — the schematic source of truth

Then get me running:
- `python3 setup.py` (KiCad must be quit) to register the KiCad libraries globally
- `cd mesh && python3 mesh_design.py && python3 verify_netlist.py`
- confirm `verify_netlist.py` prints **0 discrepancies** and that
  `kicad-cli sch erc` shows **0 errors, 3 known warnings**

Context on where things stand: the schematic is captured and verified, layout has not
started. The schematic is generated from `mesh_design.py` via `schlib.py`; connectivity
is net labels on pin stubs, and `verify_netlist.py` diffs KiCad's exported netlist
against the intended one. Once I start editing in Eeschema, stop regenerating.

Next up, roughly in order:
1. Author the two missing footprints — `zach:USB_A_EdgeFinger_2.0mm` (USB-A edge
   fingers for a 2.0 mm board) and `zach:Antenna_IFA_915MHz` (printed IFA). These are
   the two `footprint_link_issues` ERC warnings.
2. Decide discrete RF network vs. the Johanson `0900FM15D0039001E` IPD before layout —
   see the RF section of SCHEMATIC-NOTES.
3. Custom dual-footprint (150/208 mil) pads for the GD25Q32E.
4. SMA edge-launch footprint for 2.0 mm board (stock ones are slotted for 1.6 mm).
5. Then start the PCB.

Don't re-derive the things already settled in SCHEMATIC-NOTES — especially the
Meshtastic GPIO map, the PE4259 complementary control wiring, and the SK9822-EC20
pinout. Those were verified against primary sources and getting them "helpfully"
changed back would cost a board spin.
