#!/usr/bin/env python3
"""
Minimal KiCad 10 schematic writer.

Connectivity is expressed as net names on pins, not as routed wires: every connected
pin gets a short stub with a label on the end. That is deterministic and it is what
makes the generated netlist checkable against the intended one.

Coordinate note: symbol libraries use +Y up, schematics use +Y down. A library pin at
(lx, ly) on a symbol placed at (px, py) with rotation 0 lands at (px + lx, py - ly).
Only rotation 0 is supported, which is all this design needs.
"""
import os
import re
import sys
import json
import pathlib
import uuid as _uuid

NS = _uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")
KVER = os.environ.get("KICAD_VERSION", "10.0")


def _first_dir(*cands):
    for c in cands:
        if c and pathlib.Path(c).is_dir():
            return pathlib.Path(c)
    return None


def _find_config():
    """KiCad's per-user config directory, which holds the library tables."""
    home = pathlib.Path.home()
    d = _first_dir(
        os.environ.get("KICAD_CONFIG_HOME"),
        home / "Library/Preferences/kicad" / KVER,          # macOS
        pathlib.Path(os.environ.get("APPDATA", "/nonexistent")) / "kicad" / KVER,  # Windows
        pathlib.Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "kicad" / KVER,
        home / ".config/kicad" / KVER,                      # Linux
    )
    if d is None:
        sys.exit("Could not find the KiCad %s config directory. Set KICAD_CONFIG_HOME." % KVER)
    return d


def _find_stock():
    """The symbol library that ships with KiCad."""
    home = pathlib.Path.home()
    d = _first_dir(
        os.environ.get("KICAD_SYMBOL_DIR"),
        "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols",   # macOS
        "/usr/share/kicad/symbols",                                       # Linux
        "/usr/local/share/kicad/symbols",
        home / ".nix-profile/share/kicad/symbols",
        "C:/Program Files/KiCad/%s/share/kicad/symbols" % KVER,           # Windows
        "/app/share/kicad/symbols",                                       # Flatpak
    )
    if d is None:
        sys.exit("Could not find KiCad's stock symbols. Set KICAD_SYMBOL_DIR.")
    return d


CFG = _find_config()
STOCK = _find_stock()

_vars = (json.loads((CFG / "kicad_common.json").read_text())
         .get("environment", {}).get("vars") or {})


def _expand(u):
    for k, v in _vars.items():
        u = u.replace("${%s}" % k, v)
    return u


def _load_libs():
    libs = {f.stem: f for f in STOCK.glob("*.kicad_sym")}
    for n, u in re.findall(r'\(name "([^"]+)"\).*?\(uri "([^"]+)"',
                           (CFG / "sym-lib-table").read_text()):
        if n != "KiCad":
            libs[n] = pathlib.Path(_expand(u))
    return libs


LIBS = _load_libs()


def sexp_block(text, start):
    """Return the balanced-paren block that begins at index `start`."""
    d = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            d += 1
        elif text[i] == ")":
            d -= 1
            if d == 0:
                return text[start:i + 1]
    raise ValueError("unbalanced s-expression")


def raw_symbol(lib_id):
    lib, name = lib_id.split(":", 1)
    if lib not in LIBS:
        raise KeyError("no such symbol library: %s" % lib)
    t = LIBS[lib].read_text()
    m = re.search(r'^\t\(symbol "%s"' % re.escape(name), t, re.M)
    if not m:
        raise KeyError("no such symbol: %s" % lib_id)
    return sexp_block(t, m.start() + 1)


def _props(block):
    out = {}
    for m in re.finditer(r'\(property "', block):
        seg = sexp_block(block, m.start())
        k = re.match(r'\(property "([^"]*)"', seg).group(1)
        v = re.match(r'\(property "[^"]*" "((?:[^"\\]|\\.)*)"', seg)
        out[k] = v.group(1) if v else ""
    return out


def _prop_spans(block):
    """{name: (start, end)} for each property sub-block, so whole blocks can be swapped."""
    out = {}
    for m in re.finditer(r'\(property "', block):
        seg = sexp_block(block, m.start())
        k = re.match(r'\(property "([^"]*)"', seg).group(1)
        out[k] = (m.start(), m.start() + len(seg))
    return out


