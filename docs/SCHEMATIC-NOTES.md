# Pikkolo Mesh Stick Rev B — schematic notes

Status 2026-08-23. Schematic captured and verified; layout not started.

```
verify_netlist.py   60 intended / 60 exported / 0 discrepancies
kicad-cli sch erc   0 errors, 1 warning (explained below)
check_design.py     81 parts, 60 nets, 0 FAIL
ready_to_route.py   4 of 6 mechanical gates PASS
```

**Run `python3 mesh/ready_to_route.py` before doing anything else.** It is the gate: it
prints what is mechanically true, and it names the things a script cannot close. Two
gates are failing right now — the BOM is not sourced, and six design decisions are still
open — and both are listed further down.

---

## How this schematic is built

`mesh/mesh_design.py` is the source of truth for connectivity. `mesh/schlib.py` renders it
to `mesh.kicad_sch`; `mesh/layout.py` holds the drawing shapes (a series chain whose parts
butt together into one wire, a shunt off a node, a parallel branch over a series one).

Connectivity is **net names on pins**, not routed wires. Every connected pin gets a short
stub with a label. Wires are drawn where they make the circuit readable, but they are
decoration — the labels carry the netlist. That is what makes the result mechanically
checkable:

```sh
cd mesh
python3 mesh_design.py       # regenerate mesh.kicad_sch + intended_netlist.json
python3 verify_netlist.py    # diff KiCad's exported netlist against intent
python3 check_design.py      # footprints resolve, no orphan nets, decoupling, pad maps
python3 bom.py               # grouped BOM;  --csv / --jlc to export
python3 ready_to_route.py    # the gate
```

`verify_netlist.py` is the important one. It catches what a generated schematic is prone
to: a stub landing a fraction off-grid, or two labels quietly merging. It earned its keep
twice during Rev B — it caught a mirrored RF chain that had shorted alternate nodes, and
an LED wired cathode-to-GPIO.

**Once you start editing in Eeschema, stop regenerating** — `mesh_design.py` overwrites the
file. From that point it is documentation of intent, not the source.

---

## Rev B: what changed and why

### USB-A edge fingers → a real USB-C male plug

Modern laptops have no USB-A. J2 is now `Connector:USB_C_Plug_USB2.0` on
`Connector_USB:USB_C_Plug_JAE_DX07P024AJ1`.

**The CC termination is the part people get wrong.** A sink presenting a *plug* is a
"direct connect device" and terminates CC with a **single** Rd on A5. R11 is 5.1 kΩ 1%.
B5/VCONN is left open — it must read above zOPEN (126 kΩ). Putting Rd on *both* lands as
Rd/Rd at the host receptacle, which Type-C R2.4 Table 4-10 defines as **Debug Accessory
Mode**. That is a device that does not enumerate, not a device with extra safety.

All four VBUS (A4/A9/B4/B9) and all four GND (A1/A12/B1/B12) contacts are bussed — the
spec requires it, and one contact is rated 250 mA against a ~240 mA peak draw. B6/B7, SBU
and the SuperSpeed pads are deliberately **unnetted**: a USB 2.0 plug has no such
contacts, the receptacle already shorts A6↔B6, and tying them adds a stub to a 90 Ω pair
for nothing. `check_design.py` knows this and excepts J2 from the pad-map rule by name.

**This is also the only management interface.** Meshtastic excludes Bluetooth on RP2040
entirely, so every configuration action happens over USB CDC. The connector is not a
power inlet that could be cost-reduced away.

### Board thickness is now 0.8 mm, and it is not a choice

The JAE plug is a **straddle mount**: the A row lands on F.Cu, the B row on B.Cu, and the
board edge *is* the plug's tongue. The drawing specifies 0.8 ±0.08 mm pad-to-pad.

The old 2.0 mm existed only to make USB-A fingers work. Losing it is a windfall: a 90 Ω
USB pair and a sane 50 Ω RF line are routable on a 20 mm-wide board at 0.8 mm and were
not at 2.0 mm.

It does invalidate the Rev A plan for J1 — stock SMA edge-launch footprints are slotted
for 1.6 mm board. See the open decisions.

### The SK9822 LED chain is gone

Rev A spent an SK9822-EC20, a 74HCT2G34 level shifter, two resistors and two capacitors —
six parts, a 4.5–5.5 V logic domain, and the board's only part with under 500 pieces of
distributor stock — on one RGB pixel that **upstream Meshtastic cannot drive at all**.
`AmbientLightingThread` knows NCP5623, LP5562 and NeoPixel; there is no APA102/SK9822
driver in the tree.

