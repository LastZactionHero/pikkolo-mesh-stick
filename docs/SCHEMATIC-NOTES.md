# Pikkolo Mesh Stick Rev B — schematic notes

Status 2026-08-23. Schematic captured and verified; layout not started.

```
verify_netlist.py   59 intended / 59 exported / 0 discrepancies
kicad-cli sch erc   0 errors, 1 warning (explained below)
check_design.py     75 parts, 59 nets, 0 FAIL
bom.py              35 line items, 64 fitted placements, 2 DNP
ready_to_route.py   5 of 6 mechanical gates PASS
```

**Run `python3 mesh/ready_to_route.py` before doing anything else.** It is the gate: it
prints what is mechanically true, and it names the things a script cannot close. Every
design decision is now closed. One gate is still failing: three commodity resistor values
(470R, 4k7, 0R) have no distributor part number, and guessing one is worse than leaving
the gap visible.

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

## The decisions, and why

`mesh_design.py` carries these in `STACKUP` and `DECISIONS`. The gate fails on any `None`,
so an open question cannot be forgotten into a fab order. All are now closed.

| Decision | Made | Why |
|---|---|---|
| `stackup.layers` | **4**, `JLC04081H-3313` | Not for via inductance — that argument was recomputed and does not survive at 0.8 mm, where the resonances land at 2.2–3.9 GHz and help. It buys an uninterrupted ground plane 0.0994 mm under every RF element and a 50 Ω line 0.15 mm wide instead of 1.34 mm. Fee-free; ≤ $0.15/board at qty 100. |
| `rf_network` | **`johanson-ipd`**, `0900FM15K0039001E` | Replaces 13 discretes with one factory-trimmed LTCC part, and fixes the underlying defect: the discrete TX arm was Semtech's **SX1261** topology being run at +22 dBm. The **K** variant, not the D — see the FCC section. KiCad already ships the symbol and footprint. |
| `antenna` | **SMA(F) right-angle, BWSMA-KWE-Z001** (C496551) | A real SMA jack, through-hole. The earlier reason for avoiding board-edge SMA — that the Taoglas "caps at 0.79 mm" — was a misreading: its spec table says 0.8 mm, only the footprint page says 0.79, and 0.79 mm *is* 0.031 in, the industry number for a 0.8 mm board. The real objection applies to every edge launch: tightening an SMA to its spec torque (0.57 N·m) puts ~134 MPa of shear into a 20 × 0.8 mm FR-4 strip, past FR-4's shear strength. Through-hole legs carry that through plated barrels instead, and make thickness a non-parameter. $0.51 and 130k at LCSC against $3.75–4.01 for edge launches; KiCad already ships the footprint. |
| `flash_mpn` | **W25Q32JVSSIQ** (C179173) | The GD25Q32E accepts only a **one-byte** 01h status-register write; RP2040's stock boot2 issues a two-byte form, so the quad-enable bit never gets set and the chip faults out of boot — after enumerating and accepting a UF2. The Winbond `…IQ` order codes ship QE fixed at 1, so boot2 finds the bit already set and never issues the write. Checked against LCSC rather than assumed: 70,003 in stock and **cheaper** than the GigaDevice part it replaces ($0.554 vs $0.906). Same 4 MB, same 208-mil SOIC-8, pin-identical symbol. The Winbond part that really is hard to source is **W25Q80DV** — an older generation in USON-8, and a different part entirely. |
| `rails` | **two LDOs** | Not a preference — a number. Merged onto one ME6211 the worst-case corner is 432 mW against that package's 300 mW **absolute maximum**. Splitting 72 mA / 121 mA keeps both inside SOA. |
| `ferrite_fb1` | **deleted** | With the VBUS bulk cut to spec it was left driving 2 µF: a 90–145 kHz tank damped only by its own DCR, ringing 13–49 % above 5 V on hot-plug — past the LP5907's 6.0 V absolute maximum. |

## Manufacturing constraints, established before layout

