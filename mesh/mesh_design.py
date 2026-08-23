#!/usr/bin/env python3
"""
Pikkolo Mesh Stick Rev A — schematic source.

Generates mesh.kicad_sch. Connectivity lives here; schlib.py turns it into KiCad.
Regenerating overwrites the .kicad_sch, so once you start editing in Eeschema this
file becomes a reference rather than the source of truth.

Provenance tags on nets and values:
  [variant]  verbatim from Meshtastic variants/rp2040/rp2040-lora/variant.h
  [chosen]   not in that file; needs a variant patch (see docs/SCHEMATIC-NOTES.md)
  [semtech]  SX1262 datasheet Rev 2.2 / AN1200.40 reference-design topology
  [ws]       value from the Waveshare RP2040-LoRa schematic, the board this clones
  [rpi]      Raspberry Pi "Hardware design with RP2040" minimal design
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from schlib import Sch

FP = dict(
    RP2040="Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm",
    SX1262="Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm",
    SOIC8="Package_SO:SOIC-8_5.3x5.3mm_P1.27mm",
    SC70_6="Package_TO_SOT_SMD:SOT-363_SC-70-6",
    SOT23_5="Package_TO_SOT_SMD:SOT-23-5",
    SOT23_6="Package_TO_SOT_SMD:SOT-23-6",
    XTAL="Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
    TCXO="Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm",
    SK9822="zach:LED_SK9822-EC20_2020",
    SW="Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A",
    SMA="Connector_Coaxial:SMA_Amphenol_132289_EdgeMount",
    TP="TestPoint:TestPoint_Pad_D1.0mm",
    R="Resistor_SMD:R_0402_1005Metric",
    C="Capacitor_SMD:C_0402_1005Metric",
    C0603="Capacitor_SMD:C_0603_1608Metric",
    C0805="Capacitor_SMD:C_0805_2012Metric",
    L="Inductor_SMD:L_0402_1005Metric",
    FB="Inductor_SMD:L_0603_1608Metric",
)

# Footprints that still need authoring before layout.
TODO_FP = {
    "J2": "zach:USB_A_EdgeFinger_2.0mm",
    "AE1": "zach:Antenna_IFA_915MHz",
}

s = Sch(paper="A2", project="mesh", title="Pikkolo Mesh Stick Rev A")
R_, C_, L_ = "Device:R", "Device:C", "Device:L"


def cap(ref, x, y, val, fp=FP["C"]):
    s.place(ref, C_, x, y, value=val, footprint=fp)


def res(ref, x, y, val, dnp=False):
    s.place(ref, R_, x, y, value=val, footprint=FP["R"], dnp=dnp)


def ind(ref, x, y, val):
    s.place(ref, L_, x, y, value=val, footprint=FP["L"])


def flag(ref, x, y):
    s.place(ref, "power:PWR_FLAG", x, y, in_bom=False)


def rail(ref, lib, x, y):
    s.place(ref, lib, x, y, in_bom=False)


def shunt(ref, x, y, val, node):
    """A capacitor from `node` to ground — the RF network's basic building block."""
    cap(ref, x, y, val)
    s.net(node, "%s.1" % ref)
    s.net("GND", "%s.2" % ref)


def series(ref, kind, x, y, val, a, b):
    """A series element bridging nets `a` and `b`."""
    (cap if kind == "C" else ind if kind == "L" else res)(ref, x, y, val)
    s.net(a, "%s.1" % ref)
    s.net(b, "%s.2" % ref)


# ========================================================== A. USB entry + power
s.box(15.24, 15.24, 165.1, 149.86)
s.text(17.78, 22.86, "A  USB entry, ESD, power rails")

s.place("J2", "Connector:USB_A", 45.72, 60.96, value="USB-A edge fingers",
        footprint=TODO_FP["J2"])
s.place("U7", "Power_Protection:USBLC6-2SC6", 88.9, 60.96, value="USBLC6-2SC6",
        footprint=FP["SOT23_6"])
res("R1", 127.0, 55.88, "27R")
res("R2", 127.0, 66.04, "27R")

s.place("FB1", "Device:FerriteBead", 45.72, 96.52, value="600R@100MHz", footprint=FP["FB"])
cap("C26", 27.94, 111.76, "22u", FP["C0805"])
cap("C27", 63.5, 111.76, "22u", FP["C0805"])