Now: D1 green on GPIO2 and D2 red on GPIO3, each anode-to-GPIO through 1 kΩ to ground.
These drive upstream's `LED_POWER` (a 1 ms heartbeat once a second) and `LED_LORA` (solid
through TX, 100 ms per received packet) with nothing but a `#define`. Two independent
lights arguably say more than one multiplexed colour did.

What is lost: arbitrary colour, the app's ambient-lighting slider, per-node colour
identity. If colour becomes non-negotiable, the answer is **not** to bring back the
SK9822 — it is a genuinely 3.3 V one-wire part (XINGLIGHT XL-2121RGBC-2812B, LCSC
C5349957) on upstream's NeoPixel path: 3 parts, one GPIO, no level shifter.

The `zach:SK9822-EC20` symbol and `zach:LED_SK9822-EC20_2020` footprint remain in the
library. They are correct and were expensive to get right; they are simply unused.

### The BOOTSEL button is gone; R4 stayed

A BOOTSEL button buys exactly one thing: forcing bootloader mode when flash holds a
*valid* image that hangs before USB is serviced. Everything else is already covered —
blank or corrupt flash drops to USB boot by itself, arduino-pico implements the 1200-baud
touch, and SWD via TP1/TP2/TP3 is the guaranteed path.

TP5 lands the `BOOT_SW` net instead; short it to TP3 with tweezers. **R4 (1 kΩ) is kept**
— it isolates that pad stub from QSPI_SS, which runs at ~62 MHz.

### The printed IFA is gone, and so is the dual feed

TI DN023 is the canonical printed 868/915 MHz inverted-F and it is unambiguous: **43 × 20
mm**, characterised on a 31 × 45 mm ground plane. On a 75 × 20 mm stick that antenna eats
57% of the board and still needs retuning against a ground plane barely half the size TI
used.

The RA/RB dual-feed 0 Ω pair went with it. It looked like a 2-cent build option; it is
not. The two feeds want incompatible board-end treatments (a chip antenna needs an
all-layer keepout, an SMA launch needs a solid flood to the edge), and both stubs hang off
`ANT2` detuning whichever feed is actually fitted.

`ANT2` now goes straight to J1.

---

## Defects the red team found, and what was done

Each of these had a primary source behind it. Five were respin- or major-class.

| Defect | Fix |
|---|---|
| No 1 µF at **VREG_VIN**. The RP2040 core LDO needs one at *both* ends (§2.10.1). | C42 added |
| One 100 nF across **two DVDD pins** on opposite corners of the QFN; §2.9.2 asks for one per pin. | C43 added |
| Nothing at all on **USB_VDD** or **ADC_AVDD** — the six 100 nF exactly consumed the six IOVDD pins. | C44 added |
| No pull-up on **QSPI_SS**. CS# must be at its own supply through the 3V3 ramp; RPi omit it only for a flash they qualified, which the GD25Q32E is not. | R14 10 kΩ |
| **27 pF crystal loads** tagged `[rpi]` — but RPi's value is 15 pF for a CL = 10 pF part. 27 pF implies CL = 16.5 pF, matching no specified crystal, and eats start-up margin. | C1/C2 → 15p, Y1 named |
| **55 µF on VBUS** against a 10 µF ceiling in *both* USB 2.0 §7.2.4.1 and Type-C Table 4-3. The ferrite buys no exemption at ~0.3 Ω DCR. | Values only → 9.1 µF |
| **Y2 was an HCMOS oscillator symbol** (`ASE-xxxMHz`) whose pin 1 is EN — and it was being driven. A clipped-sine TCXO has NC there. | Symbol + 2520 footprint |
| The **exposed pad is the RP2040's only ground**, and the stock KiCad footprint has no vias in it. Same for the SX1262, which also dissipates ~230 mW at +22 dBm. | Both footprints forked |
| USBLC6-2SC6 missing the 100 nF at pin 5 its datasheet asks for. | C41 added |
| C40/R6 ordered against Semtech Fig 4-2 (220 Ω belongs at the TCXO output, 10 pF nearest XTA). | Swapped |

### Still true from Rev A, do not "helpfully" undo

- **The RF switch needs TWO control lines.** SX1262 DIO2 → PE4259 CTRL (pin 4) *and*
  RP2040 GPIO17 → pin 6 (/CTRL). Wiring only GP17 leaves the switch uncontrolled. Pin 6 is
  a logic input in complementary mode, so it needs **no** bypass cap. RadioLib parks GP17
  low at idle, which rests the switch in the **TX** path.
- **The TCXO is not enabled by stock firmware.** `SX126X_DIO3_TCXO_VOLTAGE` is commented
  out upstream, so RadioLib never issues `SetDIO3AsTCXOCtrl`, DIO3 stays low and the radio
  fails to start. Your variant must define it.
