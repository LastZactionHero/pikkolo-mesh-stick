#!/usr/bin/env python3
"""
Drawing helpers that sit on top of schlib.

schlib knows how to write KiCad; it does not know what a filter looks like. This is
where the shapes live -- a series chain whose parts butt together into one continuous
wire, a shunt hanging off a node, a parallel branch drawn over the top of a series one.

Connectivity is still carried by the net labels, so a chain that is drawn wrong shows
up in verify_netlist.py as a merged or missing net rather than as a quiet mistake.
"""

PITCH = 15.24          # centre-to-centre for chained parts: 2 x 3.81 pin + 2 x 3.81 stub
HALF = PITCH / 2.0
DROP = 7.62            # a shunt's centre sits this far off the chain line
LIB = {"R": "Device:R", "C": "Device:C", "L": "Device:L"}


class Chain:
    """
    A horizontal run of two-pin parts, drawn as one continuous wire.

        c = Chain(s, x, y, FP)
        c.series("L3", "L", "4n7", "TX2", "RF_TX")
        c.shunt("C23", "C", "1p8", "RF_TX")

    Parts are placed on PITCH so that each pair of facing stubs meets exactly, which is
    what makes the run read as a wire instead of as a column of labels. Only the first
    pin of a joint keeps its label; the second is silenced.
    """

    def __init__(self, sch, x, y, footprints, mirror=False):
        self.s, self.x0, self.y, self.fp = sch, float(x), float(y), footprints
        self.dir = -1 if mirror else 1
        self.angle = 270 if mirror else 90
        self.n = 0
        self.nodes = {}          # net name -> x of the joint that carries it

    # -- geometry -----------------------------------------------------------
    def slot(self, i):
        return self.x0 + self.dir * i * PITCH

    def joint(self, i):
        """x of the wire joint immediately before slot i."""
        return self.slot(i) - self.dir * HALF

    # -- placement ----------------------------------------------------------
    def series(self, ref, kind, val, a, b, **kw):
        """
        One series element, continuing the run.

        A mirrored chain turns each part 270 degrees instead of 90, which puts pin 1 on
        the right. Pin 1 then still faces back up the run, so the joint arithmetic is the
        same in both directions -- only the parts are flipped. Placing them right to left
        without flipping them silently shorts alternate nodes, which is the class of
        mistake verify_netlist.py exists to catch.
        """
        self.s.place(ref, LIB[kind], self.slot(self.n), self.y, value=val,
                     footprint=self.fp[kind], angle=self.angle, **kw)
        self.s.net(a, "%s.1" % ref)
        self.s.net(b, "%s.2" % ref)
        if self.n:
            self.s.quiet_pin("%s.1" % ref)           # the joint already carries a label
        self.nodes.setdefault(a, self.joint(self.n))
        self.nodes[b] = self.joint(self.n + 1)
        self.n += 1
        return self

    def gap(self, n=1):
        self.n += n
        return self

    def shunt(self, ref, kind, val, node, to="GND", **kw):
        """A part from a chain node down to `to`, hanging off the joint carrying it."""
        x = self.nodes[node]
        self.s.place(ref, LIB[kind], x, self.y + DROP, value=val,
                     footprint=self.fp[kind], **kw)
        self.s.net(node, "%s.1" % ref)
        self.s.net(to, "%s.2" % ref)
        self.s.quiet_pin("%s.1" % ref)
        self.s.junction(x, self.y)
        return self

    def parallel(self, ref, kind, val, a, b, above=PITCH, **kw):
        """A part bridging two chain nodes, drawn as a branch over the series run."""
        xa, xb = self.nodes[a], self.nodes[b]
        y = self.y - above
        self.s.place(ref, LIB[kind], (xa + xb) / 2.0, y, value=val,
                     footprint=self.fp[kind], angle=90, **kw)
        self.s.net(a, "%s.1" % ref)
        self.s.net(b, "%s.2" % ref)
        self.s.quiet_pin("%s.1" % ref, "%s.2" % ref)
        self.s.wire((xa, y), (xa, self.y))
        self.s.wire((xb, y), (xb, self.y))
        self.s.junction(xa, self.y)
        self.s.junction(xb, self.y)
        return self

    def tap(self, node, dy, label=True):
        """Drop a bare wire from a chain node, returning the free end's coordinate."""
        x = self.nodes[node]
        self.s.wire((x, self.y), (x, self.y + dy))
        self.s.junction(x, self.y)
        return (x, self.y + dy)
