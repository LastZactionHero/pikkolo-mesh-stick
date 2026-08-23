# Pikkolo Mesh Stick Rev A — schematic notes

Status as of 2026-08-23. The schematic is captured, ERC-clean (0 errors), and its
exported netlist matches the intended netlist exactly (61 nets, 0 discrepancies).
Layout has not started.

---

## How this schematic is built

`mesh/mesh_design.py` is the source of truth for connectivity; `mesh/schlib.py`
renders it to `mesh.kicad_sch`. Connectivity is expressed as **net names on pins**,
not routed wires — every connected pin gets a short stub with a label. That makes the
result mechanically checkable:

```sh
cd mesh
python3 mesh_design.py     # regenerate mesh.kicad_sch
python3 verify_netlist.py  # diff KiCad's exported netlist against intent
```

`verify_netlist.py` is the important one. It catches the failure mode a generated
schematic is prone to: a stub landing a fraction off-grid, or two labels silently
merging. It should always print `0 discrepancies`.

**Once you start editing in Eeschema, stop regenerating** — `mesh_design.py` overwrites
the file. From that point it is documentation of intent, not the source.

---

## Five hardware/firmware mismatches found against the stock Meshtastic variant

The BOM's open item "Pull Meshtastic `rp2040-lora` variant.h — match button/LED GPIOs"
turned up more than expected. The real file is at
`variants/rp2040/rp2040-lora/variant.h` (not `variants/rp2040-lora/`), and a copy is in
`docs/meshtastic-rp2040-lora-variant.h`.

### 1. The RF switch needs TWO control lines, not one

The BOM says "PE4259 ctrl = GP17". That is half the interface. The variant states:

> `// On rp2040-lora board the antenna switch is wired and works with complementary-pin`
> `// control logic. See PE4259 datasheet page 4`
> `#define SX126X_DIO2_AS_RF_SWITCH // Antenna switch CTRL`
> `#define SX126X_RXEN LORA_DIO4    // Antenna switch !CTRL via GPIO17`

So **SX1262 DIO2 → PE4259 CTRL (pin 4)** *and* **RP2040 GPIO17 → PE4259 pin 6 (/CTRL)**.
Wiring only GP17 and leaving DIO2 unconnected would leave the switch uncontrolled.
This is wired correctly in the schematic, with the reference design's 100R + 1nF
de-noising RC on each control line.

Consequence: pin 6 is a **logic input**, not a supply — so it needs no bypass cap.
(The `zach:PE4259-63` symbol types pin 6 as an input for exactly this reason.)

RadioLib parks GP17 LOW when idle, which puts the switch in the **TX** path at rest.

### 2. The TCXO is not enabled by stock firmware

`// #define SX126X_DIO3_TCXO_VOLTAGE 1.8` is **commented out** upstream, and has been
since the variant was introduced. With it absent, RadioLib never issues
`SetDIO3AsTCXOCtrl`, DIO3 stays low, the TCXO never gets powered, and the radio fails
to start (`RADIOLIB_ERR_CHIP_NOT_FOUND` / `XOSC_START_ERR`).

This board mandates a DIO3-powered TCXO, so **your variant must define it**:

```c
#define SX126X_DIO3_TCXO_VOLTAGE 1.8
```

### 3. There is no user button in the stock variant

`#define BUTTON_PIN -1 // Pin 17 used for antenna switching via DIO4`.

SW1 is wired to **GPIO6** here (a `[chosen]` pin). Either set `BUTTON_PIN 6` in your
variant, or set `config.device.button_gpio = 6` at runtime. Defaults when defined are
active-low with internal pull-up, which is how SW1 is wired.

### 4. Stock Meshtastic cannot drive an SK9822 at all

The variant defines only `LED_POWER PIN_LED` (a plain GPIO25 LED). There is no
`HAS_NEOPIXEL`, `HAS_RGB_LED`, or any APA102/DotStar driver in the firmware —
`AmbientLightingThread` supports NeoPixel (one-wire), NCP5623 and LP5562 only.

The SK9822 is a two-wire clock+data part. **Driving it needs custom firmware.**
It is wired to GPIO2 (clock) and GPIO3 (data), which are a valid hardware **SPI0**
SCK/TX pair, so it can be driven by the SPI peripheral rather than bit-banged.

