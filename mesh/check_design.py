#!/usr/bin/env python3
"""
Static design rules for the Pikkolo schematic, checked straight off mesh_design.py.

verify_netlist.py answers "did KiCad build the netlist I meant?".  This answers
"is the netlist I meant a sane board?" -- the things ERC cannot see because they
are about intent: an unresolvable footprint, a net with one pin on it, an IC
supply rail with no decoupling, a BOM line with no part number.

    python3 check_design.py          # human report, exit 1 on any FAIL
    python3 check_design.py --json   # machine readable
"""
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

import schlib                                   # noqa: E402  (path set above)
import mesh_design                              # noqa: E402  (builds the Sch on import)

S = mesh_design.s

# Nets that are legitimately single-pin, or single-pin by construction.
ALLOWED_ONE_PIN = set()

# Supply-pin electrical types that want a decoupling cap on their net.
SUPPLY_ETYPES = {"power_in"}

# Parts that are not real BOM lines.
NON_BOM_PREFIX = ("#PWR", "#FLG", "TP")


def _fp_libs():
    """{libname: path} from the global footprint table, env vars expanded."""
    tbl = schlib.CFG / "fp-lib-table"
    out = {}
    if not tbl.exists():
        return out
    for n, u in re.findall(r'\(name "([^"]+)"\)\s*\(type "[^"]+"\)\s*\(uri "([^"]+)"', tbl.read_text()):
        out[n] = pathlib.Path(schlib._expand(u.replace("${KICAD10_TEMPLATE_DIR}",
                                                       "/usr/share/kicad/template")))
    return out


FP_LIBS = _fp_libs()
STOCK_FP = pathlib.Path(os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))


def resolve_footprint(fp):
    """(ok, detail) for a 'Lib:Name' footprint reference."""
    if not fp:
        return False, "no footprint assigned"
    if ":" not in fp:
        return False, "not in Lib:Name form"
    lib, name = fp.split(":", 1)
    cands = []
    if lib in FP_LIBS:
        cands.append(FP_LIBS[lib])
    cands.append(STOCK_FP / (lib + ".pretty"))
    for d in cands:
        if (d / (name + ".kicad_mod")).exists():
            return True, str(d / (name + ".kicad_mod"))
    if not any(d.is_dir() for d in cands):
        return False, "library '%s' not registered" % lib
    return False, "'%s' not in %s" % (name, lib)


def check():
    res = []          # (level, rule, message)

    def add(level, rule, msg):
        res.append((level, rule, msg))

    nl = S.intended_netlist()
    ref_of = {r: p.reference for r, p in S.parts.items()}
    part_of_ref = {}
    for r, p in S.parts.items():
        part_of_ref.setdefault(p.reference, []).append(p)

    # --- 1. generator's own audit ------------------------------------------
    errs, warns = S.audit()
    for e in errs:
        add("FAIL", "audit", e)
    for w in warns:
        add("WARN", "audit", w)

    # --- 2. footprints resolve ---------------------------------------------
    for r, p in sorted(S.parts.items()):
        if r.startswith(("#PWR", "#FLG")):
            continue
        ok, detail = resolve_footprint(p.footprint)
        if not ok:
            add("FAIL", "footprint", "%s (%s): %s" % (p.reference, p.value, detail))

    # --- 3. no single-pin nets ---------------------------------------------
    for net, nodes in nl.items():
        real = [n for n in nodes if not n.startswith(("#PWR", "#FLG"))]
        if len(real) < 2 and net not in ALLOWED_ONE_PIN:
            add("FAIL", "orphan-net", "net %s has %d real node(s): %s" % (net, len(real), real))

    # --- 4. every supply pin sits on a net that has a cap ------------------
    caps_on = {}
    for net, nodes in nl.items():
        for n in nodes:
            ref = n.split(".")[0]
            if ref.startswith("C"):
                caps_on.setdefault(net, set()).add(ref)
    for r, p in sorted(S.parts.items()):
        if len(p.pins) < 4:                       # discretes and 2-3 pin parts
            continue
        for num, pin in p.pins.items():
            if pin["etype"] not in SUPPLY_ETYPES:
                continue
            if "GND" in pin["name"].upper() or "VSS" in pin["name"].upper():
                continue
            net = next((k for k, v in nl.items() if "%s.%s" % (p.reference, num) in v), None)
            if net is None:
                continue
            if net not in caps_on:
                add("WARN", "decoupling",
                    "%s pin %s (%s) on net %s has no capacitor" % (p.reference, num, pin["name"], net))

    # --- 5. BOM completeness ------------------------------------------------
    need = ("MPN", "Manufacturer")
    for ref in sorted(part_of_ref):
        p = part_of_ref[ref][0]
        if ref.startswith(NON_BOM_PREFIX) or not p.in_bom:
            continue
        missing = [k for k in need if not p.props.get(k)]
        if missing:
            add("WARN", "bom", "%s (%s): missing %s" % (ref, p.value, ", ".join(missing)))

    # --- 6. reference designators are sane ---------------------------------
    for ref in sorted(part_of_ref):
        if ref.startswith(("#PWR", "#FLG")):
            continue
        if not re.match(r"^[A-Z]{1,3}\d+$", ref):
            add("WARN", "refdes", "%s is not a standard reference designator" % ref)

    # --- 7. DNP parts are visible ------------------------------------------
    for ref in sorted(part_of_ref):
        p = part_of_ref[ref][0]
        if p.dnp:
            add("INFO", "dnp", "%s (%s) is marked do-not-populate" % (ref, p.value))

    return res


def main():
    res = check()
    as_json = "--json" in sys.argv
    if as_json:
        print(json.dumps([{"level": a, "rule": b, "message": c} for a, b, c in res], indent=1))
    else:
        order = {"FAIL": 0, "WARN": 1, "INFO": 2}
        for level, rule, msg in sorted(res, key=lambda r: (order[r[0]], r[1])):
            print("  %-4s %-11s %s" % (level, rule, msg))
        n = {k: sum(1 for r in res if r[0] == k) for k in ("FAIL", "WARN", "INFO")}
        print("\n%d parts, %d nets -- %d FAIL, %d WARN, %d INFO"
              % (len([r for r in S.parts if not r.startswith(("#PWR", "#FLG"))]),
                 len(S.intended_netlist()), n["FAIL"], n["WARN"], n["INFO"]))
    return 1 if any(r[0] == "FAIL" for r in res) else 0


if __name__ == "__main__":
    sys.exit(main())