s.place("U5", "Regulator_Linear:ME6211C33M5", 106.68, 96.52, value="ME6211C33M5G",
        footprint=FP["SOT23_5"])
cap("C15", 88.9, 111.76, "1u")
cap("C16", 132.08, 111.76, "1u")
cap("C18", 152.4, 111.76, "10u", FP["C0603"])

s.place("U6", "Regulator_Linear:LP5907MFX-3.3", 106.68, 137.16, value="LP5907MFX-3.3",
        footprint=FP["SOT23_5"])
cap("C17", 132.08, 152.4, "1u")
cap("C19", 152.4, 152.4, "10u", FP["C0603"])
cap("C14", 88.9, 152.4, "100n")

rail("#PWR_VBUS", "power:VBUS", 45.72, 33.02)
rail("#PWR_3V3A", "power:+3V3", 152.4, 96.52)
rail("#PWR_RFA", "zach:+3V3_RF", 152.4, 137.16)
flag("#FLG_VBUS", 20.32, 33.02)
flag("#FLG_GND", 20.32, 43.18)
flag("#FLG_VBUSF", 20.32, 53.34)
rail("#PWR_GND1", "power:GND", 20.32, 63.5)

s.net("VBUS", "J2.1", "U7.5", "#PWR_VBUS.1", "#FLG_VBUS.1", "FB1.1", "C26.1")
s.net("VBUS_F", "#FLG_VBUSF.1", "FB1.2", "C27.1", "U5.1", "U5.3", "U6.1", "U6.3", "C15.1")
s.net("GND", "J2.4", "J2.SH", "U7.2", "#FLG_GND.1", "#PWR_GND1.1", "C26.2", "C27.2",
      "U5.2", "U6.2", "C15.2", "C16.2", "C17.2", "C18.2", "C19.2", "C14.2")
s.net("+3V3", "U5.5", "C16.1", "C18.1", "#PWR_3V3A.1")
s.net("+3V3_RF", "U6.5", "C17.1", "C19.1", "C14.1", "#PWR_RFA.1")
s.no_connect("U5.4", "U6.4")

s.net("USB_DP_C", "J2.3", "U7.1")
s.net("USB_DM_C", "J2.2", "U7.3")
s.net("USB_DP_R", "U7.6", "R1.1")
s.net("USB_DM_R", "U7.4", "R2.1")
s.net("USB_DP", "R1.2")
s.net("USB_DM", "R2.2")

# ============================================================== B. RP2040 core
s.box(190.5, 15.24, 210.82, 279.4)
s.text(193.04, 22.86, "B  RP2040, flash, crystal, buttons")

s.place("U1", "MCU_RaspberryPi:RP2040", 264.16, 132.08, value="RP2040", footprint=FP["RP2040"])

s.net("+3V3", "U1.1", "U1.43", "U1.44", "U1.48")   # IOVDD, ADC_AVDD, VREG_VIN, USB_VDD
s.net("DVDD", "U1.23", "U1.45")                    # VREG_VOUT feeds DVDD  [rpi]
s.net("GND", "U1.57", "U1.19")                     # TESTEN must be grounded  [rpi]
s.net("USB_DM", "U1.46")
s.net("USB_DP", "U1.47")
s.net("RUN", "U1.26")

# 100nF per power pin [rpi]; schematically one node, physically one cap per pin.
for ref, x in [("C3", 203.2), ("C4", 218.44), ("C5", 233.68), ("C6", 248.92)]:
    cap(ref, x, 40.64, "100n")
    s.net("+3V3", "%s.1" % ref)
    s.net("GND", "%s.2" % ref)
cap("C7", 264.16, 40.64, "100n")
s.net("DVDD", "C7.1")
s.net("GND", "C7.2")
cap("C28", 279.4, 40.64, "1u")                     # VREG_VOUT reservoir  [rpi]
s.net("DVDD", "C28.1")
s.net("GND", "C28.2")
cap("C8", 294.64, 40.64, "100n")
s.net("+3V3", "C8.1")
s.net("GND", "C8.2")
cap("C9", 309.88, 40.64, "100n")
s.net("+3V3", "C9.1")
s.net("GND", "C9.2")

res("R5", 208.28, 96.52, "10k")                    # RUN pull-up  [rpi]
s.net("+3V3", "R5.1")
s.net("RUN", "R5.2")