### 5. LoRa SPI is SPI1

`-D HW_SPI1_DEVICE`, 4 MHz, MODE0. SCK=GP14, MOSI=GP15, MISO=GP24, CS=GP13 — all
legal SPI1 pinmux functions. Leaving SPI0 free for the LED is not a coincidence worth
breaking.

---

## Two board-spin-class errors caught in the BOM

### SK9822-EC20 is NOT pin-compatible with APA102-2020

This is the big one. The widespread "SK9822 is a drop-in for APA102" claim is **true for
the 5050 parts and false for the 2020 parts**.

| Pad | SK9822-EC20 | KiCad `LED:APA102-2020` |
|---|---|---|
| 1 | SDO | VDD |
| 2 | GND | CKO |
| 3 | SDI | SDO |
| 4 | CKI | SDI |
| 5 | VDD | CKI |
| 6 | CKO | GND |

Using the stock APA102 symbol/footprint would put VDD on the data-out pad. The land
geometry differs too — KiCad's APA102-2020 is an 8-pad footprint with two centre pads;
the SK9822-EC20 has six pads only.

Fixed: this repo ships `zach:SK9822-EC20` (correct pinout) and
`zach:LED_SK9822-EC20_2020` (six 0.70 × 0.40 mm pads at x = ±0.65, y = 0, ±0.80,
per datasheet Rev.05 §6).

**Placement hazard:** the package orientation mark is on the SDI/CKI edge — *not* at
pin 1. The footprint carries a fab-layer note saying so.

### The SS14 does not drop enough voltage to fix V_IH

The BOM's reasoning was right, the part was wrong. SK9822 wants V_IH ≥ 0.7·VDD, so a
3.3 V driver needs the LED rail at or below ~4.6 V. An SS14 is a 1 A rectifier — its
0.47 V spec is at 1 A, and at this LED's 1–55 mA it drops only **0.15–0.30 V**, leaving
the rail at 4.6–5.05 V. That fails the threshold.

Fixed: **U8, a 74HCT2G34 dual buffer** on VBUS. HCT thresholds guarantee V_IH = 2.0 V
max, so a 3.3 V GPIO has >1 V of margin, the LED sees a full-rail HIGH, and it stays
inside its characterised 4.5–5.5 V supply range. D2/SS14 is deleted.

Fallback if you want the part count back: a **1N4148W** (silicon, not schottky) lands
the rail at 3.9–4.65 V. That mostly works but is marginal at the VBUS-high/LED-idle
corner — roughly ±50 mV either side of the threshold. Not recommended for boards you
cannot rework.

*Note:* the schematic uses the `74xGxx:74AUC2G34` symbol with the Value set to
`74HCT2G34` — same SOT-363 pinout, and KiCad has no HCT2G34 symbol. **Order the HCT
part**; AUC is a 0.8–2.7 V core-logic family and will not do this job.

---

## RF front end

Topology is the Semtech reference design (datasheet Rev 2.2 §14.6 / AN1200.40), with
902–928 MHz values taken from the Waveshare RP2040-LoRa schematic — the board this
clones. **Treat the values as a validated starting point, not gospel**: they are a
licensee's implementation, Semtech does not publish per-band values, and this is a
2-layer stack-up where the reference is 4-layer. Expect to tune on a VNA.

```
TX:   RFO ─┬─ L1 47n choke ─ VR_PA          (RFO has no internal DC path)
           └─ [L2 2n5 ‖ C20 3p] ─┬─ C22 39p ─ L3 4n7 ─┬─ RF1
                                 C21 5p6              C23 1p8
RX:   RF2 ─┬─ C25 2p4 ─ RFI_N ─ L4 15n ─ RFI_P ─ C31 1p8
           C24 1p
ANT:  RFC ─ C32 39p ─┬─ L5 9n1 ─┬─ RA/RB ─ IFA or SMA
                     C33 3p9    C34 3p9
```

- The L2 ‖ C20 notch resonates at 1.838 GHz = 2 × 918.9 MHz, exactly the second
  harmonic of the band centre. Good evidence the values are tuned for US915.