- **LoRa SPI is SPI1** — SCK=GP14, MOSI=GP15, MISO=GP24, CS=GP13, all legal SPI1 pinmux.
  Leaving SPI0 free is not an accident worth breaking.

### DCC_SW is open on purpose

Pin 9 is left no-connect: internal-LDO mode, Option D of datasheet Fig 5-4. Meshtastic and
RadioLib issue `SetRegulatorMode(DC-DC)` unconditionally and there is no build flag to
change it — but the datasheet is explicit that the linear regulator backstops VREG, and
Meshtastic's own shipping `t-echo-lite` variant leaves DCC_SW open the same way. It costs
4.2 mA in RX, which is free on a USB-powered stick, and it saves a 15 µH 0805.

### Known ERC state

One warning: `pin_to_pin`, PWR_FLAG on VDD_TCXO meeting DIO3 — a bidirectional pin that
really is a regulated supply. The standard cost of telling ERC a GPIO-like pin is a rail.
It is on `ready_to_route.py`'s allow-list with that reason; any *new* warning kind fails
the gate.

---

## Open decisions — the gate fails until these are closed

`mesh_design.py` carries them in `STACKUP` and `DECISIONS` as `None`, so they cannot be
forgotten into a fab order.

| Decision | The question |
|---|---|
| `stackup.layers` | 2 or 4. One review computed that 2-layer shunt-cap ground vias (1.71 nH at 0.8 mm through-board) put each RF shunt cap's series resonance around 1.7–2.1 GHz — below 3f₀/4f₀/5f₀, which is where the filter has to work. Semtech themselves used 4 layers for the +22 dBm SX1262 and 2 only for the +14 dBm SX1261. |
| `rf_network` | Discrete or the Johanson `0900FM15D0039001E` IPD. The discrete TX arm is reportedly Semtech's **SX1261** topology being run at +22 dBm — two elements short. The IPD replaces ~10 discretes, covers the differential RX balun, and is vendor-qualified at +22 dBm, which would close the tuning question outright. Blocked on its land pattern. |
| `antenna` | SMA edge-launch (needs a part suited to 0.8 mm, not the 1.6 mm-slotted stock footprint J1 still points at) or a chip antenna (Johanson 0915AT43A0026 is −4 dBi average and needs a 9.5 × 20 mm all-layer keepout). This sets the board outline. |
| `flash_mpn` | The stock RP2040 boot2 sets the quad-enable bit with a two-byte 01h WRSR that not every flash executes. Either confirm the GD25Q32E accepts it, name the `boot2_generic_03h` override, or move to a part that is known good. |
| `rails` | One LDO or two. Waveshare runs RP2040 and SX1262 from one 3V3 rail; deleting U6 + C17 saves 2 parts. Needs the phase-noise cost quantified, not assumed. |
| `ferrite_fb1` | Keep or delete. Needs its LC resonance against C27 + C15 computed before it is defended. |

## FCC, for whoever does the pre-scan

Under §15.247(d) out-of-band emissions need only 20 dBc — **except** where they land in a
§15.205(a) restricted band, which must meet §15.209(a). Mapping US915 (902.125–927.875
MHz): 2f₀ = 1804–1856 MHz is **not** restricted (20 dBc), but 3f₀ = 2706–2784 MHz,
4f₀ = 3608–3712 MHz and 5f₀ = 4510–4640 MHz **are**, and need roughly 63 dB.

So the L2‖C20 notch at 1.838 GHz — whose arithmetic is exactly right, 1/(2π√(2.5 nH ×
3.0 pF)) = 1837.8 MHz = 2 × 918.9 — targets the one harmonic the FCC does not constrain.
The parts that carry compliance are the LPF section and the antenna pi (C32/C33/L5/C34).
**The antenna pi is not a BOM-reduction candidate**: the PE4259 sits between the TX filter
and the antenna and generates its own harmonics, so the pi is the only filtering after the
switch.

## Layout constraints that live in the schematic

- R1/R2 (27 Ω) within ~5 mm of U1 pins 46/47 — at the **MCU**, not at the ESD array. U7
  goes hard against the plug pads.
- R4 and R14 within ~3 mm of U3 pin 1.
- One decoupler per power pin. Because the RP2040 symbol stacks its IOVDD pins, the
  ratsnest cannot show which cap belongs where — so each carries a `Description` naming
  its pin (`C3` = IOVDD pin 1, `C9` = pins 48+49, and so on). Follow those.
- RF shunt-cap ground pads: two vias each, shortest possible barrel. On a 2-layer board
  this is the single most important harmonic-filtering detail.
- +3V3_RF must stay ≥ 3.30 V **at the SX1262 pins** at 118 mA; that is the datasheet
  minimum to reach +22 dBm, so the rail has no headroom to give away.
