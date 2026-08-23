# Pikkolo Mesh Stick Rev A — library coverage

Verified against KiCad 10.0 stock libraries on 2026-08-22. `stock` = ships with KiCad,
nothing to install.

## Fully covered by stock KiCad

| Ref | Part | Symbol | Footprint |
|---|---|---|---|
| U1 | RP2040 | `MCU_RaspberryPi:RP2040` | `Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm` |
| U2 | SX1262IMLTRT | `RF:SX1262IMLTRT` | `Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm` † |
| U5 | ME6211C33M5G | `Regulator_Linear:ME6211C33M5` | `Package_TO_SOT_SMD:SOT-23-5` |
| U7 | USBLC6-2SC6 | `Power_Protection:USBLC6-2SC6` | `Package_TO_SOT_SMD:SOT-23-6` |
| Y1 | 12MHz 3225 xtal | `Device:Crystal_GND24` | `Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm` |
| Y2 | 32MHz TCXO 3225 | `Oscillator:ASE-xxxMHz` | `Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm` |
| D2 | SS14 | `Diode:SS14` | `Diode_SMD:D_SOD-123` |
| SW1,SW2 | TS-1187A | `Switch:SW_Push` | `Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A` ‡ |
| R*, C*, L*, FB1 | all passives | `Device:R` / `C` / `L` / `FerriteBead` | `Resistor_SMD` / `Capacitor_SMD` / `Inductor_SMD` 0402·0603·0805 |

† EP2.6x2.6mm is the KiCad symbol's own default, not a guess — the library maintainers
picked it for this part. Stock also carries 2.15/2.5/2.65/2.7/2.75/2.8mm EP variants of
QFN-24 4x4 P0.5mm, so confirm against the Semtech land pattern before committing copper.
‡ Exact MPN footprint, not a generic — stock KiCad has the XKB TS-1187A.

## Covered, but with a caveat

| Ref | Part | Status |
|---|---|---|
| U3 | GD25Q32E (see `zach:GD25Q32E`) | Stock `Memory_Flash:GD25QxxxEY` is **WSON-8**, not SOIC-8. esden `pkl_memory:GD25Q32E` has the right MPN but its footprint is **USON-8** — also wrong. Use either symbol (pinout is standard JEDEC serial flash) and point it at your own dual-150/208mil footprint in `zach.pretty`. Stock `Memory_Flash:W25Q32JVSS` is the SOIC-8 208mil alt and matches the BOM's Winbond fallback. |
| U6 | LP5907YKA-3.3 | Stock has `Regulator_Linear:LP5907MFX-3.3` (SOT-23-5) — this is the BOM's own fallback. **DSBGA-4 0.4mm is not in stock KiCad**, so if the WLCSP survives the open-items list, import it from SnapMagic/TI. |
| D1 | SK9822-EC20 | No SK9822 symbol. `LED:APA102-2020` + `LED_SMD:LED-APA102-2020` — SK9822 is an APA102 clone in the same 2020 body. **Verify pinout against your reel's datasheet before trusting it**; SK9822 and APA102 do differ on some package variants. |
| J1 | SMA edge-launch | `Connector:Conn_Coaxial` symbol is fine. Stock edge-mount footprints (e.g. `SMA_Amphenol_132289_EdgeMount`) are slotted for **1.6mm** board — your BOM calls for 2.0mm. Custom footprint in `zach.pretty`, matched to whichever connector you actually source. |

## Genuinely needs downloading

| Ref | Part | Source | Status |
|---|---|---|---|
| U4 | PE4259-63 | UltraLibrarian zip | **DONE** — `zach:PE4259-63` |

**One part.** Not twenty. And it's now imported.

### U4 PE4259-63 — import notes

Symbol lives in `zach.kicad_sym` (hand-corrected, not the raw vendor output).
The three vendor IPC density footprints are in `imported/UltraLibrarian.pretty/`
as alternates; the assigned footprint is stock `Package_TO_SOT_SMD:SOT-363_SC-70-6`
(same JEDEC body, IPC-7351 nominal, maintained upstream).

Pinout verified against pSemi DOC-03694 Table 7:

| Pin | Name | Note |
|---|---|---|
| 1 | RF1 | DC block required |
| 2 | GND | short trace to plane |
| 3 | RF2 | DC block required |
| 4 | CTRL | CMOS logic in |
| 5 | RFC | DC block required |
| 6 | VDD / ~CTRL | see mode below |

Corrections made to the UltraLibrarian output: renamed `4259-63` → `PE4259-63`;
GND was typed `power_out` (would fight a real power net in ERC) → `power_in`;
CTRL and RFC were `unspecified` → `input` / `bidirectional`; real datasheet URL;
body shrunk from 50.8mm wide to a 25.4mm square with an SPDT glyph.

**Single-pin control mode** (what the BOM's "ctrl = GP17" implies): pin 6 = 3V supply,
decoupled. Truth table — CTRL High → RFC-RF1, CTRL Low → RFC-RF2.
Complementary mode instead drives pin 6 as the inverse of CTRL and needs no bypass.

Two things this pulls into the schematic that the BOM doesn't currently budget:

- **Three DC blocking caps.** Datasheet: "RF pins 1, 3, and 5 must be DC blocked with
  an external series capacitor or held at 0 VDC." RF1, RF2 and RFC all need one.
  Fold into the C20-C25 RF allocation when the Semtech values get locked.
- **One decoupling cap for pin 6.** The C3-C14 breakdown lists RP2040 x7, SX1262 x2,
  LDOs, flash, TCXO — U4 isn't in it. Single-pin mode needs bypassing on VDD.

Min supply is 1.8V, so either 3V3 rail works.

## Custom footprints to author in `zach.pretty`

- `GD25Q32E_SOIC8_dual_150_208mil` — overlapping pads for either body width
- `SMA_EdgeLaunch_2.0mm` — 2.0mm board slot
- IFA antenna as a footprint (keeps the keepout and the copper together, and makes
  it placeable/DRC-checkable instead of loose board copper)
