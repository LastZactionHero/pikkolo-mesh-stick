#!/usr/bin/env python3
"""
Bill of materials, straight off mesh_design.py.

Groups by (Value, Footprint, MPN) the way an assembler does, because that grouping --
not the raw part count -- is what a fab charges setup for.

    python3 bom.py                 human summary
    python3 bom.py --csv out.csv   generic CSV
    python3 bom.py --jlc out.csv   JLCPCB assembly BOM (Comment / Designator / Footprint / LCSC)
"""
import csv
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import mesh_design                                    # noqa: E402

S = mesh_design.s
SKIP = ("#PWR", "#FLG")


def _natural(ref):
    m = re.match(r"^([A-Z]+)(\d+)$", ref)
    return (m.group(1), int(m.group(2))) if m else (ref, 0)


def lines():
    by_ref = {}
    for r, p in S.parts.items():
        if r.startswith(SKIP) or not p.in_bom:
            continue
        by_ref.setdefault(p.reference, p)              # multi-unit parts collapse to one
    groups = {}
    for ref, p in by_ref.items():
        key = (p.value, p.footprint, p.props.get("MPN", ""), p.dnp)
        groups.setdefault(key, []).append(ref)
    out = []
    for (value, fp, mpn, dnp), refs in groups.items():
        p = by_ref[refs[0]]
        out.append(dict(
            refs=sorted(refs, key=_natural),
            qty=len(refs),
            value=value,
            footprint=fp or "",
            mpn=mpn,
            manufacturer=p.props.get("Manufacturer", ""),
            lcsc=p.props.get("LCSC", ""),
            description=p.props.get("Description", ""),
            dnp=dnp,
        ))
    return sorted(out, key=lambda g: _natural(g["refs"][0]))


def cost_report(rows, builds=(10, 100)):
    """
    What the board costs, and -- for a hand-sourced build -- what the CART costs.

    Those are different numbers and the gap is the point. Most 0402 passives carry a
    100-piece minimum, so a ten-board build buys 100 of nearly everything and throws most
    of it away. Unit-price optimisation barely moves the cart; line-item count does.
    """
    prices = json.loads((HERE / "prices.json").read_text())
    spec = prices["_spec_resistor"]
    print("Prices are a %s snapshot -- re-check before ordering.\n" % prices["_snapshot"])
    for build in builds:
        key = "p10" if build <= 10 else "p100"
        board = cart = 0.0
        unpriced = []
        print("=== %d boards " % build + "=" * 46)
        print("  %-24s %3s %9s %9s %8s" % ("LINE", "QTY", "UNIT", "BOARD", "CART"))
        for r in rows:
            if r["dnp"]:
                continue
            pr = prices.get(r["lcsc"]) or prices.get(r["mpn"])
            if pr is None:
                if all(x[0] == "R" for x in r["refs"]):
                    pr = spec
                else:
                    unpriced.append(r); continue
            need = r["qty"] * build
            buy = max(need, pr.get("moq", 1))
            buy = -(-buy // pr.get("moq", 1)) * pr.get("moq", 1)
            b = r["qty"] * pr[key]
            c = buy * pr[key]
            board += b; cart += c
            print("  %-24s %3d %9.4f %9.3f %8.2f%s"
                  % ((",".join(r["refs"]))[:24], r["qty"], pr[key], b, c,
                     "   <- MOQ %d" % pr["moq"] if buy > need else ""))
        print("  %-24s %31s %8.2f" % ("", "parts per board  $%.2f" % board, cart))
        print("  %-24s %31s %8.2f" % ("", "x %d boards      $%.2f" % (build, board * build), cart))
        waste = cart - board * build
        print("  MOQ overbuy on a %d-board run: $%.2f (%.0f%% of the cart)"
              % (build, waste, 100 * waste / cart if cart else 0))
        if unpriced:
            print("  NOT PRICED: %s" % ", ".join(",".join(r["refs"]) for r in unpriced))
        print()
    return 0


def main():
    rows = lines()
    fitted = [r for r in rows if not r["dnp"]]
    if "--csv" in sys.argv:
        path = sys.argv[sys.argv.index("--csv") + 1]
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Refs", "Qty", "Value", "Footprint", "MPN", "Manufacturer",
                        "LCSC", "Description", "DNP"])
            for r in rows:
                w.writerow([",".join(r["refs"]), r["qty"], r["value"], r["footprint"],
                            r["mpn"], r["manufacturer"], r["lcsc"], r["description"],
                            "DNP" if r["dnp"] else ""])
        print("wrote %s (%d lines)" % (path, len(rows)))
        return 0
    if "--jlc" in sys.argv:
        path = sys.argv[sys.argv.index("--jlc") + 1]
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Comment", "Designator", "Footprint", "JLCPCB Part #"])
            for r in fitted:
                w.writerow([r["value"], ",".join(r["refs"]),
                            r["footprint"].split(":")[-1], r["lcsc"]])
        print("wrote %s (%d fitted lines)" % (path, len(fitted)))
        return 0

    if "--cost" in sys.argv:
        return cost_report(rows)

    print("%-26s %3s  %-34s %-20s %s" % ("REFS", "QTY", "VALUE / FOOTPRINT", "MPN", "LCSC"))
    for r in rows:
        refs = ",".join(r["refs"])
        refs = refs if len(refs) <= 26 else refs[:23] + "..."
        print("%-26s %3d  %-34s %-20s %s%s"
              % (refs, r["qty"], "%s  %s" % (r["value"], r["footprint"].split(":")[-1]),
                 r["mpn"] or "-", r["lcsc"] or "-", "   [DNP]" if r["dnp"] else ""))
    print("\n%d distinct line items, %d placements (%d fitted, %d DNP)"
          % (len(rows), sum(r["qty"] for r in rows), sum(r["qty"] for r in fitted),
             sum(r["qty"] for r in rows if r["dnp"])))
    missing = [r for r in fitted if not r["lcsc"] and not r["mpn"]]
    if missing:
        print("%d of %d fitted line items have no part number at all: %s"
              % (len(missing), len(fitted),
                 ", ".join(",".join(r["refs"]) for r in missing)))
    no_lcsc = [r for r in fitted if not r["lcsc"] and r["mpn"]]
    if no_lcsc:
        print("%d sourced by MPN but not stocked at LCSC (consigned / other distributor): %s"
              % (len(no_lcsc), ", ".join(",".join(r["refs"]) for r in no_lcsc)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