- RF1 = TX, RF2 = RX, RFC = antenna, per every Semtech drawing.
- pSemi requires RF1, RF3 and RF5 be DC-blocked — satisfied by C22, C25 and C32.

**Worth considering before layout:** Johanson `0900FM15D0039001E` is a single 0805 IPD
that replaces this entire 13-part matching/filter block (~0.8 dB typ IL), and is
qualified on the Semtech SX126xMB2xAS shield at +22 dBm. On a 20 mm-wide 2-layer stick
that is a serious offer — it removes most of the tuning risk along with the parts.

### Other SX1262 corrections applied

- **TCXO → XTA needs a 10 pF DC-cut in series with 220 Ω**, and XTB left open
  (datasheet §4.1.4). Waveshare uses a bare 0 Ω with no DC block — follow Semtech.
  Wired as C40 + R6.
- **The TCXO must be a clipped-sine output type**, 0.2–1.2 Vpk-pk, ≤4 mA. A CMOS /
  square-wave 32 MHz TCXO will overdrive XTA. Confirm this when you pick the MPN.
- **VBAT_IO is on the same rail as VBAT** (3V3_RF). The datasheet requires
  `VBAT_IO ≤ VBAT at all times`; two independent LDOs with different ramp rates could
  violate that transiently, so they share one rail deliberately.
- VREG = 470 nF, VR_PA = 47 nF ∥ 47 pF, DCC_SW left NC (internal-LDO mode).

---

## BOM deltas

The BOM's RF section was explicitly a placeholder ("counts below are placeholders").
The reference design needs more parts than budgeted:

| | BOM | Actual | Note |
|---|---|---|---|
| RF inductors | L1–L4 (4) | L1–L5 (5) | + PA drain choke |
| RF caps | C20–C25 (6) | C20–C25, C31–C37, C40 (14) | full ref design |
| RF resistors | — | R6–R8 (3) | TCXO series + 2× control RC |
| LED support | D2 SS14 | U8 74HCT2G34, R9, R10 | see above |
| Decoupling | C3–C14 (12) | + C28, C29, C30, C37, C38, C39 | VREG_VOUT, SX VREG, VR_PA ×2, LED |
| Test points | — | TP1–TP3 | SWD + GND, for bring-up |

Removed: D2 (SS14).
The PE4259 needs **no** bypass cap — complementary mode, so pin 6 is a logic input.

---

## Known ERC state

`kicad-cli sch erc` reports **0 errors, 3 warnings**, all understood:

| Warning | Why it is fine |
|---|---|
| `footprint_link_issues` ×2 | `zach:USB_A_EdgeFinger_2.0mm` and `zach:Antenna_IFA_915MHz` are not authored yet. This warning *is* the tracker. |
| `pin_to_pin` ×1 | PWR_FLAG on VDD_TCXO meets DIO3 (a bidirectional pin that really is a regulated supply). Standard cost of telling ERC a GPIO-like pin is a rail. |

---

## Next steps

1. **Author the two missing footprints** — USB-A edge fingers for 2.0 mm board, and the
   printed IFA. Both are dimensional decisions that belong with layout.
2. **Decide discrete RF network vs the Johanson IPD** before placement.
3. **Pick the TCXO MPN** — clipped-sine, 1.8 V operation, ≤4 mA.
4. **Custom flash footprint** — the BOM wants dual 150/208 mil pads; `U3` currently
   points at stock `SOIC-8_5.3x5.3mm` (208 mil) as a placeholder.
5. **SMA edge-launch** — stock footprints are slotted for 1.6 mm; this board is 2.0 mm.
6. Fork the Meshtastic variant with the four changes in section "mismatches" above.

## Verification caveat

The research behind the RF section came from a multi-agent pass; 5 of 5 research agents
completed but **3 of 5 adversarial verification agents stalled and did not report**.
The SX1262 and Meshtastic findings were additionally spot-checked by hand against the
primary sources (the variant header was fetched directly, the PE4259 pinout read out of
pSemi DOC-03694). The RF **values** carry the weakest independent confirmation — which
is another reason to treat them as a starting point for VNA tuning.