- **Order stack-up `JLC04081H-3313` by name, never "no requirement".** The fab's thickness
  tolerance (±0.1 mm) is wider than the connector's window (0.72–0.88 mm) and nothing
  closes that; all you control is where the nominal sits. `-3313` builds at 0.7992 mm,
  dead centre. Explicitly exclude `JLC04081H-7628A` — it builds at 0.7212 mm, below the
  connector's floor before tolerance is applied.
- **Specify a 0.12 mm stencil.** The RP2040's 0.20 × 0.875 mm lead apertures have an IPC
  area ratio of 0.68 at 0.12 mm and only 0.54 at 0.15 mm, against a 0.66 floor.
- **The board must be panelised.** 20 × 75 mm is under JLCPCB Standard PCBA's 70 × 70 mm
  single-board minimum, and Economic PCBA is disqualified twice over — single-sided
  placement only (J2's B row is on B.Cu) and no ENIG at 0.8 mm. A 3-up panel at roughly
  74 × 85 mm clears it.
- **Fiducials are missing** — none global, none local at the 0.4 mm-pitch QFN-56. Add them
  in layout.
- **J2 forces double-sided paste** and a protection cap during reflow, on a board that is
  otherwise single-sided. Hand-fit it after the SMT run and mark it Do Not Place in the
  JLCPCB BOM.
- **The 0.5 mm copper-to-edge rule cannot hold at J2** — its own shell pads sit 0.275 mm
  from the footprint edge. Scope that rule so it excludes the connector, rather than
  discovering it as 20 DRC errors.
- **The RP2040 leaves a 0.20 mm solder-mask dam**, which is exactly JLCPCB's limit. Expect
  ganged openings if anything shifts.
- **Exposed-pad vias are unfilled by design.** JLCPCB's plugged-via rules exclude a via
  with a mask opening on either side, and the exposed pad's own opening is one. Wicking is
  controlled at the stencil instead: paste coverage is 56.3 % (RP2040) and 52.3 % (SX1262),
  inside IPC-7093A's 50–60 % band, and every aperture clears its via barrel.

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

## The firmware contract

A forked variant is mandatory — stock `rp2040-lora` will not bring this board up.

| Define | Value | Why |
|---|---|---|
| `SX126X_DIO3_TCXO_VOLTAGE` | **3.0** | Commented out upstream, so DIO3 never powers the TCXO and the radio never starts. **3.0, not 1.8** — Y2 is the MCGNNM ordering code (2.66–3.465 V). The 1.8 V sibling is a trap: RadioLib defaults `tcxoVoltage` to 1.6 V, below that part's 1.7 V minimum. |
| `-D HW_SPI1_DEVICE` | required | Load-bearing: omitting it is a boot-time `panic()`, and SPI0's default pins collide with LORA_DIO1 / RF_SW_NCTRL / LORA_BUSY. |
| `BUTTON_PIN` | 6 | Upstream is −1, and the code tests `#ifdef` not the value, so the button silently does nothing. |
| `LED_POWER` / `LED_LORA` | 2 / 3 | The two plain LEDs. No custom driver needed. |
| `HAS_CPU_SHUTDOWN` | **omit** | A 3.9 s hold on SW1 triggers SHUTDOWN. On a USB-only stick with no wake source that is a node that stops until it is physically unplugged. |
| `board_upload.maximum_size` | 4194304+ | `board = rpipico` declares 2 MiB. |
| `SX126X_MAX_POWER` | see note | Defaults to 22, so first-article firmware commands +22 dBm immediately. Hold it lower until the front end has been measured. |
| `BATTERY_PIN` | **never define** | No battery, no divider, GP26 is a no-connect. Uncommenting it makes `Power.cpp` read a floating pin and act on the result. |

Also: SPI0's default pins must be overridden (`PIN_SPI0_SCK 2`, `PIN_SPI0_MOSI 3`) or the
global `SPI` object must never be touched.

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
