#!/usr/bin/env python3
"""
Write the net classes and board constraints into mesh.kicad_pro.

Net classes are a schematic-time decision -- which nets are RF, which carry current,
which are a differential pair -- so they belong next to the netlist, not in a layout
session's memory. Run after mesh_design.py.

KiCad rewrites this file on exit, so run it with KiCad closed.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent

# (name, track width mm, clearance mm, via dia/drill mm, colour) and the net patterns.
CLASSES = [
    dict(name="RF", track_width=0.90, clearance=0.35, via_diameter=0.6, via_drill=0.3,
         pcb_color="rgba(255, 92, 0, 0.500)",
         patterns=["RF_TX", "RF_RX", "RF_ANT", "RFO", "RFI_P", "RFI_N",
                   "TX1", "TX2", "ANT1", "ANT2", "ANT_IFA", "ANT_SMA"]),
    dict(name="Power", track_width=0.60, clearance=0.25, via_diameter=0.8, via_drill=0.4,
         pcb_color="rgba(255, 0, 0, 0.400)",
         patterns=["VBUS", "VBUS_F", "+3V3", "+3V3_RF", "DVDD", "SX_VREG", "VR_PA",
                   "VDD_TCXO"]),
    dict(name="USB", track_width=0.35, clearance=0.20, via_diameter=0.6, via_drill=0.3,
         diff_pair_width=0.35, diff_pair_gap=0.20,
         pcb_color="rgba(0, 160, 255, 0.500)",
         patterns=["USB_DP", "USB_DM", "USB_DP_C", "USB_DM_C", "USB_DP_R", "USB_DM_R"]),
]


def main():
    pro = HERE / "mesh.kicad_pro"
    d = json.loads(pro.read_text())
    ns = d.setdefault("net_settings", {})
    classes = [c for c in ns.get("classes", []) if c.get("name") == "Default"]
    if not classes:
        sys.exit("mesh.kicad_pro has no Default net class; open it in KiCad once first.")
    default = classes[0]

    patterns = []
    for spec in CLASSES:
        c = dict(default)
        c.update({k: v for k, v in spec.items() if k != "patterns"})
        c["priority"] = len(classes)
        classes.append(c)
        for pat in spec["patterns"]:
            patterns.append({"netclass": spec["name"], "pattern": pat})

    ns["classes"] = classes
    ns["netclass_patterns"] = patterns
    pro.write_text(json.dumps(d, indent=2) + "\n")
    print("mesh.kicad_pro: %d net classes, %d net patterns"
          % (len(classes), len(patterns)))


if __name__ == "__main__":
    main()