def flat_symbol(lib_id):
    """
    Resolve a symbol to a standalone definition.

    Derived symbols (`extends`) carry no geometry of their own, so the parent's
    graphics and pins are adopted and the child's own properties layered on top.
    A schematic's lib_symbols section has to stand alone, so everything is flattened.
    """
    lib, name = lib_id.split(":", 1)
    blk = raw_symbol(lib_id)
    ext = re.search(r'\(extends "([^"]+)"', blk)
    if ext:
        # A derived symbol overrides whole property blocks, field positions included —
        # copying only the value strings leaves the parent's positions behind and KiCad
        # then flags the cached copy as not matching the library.
        child_spans = _prop_spans(blk)
        child_blocks = {k: blk[a:b] for k, (a, b) in child_spans.items()}
        parent_name = ext.group(1)
        blk = flat_symbol("%s:%s" % (lib, parent_name))
        blk = blk.replace('(symbol "%s"' % parent_name, '(symbol "%s"' % name, 1)
        blk = blk.replace('(symbol "%s_' % parent_name, '(symbol "%s_' % name)
        for k, seg in child_blocks.items():
            spans = _prop_spans(blk)
            if k in spans:
                a, b = spans[k]
                blk = blk[:a] + seg + blk[b:]
            else:                                   # property the parent never had
                spans = _prop_spans(blk)
                a = max(b for _, b in spans.values())
                blk = blk[:a] + "\n\t\t" + seg + blk[a:]
    return blk


def pins(lib_id, unit=None):
    """
    [{num, name, etype, x, y, rot, length, unit}] in library coordinates.

    Sub-symbols are named NAME_<unit>_<bodystyle>; unit 0 holds pins common to every
    unit (typically the power pins). Passing `unit` returns that unit plus unit 0,
    which is what a single placed gate of a multi-unit part actually owns.
    """
    blk = flat_symbol(lib_id)
    name = lib_id.split(":", 1)[1]
    out = []
    for sm in re.finditer(r'\(symbol "%s_(\d+)_(\d+)"' % re.escape(name), blk):
        u = int(sm.group(1))
        sub = sexp_block(blk, sm.start())
        for m in re.finditer(r'\(pin (\w+) (\w+)\s*\(at ([-\d.]+) ([-\d.]+) (\d+)\)\s*\(length ([\d.]+)\)', sub):
            seg = sexp_block(sub, m.start())
            out.append(dict(
                num=re.search(r'\(number "([^"]*)"', seg).group(1),
                name=re.search(r'\(name "([^"]*)"', seg).group(1),
                etype=m.group(1),
                x=float(m.group(3)), y=float(m.group(4)),
                rot=int(m.group(5)), length=float(m.group(6)),
                unit=u,
            ))
    if unit is not None:
        out = [p for p in out if p["unit"] in (0, unit)]
    return out


def unit_count(lib_id):
    blk = flat_symbol(lib_id)
    name = lib_id.split(":", 1)[1]
    us = {int(m.group(1)) for m in re.finditer(r'\(symbol "%s_(\d+)_\d+"' % re.escape(name), blk)}
    return max(us) if us else 1


# library rotation -> unit vector pointing from the connection point toward the body,
# already converted into schematic space (+Y down)
_DIR = {0: (1.0, 0.0), 90: (0.0, -1.0), 180: (-1.0, 0.0), 270: (0.0, 1.0)}


def uid(*parts):
    return str(_uuid.uuid5(NS, "|".join(str(p) for p in parts)))