# 12MHz crystal: 1K series on XOUT, 27p loads  [rpi]
s.place("Y1", "Device:Crystal_GND24", 213.36, 187.96, value="12MHz", footprint=FP["XTAL"])
res("R3", 236.22, 187.96, "1k")
cap("C1", 203.2, 205.74, "27p")
cap("C2", 233.68, 205.74, "27p")
s.net("XIN", "U1.20", "Y1.1", "C1.1")
s.net("XOUT_R", "Y1.3", "C2.1", "R3.1")
s.net("XOUT", "R3.2", "U1.21")
s.net("GND", "C1.2", "C2.2", "Y1.2")

# QSPI flash
s.place("U3", "zach:GD25Q32E", 337.82, 187.96, value="GD25Q32E", footprint=FP["SOIC8"])
cap("C12", 370.84, 187.96, "100n")
s.net("+3V3", "U3.8", "C12.1")
s.net("GND", "U3.4", "C12.2")
s.net("QSPI_SS", "U1.56", "U3.1")
s.net("QSPI_SCLK", "U1.52", "U3.6")
s.net("QSPI_SD0", "U1.53", "U3.5")
s.net("QSPI_SD1", "U1.55", "U3.2")
s.net("QSPI_SD2", "U1.54", "U3.3")
s.net("QSPI_SD3", "U1.51", "U3.7")

# BOOTSEL pulls QSPI_SS low through 1K  [rpi]
s.place("SW2", "Switch:SW_Push", 337.82, 246.38, value="BOOTSEL", footprint=FP["SW"])
res("R4", 314.96, 246.38, "1k")
s.net("QSPI_SS", "R4.1")
s.net("BOOT_SW", "R4.2", "SW2.1")
s.net("GND", "SW2.2")

# User button on GPIO6  [chosen] — the stock variant sets BUTTON_PIN -1
s.place("SW1", "Switch:SW_Push", 337.82, 274.32, value="USER", footprint=FP["SW"])
s.net("BTN_USER", "SW1.1", "U1.8")
s.net("GND", "SW1.2")

s.place("TP1", "Connector:TestPoint", 208.28, 246.38, value="SWCLK", footprint=FP["TP"])
s.place("TP2", "Connector:TestPoint", 228.6, 246.38, value="SWDIO", footprint=FP["TP"])
s.place("TP3", "Connector:TestPoint", 248.92, 246.38, value="GND", footprint=FP["TP"])
s.net("SWCLK", "U1.24", "TP1.1")
s.net("SWDIO", "U1.25", "TP2.1")
s.net("GND", "TP3.1")

# =========================================================== C. SX1262 + TCXO
s.box(411.48, 15.24, 157.48, 149.86)
s.text(414.02, 22.86, "C  SX1262 + 32MHz TCXO")

s.place("U2", "RF:SX1262IMLTRT", 469.9, 106.68, value="SX1262IMLTRT", footprint=FP["SX1262"])

# VDD_IN (1) ties straight to VBAT (10); VBAT_IO (11) shares the SAME rail so the
# datasheet rule "VBAT_IO <= VBAT at all times" cannot be broken by LDO ramp skew.
cap("C10", 421.64, 40.64, "100n")
cap("C11", 436.88, 40.64, "100n")
cap("C29", 452.12, 40.64, "470n")                  # VREG  [ws]
cap("C30", 467.36, 40.64, "47n")                   # VR_PA coarse  [ws]
cap("C37", 482.6, 40.64, "47p")                    # VR_PA fine  [ws]
s.net("+3V3_RF", "U2.1", "U2.10", "U2.11", "C10.1", "C11.1")
s.net("GND", "U2.2", "C10.2", "C11.2", "C29.2", "C30.2", "C37.2")
s.net("SX_VREG", "U2.7", "C29.1")
s.net("VR_PA", "U2.24", "C30.1", "C37.1")
s.no_connect("U2.9")                               # DCC_SW unused in internal-LDO mode

# SPI1 + control  [variant]
s.net("LORA_SCK", "U2.18", "U1.17")                # GPIO14
s.net("LORA_MOSI", "U2.17", "U1.18")               # GPIO15
s.net("LORA_MISO", "U2.16", "U1.36")               # GPIO24
s.net("LORA_CS", "U2.19", "U1.16")                 # GPIO13
s.net("LORA_RST", "U2.15", "U1.35")                # GPIO23
s.net("LORA_BUSY", "U2.14", "U1.29")               # GPIO18
s.net("LORA_DIO1", "U2.13", "U1.27")               # GPIO16

