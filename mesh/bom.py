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
    missing = [r for r in fitted if not r["lcsc"]]
    if missing:
        print("%d of %d fitted line items still have no LCSC part number"
              % (len(missing), len(fitted)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
