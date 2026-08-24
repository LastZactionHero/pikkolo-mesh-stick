#!/usr/bin/env python3
"""
Does THIS machine have what the project needs?

Run this first after moving to another computer. ready_to_route.py asks whether the
design is sound; this asks whether the toolchain around it resolved -- which is the
question that actually bites when a project moves, because a missing library table does
not announce itself, it just makes every footprint vanish.

    python3 doctor.py

Exit 0 when the project will open and build here.
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

import schlib                                          # noqa: E402

REPO = HERE.parent
results = []


def check(name, ok, detail):
    results.append((ok, name, detail))
    print("  [%s] %-34s %s" % ("ok " if ok else "FAIL", name, detail))
    return ok


def main():
    print("Pikkolo Mesh Stick -- environment check\n")

    cli = shutil.which("kicad-cli")
    for c in ("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
              "/usr/bin/kicad-cli", "C:/Program Files/KiCad/10.0/bin/kicad-cli.exe"):
        if not cli and pathlib.Path(c).exists():
            cli = c
    ver = ""
    if cli:
        try:
            ver = subprocess.run([cli, "--version"], capture_output=True, text=True,
                                 timeout=30).stdout.strip()
        except Exception as e:
            ver = "found but would not run: %s" % e
    check("kicad-cli", bool(cli) and ver.startswith("10"),
          "%s %s" % (cli or "NOT FOUND", ver))

    check("KiCad config dir", schlib.CFG.is_dir(), str(schlib.CFG))
    check("KiCad shared support", schlib.STOCK.parent.is_dir(), str(schlib.STOCK.parent))

    zlib = schlib._vars.get("ZLIB")
    check("ZLIB path variable", bool(zlib) and pathlib.Path(zlib).is_dir(),
          zlib or "NOT SET -- run: python3 setup.py  (with KiCad closed)")
    if zlib and pathlib.Path(zlib).resolve() != (REPO / "kicad-lib").resolve():
        check("ZLIB points at THIS clone", False,
              "%s != %s" % (zlib, REPO / "kicad-lib"))
    else:
        check("ZLIB points at THIS clone", True, str(REPO / "kicad-lib"))

    # --- every library the design actually references must resolve ---------
    try:
        import mesh_design as md
    except Exception as e:
        check("mesh_design.py imports", False, "%s: %s" % (type(e).__name__, e))
        return 1
    check("mesh_design.py imports", True, "%d parts" % len(md.s.parts))

    sym_libs = sorted({p.lib_id.split(":")[0] for p in md.s.parts.values()})
    missing = [n for n in sym_libs if n not in schlib.LIBS or not schlib.LIBS[n].exists()]
    check("symbol libraries resolve", not missing,
          "%d used%s" % (len(sym_libs), "" if not missing else "; MISSING " + ", ".join(missing)))

    import check_design as cd
    bad = []
    for r, p in md.s.parts.items():
        if r.startswith(("#PWR", "#FLG")) or not p.footprint:
            continue
        ok, why = cd.resolve_footprint(p.footprint)
        if not ok:
            bad.append("%s (%s)" % (p.reference, why))
    check("footprints resolve", not bad,
          "%d parts%s" % (len(md.s.parts), "" if not bad else "; " + "; ".join(bad[:4])))

    own = REPO / "kicad-lib"
    check("personal symbol library", (own / "zach.kicad_sym").exists(), str(own / "zach.kicad_sym"))
    mods = sorted((own / "zach.pretty").glob("*.kicad_mod"))
    check("personal footprints", len(mods) >= 4,
          "%d in zach.pretty: %s" % (len(mods), ", ".join(m.stem[:26] for m in mods)))

    bad = sum(1 for ok, _, _ in results if not ok)
    print("\n%s" % ("Environment is ready. Next: python3 ready_to_route.py"
                    if not bad else
                    "%d problem(s). If ZLIB or the libraries are unset, quit KiCad and run "
                    "python3 setup.py from the repo root." % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