# TCXO. Semtech requires a 10pF DC-cut in series with 220R into XTA, and XTB open.
# Waveshare uses a bare 0R with no DC block; follow Semtech, not Waveshare.  [semtech]
s.place("Y2", "Oscillator:ASE-xxxMHz", 421.64, 121.92, value="32MHz TCXO clipped-sine",
        footprint=FP["TCXO"])
cap("C13", 421.64, 152.4, "100n")
series("C40", "C", 452.12, 121.92, "10p", "TCXO_OUT", "TCXO_AC")
series("R6", "R", 472.44, 121.92, "220R", "TCXO_AC", "XTA")
s.net("XTA", "U2.3")
s.net("VDD_TCXO", "U2.6", "Y2.4", "Y2.1", "C13.1")  # DIO3 is a programmable LDO
s.net("TCXO_OUT", "Y2.3")
s.net("GND", "Y2.2", "C13.2")
s.no_connect("U2.4")                               # XTB left open with a TCXO  [semtech]
flag("#FLG_TCXO", 497.84, 152.4)
s.net("VDD_TCXO", "#FLG_TCXO.1")

# ====================================================== D. RF front end (915MHz)
s.box(190.5, 302.26, 378.46, 93.98)
s.text(193.04, 309.88,
       "D  TX LPF / RX balun / antenna pi / SPDT    values [ws] 902-928MHz - tune on hardware")

# --- TX arm: RFO -> 2nd-harmonic notch -> pi LPF -> switch RF1 --------------
ind("L1", 203.2, 332.74, "47n")                    # PA drain choke, VR_PA -> RFO  [semtech]
s.net("VR_PA", "L1.1")
s.net("RFO", "L1.2", "U2.23")
# series notch: L2 parallel with C20, resonant at the 2nd harmonic (~1.84GHz)
ind("L2", 223.52, 332.74, "2n5")
cap("C20", 238.76, 332.74, "3p")
for ref in ("L2", "C20"):
    s.net("RFO", "%s.1" % ref)
    s.net("TX1", "%s.2" % ref)
shunt("C21", 259.08, 332.74, "5p6", "TX1")
series("C22", "C", 279.4, 332.74, "39p", "TX1", "TX2")   # DC block into the switch
series("L3", "L", 299.72, 332.74, "4n7", "TX2", "RF_TX")
shunt("C23", 320.04, 332.74, "1p8", "RF_TX")

# --- RX arm: switch RF2 -> lumped balun -> differential LNA -----------------
shunt("C24", 203.2, 370.84, "1p", "RF_RX")
series("C25", "C", 223.52, 370.84, "2p4", "RF_RX", "RFI_N")
series("L4", "L", 243.84, 370.84, "15n", "RFI_N", "RFI_P")
shunt("C31", 264.16, 370.84, "1p8", "RFI_P")
s.net("RFI_N", "U2.22")
s.net("RFI_P", "U2.21")

# --- SPDT switch, complementary control  [variant] -------------------------
s.place("U4", "zach:PE4259-63", 378.46, 350.52, value="PE4259-63", footprint=FP["SC70_6"])
s.net("RF_TX", "U4.1")                             # RF1 = TX  [semtech]
s.net("RF_RX", "U4.3")                             # RF2 = RX
s.net("RF_ANT", "U4.5")
s.net("GND", "U4.2")
series("R7", "R", 340.36, 332.74, "100R", "RF_SW_CTRL", "SW_CTRL")
series("R8", "R", 340.36, 370.84, "100R", "RF_SW_NCTRL", "SW_NCTRL")
s.net("SW_CTRL", "U4.4")
s.net("SW_NCTRL", "U4.6")
shunt("C35", 355.6, 332.74, "1n", "SW_CTRL")
shunt("C36", 355.6, 370.84, "1n", "SW_NCTRL")
s.net("RF_SW_CTRL", "U2.12")                       # DIO2 drives CTRL
s.net("RF_SW_NCTRL", "U1.28")                      # GPIO17 drives the complement

