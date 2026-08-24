#!/usr/bin/env python3
"""
The gate. Is this schematic actually ready to lay out?

Three tools already answer narrower questions -- verify_netlist.py ("is the netlist what I
meant?"), check_design.py ("is that netlist a sane board?"), bom.py ("can I order it?").
This runs them together with the things none of them cover, and prints one verdict.

The point is that "ready to route" stops being a judgement call. Every item below is
either checked mechanically, or listed explicitly as something a human or a measurement
has to close -- and the ones a human has to close are named, not left implied.

    python3 ready_to_route.py

Exit 0 only when every mechanical gate passes. The manual gates are always printed.
"""
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

import mesh_design                                     # noqa: E402
import check_design                                    # noqa: E402
import bom                                             # noqa: E402
from verify_netlist import CLI                         # noqa: E402

S = mesh_design.s

# ERC warnings that are understood and accepted, with the reason they are accepted.
ERC_ALLOWED = {
    "pin_to_pin": "PWR_FLAG on VDD_TCXO meets SX1262 DIO3, a bidirectional pin that "
                  "really is a regulated supply. The standard cost of telling ERC that a "
                  "GPIO-like pin is a rail.",
}

# Gates no script can close. Naming them is the point.
MANUAL_GATES = [
    ("RF network validated",
     "Either the Johanson IPD is chosen (qualified by its vendor at +22 dBm, no tuning), "
     "or the discrete network is validated on a VNA against the real board. The discrete "
     "values came from a licensee's schematic, not from Semtech, and the review found the "
     "topology is the SX1261 network being run at +22 dBm."),
    ("Antenna feed decided and its keepout drawn",
     "Gain, land pattern and all-layer ground keepout have to come from the chosen part's "
     "datasheet before placement, because the keepout sets the board outline."),
    ("Flash boots with the chosen second stage",
     "First article: flash a UF2 and confirm it enumerates. The stock RP2040 boot2 sets "
     "the quad-enable bit with a two-byte 01h write that not every flash accepts."),
    ("FCC 15.247 pre-scan plan exists",
     "3f0, 4f0 and 5f0 land in 15.205 restricted bands and need ~63 dB. That is a "
     "measurement, not a simulation."),
    ("Layout constraints carried out of the schematic",
     "27R at the RP2040 not at the ESD array; R4 and the QSPI pull-up at the flash; "
     "one decoupler per power pin per the Description fields; RF shunt caps with two "
     "ground vias each on the shortest barrel."),
]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
    return r.returncode, r.stdout + r.stderr


def gate_netlist():
    rc, out = run([sys.executable, "verify_netlist.py"])
    m = re.search(r"(\d+) intended nets, (\d+) exported nets, (\d+) discrepanc", out)
    if not m:
        return False, "verify_netlist.py did not report"
    return int(m.group(3)) == 0, "%s nets, %s discrepancies" % (m.group(1), m.group(3))


def gate_erc():
    out_file = HERE / "build" / "erc.rpt"
    out_file.parent.mkdir(exist_ok=True)
    run([CLI, "sch", "erc", "-o", str(out_file), str(HERE / "mesh.kicad_sch")])
    if not out_file.exists():
        return False, "ERC produced no report"
    txt = out_file.read_text()
    m = re.search(r"ERC messages: \d+\s+Errors (\d+)\s+Warnings (\d+)", txt)
    errors = int(m.group(1)) if m else -1
    kinds = set(re.findall(r"^\[(\w+)\]", txt, re.M))
    unexplained = kinds - set(ERC_ALLOWED)
    ok = errors == 0 and not unexplained
    detail = "%d errors, %d warnings" % (errors, int(m.group(2)) if m else -1)
    if unexplained:
        detail += "; UNEXPLAINED: %s" % ", ".join(sorted(unexplained))
    return ok, detail


def gate_design_rules():
    res = check_design.check()
    fails = [r for r in res if r[0] == "FAIL"]
    return not fails, "%d FAIL, %d WARN" % (len(fails), sum(1 for r in res if r[0] == "WARN"))


def gate_bom_sourced():
    """
    Every line that actually needs a part number has one.

    Plain resistors are exempt. A 1% thin-film 0402 at a given value is fungible across a
    dozen vendors, and value + package + tolerance IS the complete purchase specification
    -- demanding an MPN for one is ceremony, not engineering. Everything else must name a
    part, including every capacitor, because the RF ones are C0G at +/-0.1 pF and a
    generic substitute would quietly detune the front end.
    """
    rows = [r for r in bom.lines() if not r["dnp"]]
    def fungible(r):
        return all(ref[0] == "R" for ref in r["refs"])
    unsourced = [r for r in rows if not r["lcsc"] and not r["mpn"] and not fungible(r)]
    spec_only = [r for r in rows if not r["lcsc"] and not r["mpn"] and fungible(r)]
    detail = "%d/%d line items sourced" % (len(rows) - len(unsourced), len(rows))
    if spec_only:
        detail += "; %d resistor value(s) bought to spec: %s" % (
            len(spec_only), ", ".join(r["value"] for r in spec_only))
    return not unsourced, detail


def gate_decisions():
    open_items = [k for k, v in mesh_design.DECISIONS.items() if v is None]
    open_items += ["stackup." + k for k, v in mesh_design.STACKUP.items() if v is None]
    return not open_items, ("all decided" if not open_items
                            else "UNDECIDED: " + ", ".join(open_items))


def gate_netclasses():
    pro = json.loads((HERE / "mesh.kicad_pro").read_text())
    names = {c["name"] for c in pro.get("net_settings", {}).get("classes", [])}
    want = {"RF", "Power", "USB"}
    return want <= names, "classes: %s" % ", ".join(sorted(names))


GATES = [
    ("netlist matches intent", gate_netlist),
    ("ERC clean, every warning explained", gate_erc),
    ("design rules pass", gate_design_rules),
    ("every fitted BOM line is orderable", gate_bom_sourced),
    ("no open design decisions", gate_decisions),
    ("net classes defined for layout", gate_netclasses),
]


def main():
    print("Pikkolo Mesh Stick Rev %s -- ready to route?\n" % mesh_design.REV)
    failed = 0
    for name, fn in GATES:
        try:
            ok, detail = fn()
        except Exception as e:                            # a broken gate is a failed gate
            ok, detail = False, "gate raised %s: %s" % (type(e).__name__, e)
        failed += not ok
        print("  [%s] %-38s %s" % ("PASS" if ok else "FAIL", name, detail))

    print("\n  Gates a script cannot close:")
    for name, why in MANUAL_GATES:
        print("  [MANUAL] %s" % name)
        for line in re.findall(r".{1,74}(?:\s|$)", why):
            if line.strip():
                print("           %s" % line.strip())

    print("\n%s" % ("READY: every mechanical gate passes. The manual gates above are what "
                    "stands between this and copper." if not failed else
                    "NOT READY: %d mechanical gate(s) failing." % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
