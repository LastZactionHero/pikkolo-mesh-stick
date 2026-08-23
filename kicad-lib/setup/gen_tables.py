#!/usr/bin/env python3
"""Regenerate KiCad global sym/fp lib tables: stock + personal + esden + impart imports."""
import re, os, pathlib

LIB   = pathlib.Path.home() / "dev" / "kicad-lib"
ESDEN = LIB / "vendor" / "esden"
CFG   = pathlib.Path.home() / "Library/Preferences/kicad/10.0"
OUT   = LIB / ".setup"

STOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/template"
IMPORT_SRCS = ["Samacsys", "Snapeda", "UltraLibrarian", "EasyEDA"]

def esden_names(table, suffix):
    """Names from esden's shipped table, minus entries whose files are absent."""
    txt = (ESDEN / table).read_text()
    names = re.findall(r'\(name "([^"]+)"\)', txt)
    keep = [n for n in names if (ESDEN / (n + suffix)).exists()]
    for n in set(names) - set(keep):
        print(f"  skip (missing): {n}{suffix}")
    return keep

def row(name, uri, descr=""):
    return f'\t(lib (name "{name}") (type "KiCad") (uri "{uri}") (options "") (descr "{descr}"))'

# ---- symbols ----
sym = ['(sym_lib_table', '\t(version 7)',
       f'\t(lib (name "KiCad") (type "Table") (uri "{STOCK}/sym-lib-table") (options "") (descr "KiCad Default Libraries"))',
       row("zach", "${ZLIB}/zach.kicad_sym", "Personal parts")]
for n in esden_names("sym-lib-table", ".kicad_sym"):
    sym.append(row(n, "${ZLIB}/vendor/esden/%s.kicad_sym" % n, "esden pretty-kicad-libs"))
for s in IMPORT_SRCS:
    sym.append(row(s, "${KICAD_3RD_PARTY}/%s.kicad_sym" % s, "impart auto-import"))
sym.append(')')

# ---- footprints ----
fp = ['(fp_lib_table', '\t(version 7)',
      f'\t(lib (name "KiCad") (type "Table") (uri "{STOCK}/fp-lib-table") (options "") (descr "KiCad Default Libraries"))',
      row("zach", "${ZLIB}/zach.pretty", "Personal footprints")]
for n in esden_names("fp-lib-table", ".pretty"):
    fp.append(row(n, "${ZLIB}/vendor/esden/%s.pretty" % n, "esden pretty-kicad-libs"))
for s in IMPORT_SRCS:
    fp.append(row(s, "${KICAD_3RD_PARTY}/%s.pretty" % s, "impart auto-import"))
fp.append(')')

OUT.mkdir(exist_ok=True)
(OUT / "sym-lib-table").write_text("\n".join(sym) + "\n")
(OUT / "fp-lib-table").write_text("\n".join(fp) + "\n")
print(f"staged sym-lib-table: {len(sym)-4} libs")
print(f"staged fp-lib-table : {len(fp)-4} libs")
