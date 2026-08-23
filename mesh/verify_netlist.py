#!/usr/bin/env python3
"""
Diff the netlist KiCad actually exports against the one mesh_design.py intended.

Catches the failure mode that matters most in a generated schematic: a stub that
lands a fraction off-grid, or two labels that quietly merge into one net.
"""
import os
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
def _find_cli():
    """kicad-cli, wherever this platform hides it."""
    import shutil
    for c in [os.environ.get("KICAD_CLI"),
              shutil.which("kicad-cli"),
              "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
              "/usr/bin/kicad-cli", "/usr/local/bin/kicad-cli",
              "C:/Program Files/KiCad/10.0/bin/kicad-cli.exe"]:
        if c and pathlib.Path(c).exists():
            return c
    sys.exit("kicad-cli not found. Set KICAD_CLI.")


CLI = _find_cli()


def exported(sch, out):
    subprocess.run([CLI, "sch", "export", "netlist", "--format", "kicadsexpr",
                    "-o", str(out), str(sch)],
                   check=True, capture_output=True)
    t = out.read_text()
    nets = {}
    for m in re.finditer(r'\(net\s+\(code "\d+"\)\s+\(name "([^"]+)"\)(.*?)\n\t\t\)', t, re.S):
        name = m.group(1).lstrip("/")
        nodes = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(2))
        nets[name] = sorted("%s.%s" % n for n in nodes)
    return nets


def main():
    sch = HERE / "mesh.kicad_sch"
    intended = json.loads((HERE / "intended_netlist.json").read_text())
    (HERE / 'build').mkdir(exist_ok=True)
    got = exported(sch, HERE / "build" / "mesh_verify.net")

    # Power symbols and flags carry no footprint and never appear as netlist nodes.
    drop = re.compile(r'^(#PWR|#FLG)')
    want = {k: [p for p in v if not drop.match(p)] for k, v in intended.items()}
    want = {k: sorted(v) for k, v in want.items() if v}

    bad = 0
    for net in sorted(set(want) | set(got)):
        a, b = want.get(net), got.get(net)
        if a is None:
            # A net KiCad reports that the design never named: only benign if it is a
            # single pin KiCad auto-named (unconnected-*).
            if not net.startswith("unconnected-"):
                print("  EXTRA net %-16s %s" % (net, b)); bad += 1
            continue
        if b is None:
            print("  MISSING net %-16s want %s" % (net, a)); bad += 1
            continue
        if a != b:
            print("  MISMATCH %s" % net)
            print("     want %s" % a)
            print("     got  %s" % b)
            bad += 1

    real = {k: v for k, v in got.items() if not k.startswith("unconnected-")}
    print("\n%d intended nets, %d exported nets, %d discrepancies"
          % (len(want), len(real), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
