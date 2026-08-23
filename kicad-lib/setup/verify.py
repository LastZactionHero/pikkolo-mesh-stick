#!/usr/bin/env python3
"""Smoke-test the KiCad global lib tables: every URI resolves, every sym lib parses."""
import re, json, pathlib, sys

CFG = pathlib.Path.home()/"Library/Preferences/kicad/10.0"
VARS = json.loads((CFG/"kicad_common.json").read_text())["environment"]["vars"]
STOCK = pathlib.Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport")

def expand(uri):
    for k, v in VARS.items():
        uri = uri.replace("${%s}" % k, v)
    return uri

def check(table, kind):
    bad, nsym, nlib = [], 0, 0
    for name, uri in re.findall(r'\(name "([^"]+)"\).*?\(uri "([^"]+)"', (CFG/table).read_text()):
        if name == "KiCad":
            continue
        nlib += 1
        p = pathlib.Path(expand(uri))
        if not p.exists():
            bad.append(f"{name} -> {p}")
            continue
        if kind == "sym":
            nsym += len(re.findall(r'^\t\(symbol "', p.read_text(), re.M))
        else:
            nsym += len(list(p.glob("*.kicad_mod")))
    return nlib, nsym, bad

ok = True
for table, kind, unit in [("sym-lib-table", "sym", "symbols"), ("fp-lib-table", "fp", "footprints")]:
    nlib, n, bad = check(table, kind)
    print(f"{table}: {nlib} libs, {n} {unit}")
    for b in bad:
        ok = False
        print("  BROKEN:", b)

# stock libs, for the total picture
SYMRE = re.compile(r'^\t\(symbol "', re.M)
ssym = sum(len(SYMRE.findall(f.read_text())) for f in (STOCK/"symbols").glob("*.kicad_sym"))
sfp = sum(len(list(d.glob("*.kicad_mod"))) for d in (STOCK/"footprints").glob("*.pretty"))
print("stock: %d symbols, %d footprints" % (ssym, sfp))

sys.exit(0 if ok else 1)