def _esc(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


class Part:
    def __init__(self, ref, lib_id, x, y, value, footprint, props, dnp, in_bom,
                 unit=1, reference=None):
        self.ref, self.lib_id, self.x, self.y = ref, lib_id, float(x), float(y)
        self.value, self.footprint = value, footprint
        self.props, self.dnp, self.in_bom = props, dnp, in_bom
        self.unit = unit
        # `ref` is this generator's handle; `reference` is what lands on the board, so
        # the two gates of a dual buffer can share U8 while staying separately placeable.
        self.reference = reference or ref
        self.pins = {p["num"]: p for p in pins(lib_id, unit=unit)}
        if not self.pins:
            raise ValueError("%s (%s unit %s) resolved to zero pins" % (ref, lib_id, unit))

    def pin_xy(self, num):
        """Absolute schematic coordinate of a pin's connection point."""
        p = self.pins[num]
        return (round(self.x + p["x"], 4), round(self.y - p["y"], 4))

    def stub_dir(self, num):
        """Unit vector pointing away from the body, for drawing the stub."""
        dx, dy = _DIR[self.pins[num]["rot"]]
        return (-dx, -dy)


class Sch:
    def __init__(self, paper="A2", project="mesh", title=""):
        self.paper, self.project, self.title = paper, project, title
        self.uuid = uid("sheet", project)
        self.parts = {}
        self.conns = []        # (ref, pinnum, net)
        self.ncs = []          # (ref, pinnum)
        self.texts = []        # (x, y, string, size)
        self.boxes = []        # (x, y, w, h)
        self.stub = 3.81

    def place(self, ref, lib_id, x, y, value=None, footprint=None,
              props=None, dnp=False, in_bom=True, unit=1, reference=None):
        if ref in self.parts:
            raise ValueError("duplicate reference %s" % ref)
        # Library pin offsets are multiples of 1.27, so an origin off the 2.54 grid
        # drags every pin on the part off KiCad's connection grid.
        for axis, v in (("x", x), ("y", y)):
            if abs(round(v / 2.54) * 2.54 - v) > 1e-6:
                raise ValueError("%s: %s=%g is not on the 2.54mm grid" % (ref, axis, v))
        p = Part(ref, lib_id, x, y, value, footprint, props or {}, dnp, in_bom,
                 unit=unit, reference=reference)
        self.parts[ref] = p
        return p

    def net(self, net, *pin_refs):
        """net("+3V3", "U1.1", "C3.1") — attach each pin to the named net."""
        for pr in pin_refs:
            ref, num = pr.rsplit(".", 1)
            if ref not in self.parts:
                raise KeyError("no part %s (net %s)" % (ref, net))
            if num not in self.parts[ref].pins:
                raise KeyError("%s has no pin %s (net %s)" % (ref, num, net))
            self.conns.append((ref, num, net))

    def no_connect(self, *pin_refs):
        for pr in pin_refs:
            ref, num = pr.rsplit(".", 1)
            if num not in self.parts[ref].pins:
                raise KeyError("%s has no pin %s" % (ref, num))
            self.ncs.append((ref, num))

    def text(self, x, y, s, size=2.0):
        self.texts.append((x, y, s, size))

    def box(self, x, y, w, h):
        self.boxes.append((x, y, w, h))

    # ---- checks -------------------------------------------------------------

    def audit(self):
        """Return (errors, warnings). Every pin must be netted, NC, or explicitly stacked."""
        errs, warns = [], []
        seen = {}
        for ref, num, net in self.conns:
            seen.setdefault(ref, {})[num] = net
        for ref, num in self.ncs:
            if num in seen.get(ref, {}):
                errs.append("%s.%s is both netted (%s) and no-connect" % (ref, num, seen[ref][num]))
            seen.setdefault(ref, {})[num] = "<NC>"

        for ref, p in sorted(self.parts.items()):
            # pins sharing a coordinate are stacked; one connection covers them all
            bypos = {}
            for num in p.pins:
                bypos.setdefault(p.pin_xy(num), []).append(num)
            for pos, nums in bypos.items():
                hit = [n for n in nums if n in seen.get(ref, {})]
                if not hit:
                    warns.append("%s pin%s %s (%s) left floating"
                                 % (ref, "s" if len(nums) > 1 else "",
                                    ",".join(nums), p.pins[nums[0]]["name"]))
                nets = {seen[ref][n] for n in hit}
                if len(nets) > 1:
                    errs.append("%s stacked pins %s driven to different nets: %s"
                                % (ref, ",".join(nums), sorted(nets)))

        # two different pins landing on the same coordinate across parts = accidental short
        occupied = {}
        for ref, p in self.parts.items():
            for num in p.pins:
                occupied.setdefault(p.pin_xy(num), set()).add(ref)
        for pos, refs in occupied.items():
            if len(refs) > 1:
                errs.append("pins from %s overlap at %s" % (sorted(refs), pos))
        return errs, warns

    def intended_netlist(self):
        """{net: sorted [ref.pin]} — the ground truth to diff the exported netlist against."""
        nl = {}
        for ref, num, net in self.conns:
            nl.setdefault(net, set()).add("%s.%s" % (self.parts[ref].reference, num))
        # stacked pins join implicitly inside KiCad, so record them too
        for ref, p in self.parts.items():
            bypos = {}
            for num in p.pins:
                bypos.setdefault(p.pin_xy(num), []).append(num)
            for pos, nums in bypos.items():
                for net, members in nl.items():
                    if any("%s.%s" % (p.reference, n) in members for n in nums):
                        members.update("%s.%s" % (p.reference, n) for n in nums)
        return {k: sorted(v) for k, v in sorted(nl.items())}

    # ---- emission -----------------------------------------------------------

    def _emit_part(self, p):
        L = []
        A = L.append
        A("\t(symbol")
        A('\t\t(lib_id "%s")' % p.lib_id)
        A("\t\t(at %g %g 0)" % (p.x, p.y))
        A("\t\t(unit %d)" % p.unit)
        A("\t\t(body_style 1)")
        A("\t\t(exclude_from_sim no)")
        A("\t\t(in_bom %s)" % ("yes" if p.in_bom else "no"))
        A("\t\t(on_board yes)")
        A("\t\t(in_pos_files yes)")
        A("\t\t(dnp %s)" % ("yes" if p.dnp else "no"))
        A('\t\t(uuid "%s")' % uid("sym", p.ref, p.unit))

        libprops = _props(flat_symbol(p.lib_id))
        power = "(power global)" in flat_symbol(p.lib_id) or "(power)" in flat_symbol(p.lib_id)
        fields = dict(libprops)
        fields["Reference"] = p.reference
        if p.value is not None:
            fields["Value"] = p.value
        if p.footprint is not None:
            fields["Footprint"] = p.footprint
        fields.update(p.props)

        # Keep visible fields off the stub labels. Two-pin parts are vertical with stubs
        # above and below, so their fields go to the right; bigger parts stack both
        # fields above the body, left-aligned to clear the centred top-pin labels.
        maxx = max((abs(pp["x"]) for pp in p.pins.values()), default=2.54)
        maxy = max((abs(pp["y"]) for pp in p.pins.values()), default=2.54)
        rots = {pp["rot"] for pp in p.pins.values()}
        if len(p.pins) <= 2 and rots <= {90, 270}:
            # vertical two-pin part: stubs run up and down, so the right side is free
            shown = {"Reference": (maxx + 2.54, -1.27), "Value": (maxx + 2.54, 1.27)}
        else:
            # everything else: stack both fields above, clear of the top stubs' labels
            shown = {"Reference": (-maxx, -maxy - 12.7), "Value": (-maxx, -maxy - 10.16)}
        for k, v in fields.items():
            if k.startswith("ki_") or k == "Description":
                hide = True
            else:
                hide = k not in shown
            if power and k in ("Reference",):
                hide = True
            if k in shown and not hide:
                ax, ay = p.x + shown[k][0], p.y + shown[k][1]
            else:
                ax, ay = p.x, p.y
            A('\t\t(property "%s" "%s"' % (k, _esc(v)))
            A("\t\t\t(at %g %g 0)" % (ax, ay))
            if hide:
                A("\t\t\t(hide yes)")
            A("\t\t\t(show_name no)")
            A("\t\t\t(do_not_autoplace no)")
            A("\t\t\t(effects")
            A("\t\t\t\t(font")
            A("\t\t\t\t\t(size 1.27 1.27)")
            A("\t\t\t\t)")
            A("\t\t\t\t(justify left)")
            A("\t\t\t)")
            A("\t\t)")
        for num in p.pins:
            A('\t\t(pin "%s"' % num)
            A('\t\t\t(uuid "%s")' % uid("pin", p.ref, num))
            A("\t\t)")
        A("\t\t(instances")
        A('\t\t\t(project "%s"' % self.project)
        A('\t\t\t\t(path "/%s"' % self.uuid)
        A('\t\t\t\t\t(reference "%s")' % p.reference)
        A("\t\t\t\t\t(unit %d)" % p.unit)
        A("\t\t\t\t)")
        A("\t\t\t)")
        A("\t\t)")
        A("\t)")
        return L

    def render(self):
        L = []
        A = L.append
        A("(kicad_sch")
        A("\t(version 20260306)")
        A('\t(generator "schlib.py")')
        A('\t(generator_version "10.0")')
        A('\t(uuid "%s")' % self.uuid)
        A('\t(paper "%s")' % self.paper)
        if self.title:
            A("\t(title_block")
            A('\t\t(title "%s")' % _esc(self.title))
            A("\t)")

        A("\t(lib_symbols")
        for lib_id in sorted({p.lib_id for p in self.parts.values()}):
            blk = flat_symbol(lib_id)
            name = lib_id.split(":", 1)[1]
            blk = blk.replace('(symbol "%s"' % name, '(symbol "%s"' % lib_id, 1)
            A("\n".join("\t" + ln for ln in blk.split("\n")))
        A("\t)")

        # decorative block outlines and captions
        for (x, y, w, h) in self.boxes:
            A("\t(rectangle")
            A("\t\t(start %g %g)" % (x, y))
            A("\t\t(end %g %g)" % (x + w, y + h))
            A("\t\t(stroke")
            A("\t\t\t(width 0.2)")
            A("\t\t\t(type dash)")
            A("\t\t)")
            A("\t\t(fill")
            A("\t\t\t(type none)")
            A("\t\t)")
            A('\t\t(uuid "%s")' % uid("box", x, y, w, h))
            A("\t)")
        for (x, y, s, size) in self.texts:
            A('\t(text "%s"' % _esc(s))
            A("\t\t(at %g %g 0)" % (x, y))
            A("\t\t(effects")
            A("\t\t\t(font")
            A("\t\t\t\t(size %g %g)" % (size, size))
            A("\t\t\t\t(bold yes)")
            A("\t\t\t)")
            A("\t\t\t(justify left bottom)")
            A("\t\t)")
            A('\t\t(uuid "%s")' % uid("txt", x, y, s))
            A("\t)")

        # one stub + label per netted pin position
        done = set()
        for ref, num, net in self.conns:
            p = self.parts[ref]
            x0, y0 = p.pin_xy(num)
            if (x0, y0) in done:
                continue
            done.add((x0, y0))
            dx, dy = p.stub_dir(num)
            x1, y1 = round(x0 + dx * self.stub, 4), round(y0 + dy * self.stub, 4)
            A("\t(wire")
            A("\t\t(pts")
            A("\t\t\t(xy %g %g) (xy %g %g)" % (x0, y0, x1, y1))
            A("\t\t)")
            A("\t\t(stroke")
            A("\t\t\t(width 0)")
            A("\t\t\t(type default)")
            A("\t\t)")
            A('\t\t(uuid "%s")' % uid("wire", ref, num))
            A("\t)")
            ang = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}[(dx, dy)]
            just = "left" if ang in (0, 90) else "right"
            A('\t(label "%s"' % _esc(net))
            A("\t\t(at %g %g %d)" % (x1, y1, ang))
            A("\t\t(effects")
            A("\t\t\t(font")
            A("\t\t\t\t(size 1.27 1.27)")
            A("\t\t\t)")
            A("\t\t\t(justify %s bottom)" % just)
            A("\t\t)")
            A('\t\t(uuid "%s")' % uid("lbl", ref, num))
            A("\t)")

        for ref, num in self.ncs:
            x0, y0 = self.parts[ref].pin_xy(num)
            A("\t(no_connect")
            A("\t\t(at %g %g)" % (x0, y0))
            A('\t\t(uuid "%s")' % uid("nc", ref, num))
            A("\t)")

        for p in sorted(self.parts.values(), key=lambda z: (z.reference, z.unit)):
            L.extend(self._emit_part(p))

        A("\t(sheet_instances")
        A('\t\t(path "/"')
        A('\t\t\t(page "1")')
        A("\t\t)")
        A("\t)")
        A("\t(embedded_fonts no)")
        A(")")
        return "\n".join(L) + "\n"

    def write(self, path):
        errs, warns = self.audit()
        pathlib.Path(path).write_text(self.render())
        return errs, warns
