#!/usr/bin/env python3
"""
One-shot setup for a fresh machine.

Registers this repo's KiCad libraries in KiCad's *global* tables, so the project
opens with every symbol and footprint resolved. Run once after cloning:

    python3 setup.py

KiCad must be fully quit: it rewrites kicad_common.json on exit and would discard
the path variables this writes.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent
LIB = REPO / "kicad-lib"
ESDEN_URL = "https://codeberg.org/esden/pretty-kicad-libs.git"
KVER = os.environ.get("KICAD_VERSION", "10.0")


def first_dir(*cands):
    for c in cands:
        if c and pathlib.Path(c).is_dir():
            return pathlib.Path(c)
    return None


def find_config():
    home = pathlib.Path.home()
    d = first_dir(
        os.environ.get("KICAD_CONFIG_HOME"),
        home / "Library/Preferences/kicad" / KVER,
        pathlib.Path(os.environ.get("APPDATA", "/nonexistent")) / "kicad" / KVER,
        pathlib.Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "kicad" / KVER,
        home / ".config/kicad" / KVER,
    )
    if d is None:
        sys.exit("Could not find the KiCad %s config dir. Launch KiCad once, or set "
                 "KICAD_CONFIG_HOME." % KVER)
    return d


def find_share():
    home = pathlib.Path.home()
    d = first_dir(
        os.environ.get("KICAD_SHARE_DIR"),
        "/Applications/KiCad/KiCad.app/Contents/SharedSupport",
        "/usr/share/kicad", "/usr/local/share/kicad",
        home / ".nix-profile/share/kicad",
        "C:/Program Files/KiCad/%s/share/kicad" % KVER,
        "/app/share/kicad",
    )
    if d is None:
        sys.exit("Could not find KiCad's shared support dir. Set KICAD_SHARE_DIR.")
    return d


def kicad_running():
    try:
        out = subprocess.run(["pgrep", "-fl", "kicad"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return False
    return any("KiCad.app/Contents/MacOS" in l or re.search(r'/(kicad|eeschema|pcbnew)\b', l)
               for l in out.splitlines())


def clone_esden():
    dst = LIB / "vendor" / "esden"
    if (dst / "fp-lib-table").exists():
        print("  esden library already present")
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    print("  cloning esden pretty-kicad-libs (~330MB, one time)...")
    r = subprocess.run(["git", "clone", "--depth", "1", ESDEN_URL, str(dst)],
                       capture_output=True, text=True)
    if r.returncode:
        print("  WARNING: esden clone failed; its libraries will be skipped.")
        print("  ", r.stderr.strip()[:200])
        return None
    return dst


def esden_names(esden, table, suffix):
    if not esden:
        return []
    txt = (esden / table).read_text()
    names = re.findall(r'\(name "([^"]+)"\)', txt)
    return [n for n in names if (esden / (n + suffix)).exists()]


def row(name, uri, descr=""):
    return '\t(lib (name "%s") (type "KiCad") (uri "%s") (options "") (descr "%s"))' % (
        name, uri, descr)


def main():
    if kicad_running():
        sys.exit("ERROR: KiCad is running. Quit it completely, then re-run.")

    cfg, share = find_config(), find_share()
    print("KiCad config : %s" % cfg)
    print("KiCad share  : %s" % share)

    esden = clone_esden()
    imported = LIB / "imported"
    imported.mkdir(exist_ok=True)
    for src in ("Samacsys", "Snapeda", "UltraLibrarian", "EasyEDA"):
        f = imported / (src + ".kicad_sym")
        if not f.exists():
            f.write_text('(kicad_symbol_lib\n\t(version 20241209)\n'
                         '\t(generator "kicad_symbol_editor")\n'
                         '\t(generator_version "9.0")\n)\n')
        (imported / (src + ".pretty")).mkdir(exist_ok=True)

    sym = ['(sym_lib_table', '\t(version 7)',
           row("KiCad", str(share / "template" / "sym-lib-table"), "KiCad Default Libraries")
           .replace('(type "KiCad")', '(type "Table")'),
           row("zach", "${ZLIB}/zach.kicad_sym", "Personal parts")]
    fp = ['(fp_lib_table', '\t(version 7)',
          row("KiCad", str(share / "template" / "fp-lib-table"), "KiCad Default Libraries")
          .replace('(type "KiCad")', '(type "Table")'),
          row("zach", "${ZLIB}/zach.pretty", "Personal footprints")]
    for n in esden_names(esden, "sym-lib-table", ".kicad_sym"):
        sym.append(row(n, "${ZLIB}/vendor/esden/%s.kicad_sym" % n, "esden pretty-kicad-libs"))
    for n in esden_names(esden, "fp-lib-table", ".pretty"):
        fp.append(row(n, "${ZLIB}/vendor/esden/%s.pretty" % n, "esden pretty-kicad-libs"))
    for src in ("Samacsys", "Snapeda", "UltraLibrarian", "EasyEDA"):
        sym.append(row(src, "${KICAD_3RD_PARTY}/%s.kicad_sym" % src, "impart auto-import"))
        fp.append(row(src, "${KICAD_3RD_PARTY}/%s.pretty" % src, "impart auto-import"))
    sym.append(')')
    fp.append(')')

    bak = REPO / "build" / "kicad-config-backup"
    bak.mkdir(parents=True, exist_ok=True)
    for f in ("sym-lib-table", "fp-lib-table", "kicad_common.json"):
        if (cfg / f).exists():
            shutil.copy2(cfg / f, bak / f)
    print("backed up existing tables to %s" % bak)

    (cfg / "sym-lib-table").write_text("\n".join(sym) + "\n")
    (cfg / "fp-lib-table").write_text("\n".join(fp) + "\n")

    common = cfg / "kicad_common.json"
    d = json.loads(common.read_text()) if common.exists() else {}
    env = d.setdefault("environment", {})
    v = env.get("vars") or {}
    v["ZLIB"] = str(LIB)
    v["KICAD_3RD_PARTY"] = str(imported)
    env["vars"] = v
    common.write_text(json.dumps(d, indent=2))

    print("\nregistered %d symbol libs, %d footprint libs" % (len(sym) - 4, len(fp) - 4))
    print("ZLIB            = %s" % LIB)
    print("KICAD_3RD_PARTY = %s" % imported)
    print("\nNow: open mesh/mesh.kicad_pro in KiCad, or regenerate with")
    print("  cd mesh && python3 mesh_design.py && python3 verify_netlist.py")


if __name__ == "__main__":
    main()