# --- antenna pi, then the build-time IFA / SMA selection -------------------
series("C32", "C", 416.56, 332.74, "39p", "RF_ANT", "ANT1")   # DC block off RFC
shunt("C33", 436.88, 332.74, "3p9", "ANT1")
series("L5", "L", 457.2, 332.74, "9n1", "ANT1", "ANT2")
shunt("C34", 477.52, 332.74, "3p9", "ANT2")

res("RA", 497.84, 332.74, "0R")
res("RB", 518.16, 332.74, "0R", dnp=True)
s.net("ANT2", "RA.1", "RB.1")
s.place("AE1", "Connector_Generic:Conn_01x01", 497.84, 370.84, value="IFA 915MHz",
        footprint=TODO_FP["AE1"])
s.place("J1", "Connector:Conn_Coaxial", 538.48, 370.84, value="SMA edge", footprint=FP["SMA"])
s.net("ANT_IFA", "RA.2", "AE1.1")
s.net("ANT_SMA", "RB.2", "J1.1")
s.net("GND", "J1.2")

# ============================================== E. SK9822 LED + level shifter
s.box(15.24, 175.26, 165.1, 111.76)
s.text(17.78, 182.88, "E  SK9822 activity LED, 5V logic via HCT buffer")

# The SK9822 needs VIH >= 0.7*VDD. A 3.3V GPIO into a 5V-rail LED does not clear that,
# and an SS14 only drops ~0.2V at this current, so the BOM's diode cannot fix it.
# An HCT-threshold buffer on VBUS does, with >1V of margin, and it keeps the LED inside
# its characterised 4.5-5.5V supply range.
s.place("U8A", "74xGxx:74AUC2G34", 60.96, 210.82, value="74HCT2G34",
        footprint=FP["SC70_6"], unit=1, reference="U8")
s.place("U8B", "74xGxx:74AUC2G34", 60.96, 238.76, value="74HCT2G34",
        footprint=FP["SC70_6"], unit=2, reference="U8")
s.place("U8C", "74xGxx:74AUC2G34", 25.4, 274.32, value="74HCT2G34",
        footprint=FP["SC70_6"], unit=3, reference="U8")
s.net("VBUS", "U8C.5")
s.net("GND", "U8C.2")
s.net("LED_CLK", "U8A.1", "U1.4")                  # GPIO2 = SPI0 SCK  [chosen]
s.net("LED_DAT", "U8B.3", "U1.5")                  # GPIO3 = SPI0 TX   [chosen]
series("R9", "R", 96.52, 210.82, "100R", "LED_CLK_5V", "CKI")
series("R10", "R", 96.52, 238.76, "100R", "LED_DAT_5V", "SDI")
s.net("LED_CLK_5V", "U8A.6")
s.net("LED_DAT_5V", "U8B.4")

s.place("D1", "zach:SK9822-EC20", 137.16, 226.06, value="SK9822-EC20", footprint=FP["SK9822"])
s.net("CKI", "D1.4")
s.net("SDI", "D1.3")
s.net("VBUS", "D1.5")
s.net("GND", "D1.2")
s.no_connect("D1.1", "D1.6")                       # single pixel, chain outputs unused

cap("C38", 162.56, 274.32, "100n")
cap("C39", 137.16, 274.32, "10u", FP["C0603"])
s.net("VBUS", "C38.1", "C39.1")
s.net("GND", "C38.2", "C39.2")

# Unused GPIOs get an explicit no-connect so ERC stays meaningful.
ALL_GPIO_PINS = list(range(2, 10)) + list(range(11, 19)) + list(range(27, 33)) + \
    list(range(34, 42))
USED_GPIO_PINS = {4, 5, 8, 16, 17, 18, 27, 28, 29, 35, 36}
for pin in ALL_GPIO_PINS:
    if pin not in USED_GPIO_PINS:
        s.no_connect("U1.%d" % pin)

if __name__ == "__main__":
    out = pathlib.Path(__file__).parent / "mesh.kicad_sch"
    errs, warns = s.write(out)
    print("wrote %s  (%d placements, %d connections)" % (out.name, len(s.parts), len(s.conns)))
    for e in errs:
        print("  ERROR  ", e)
    for w in warns:
        print("  warn   ", w)
    import json
    (pathlib.Path(__file__).parent / "intended_netlist.json").write_text(
        json.dumps(s.intended_netlist(), indent=1))
    sys.exit(1 if errs else 0)
