# Pikkolo Mesh Stick Rev B — placement floor plan

The board is a signal-flow diagram of itself: USB enters at one end, RF leaves at the
other, and everything between sits in the order energy passes through it. Digital
switching lives at the far end of the board from the radio.

```
 mm:  0     6.5      15         27              46              63          75
      |------|--------|----------|---------------|---------------|-----------|
      | 1    | 2      | 3        | 4             | 5             | 6         |
      |tongue| USB    | power    | MCU           | radio         | antenna   |
      |(bare)| U7 R11 | U5 U6    | U1 buck Y1    | U2 Y2 FL1 U4  | C32 R15   |
      |      | C41    | C15 C27  | R1R2 LEDs TPs | + decoupling  | pi(DNP) J1|
```

## Zones

1. **Tongue (0–6.5).** The board edge IS the USB-C plug's paddle card: A row on F.Cu,
   B row on B.Cu, shell pads, 1.4 mm keying notch — all from the JAE DX07P024AJ1 drawing.
   No components; nothing routed here that is not a J2 pad. The 0.5 mm copper-to-edge DRC
   rule must be scoped to except this zone.
2. **USB entry (6.5–15).** U7 hard against the tongue pads, flow-through orientation.
   R11 at A5. C41 local to U7 pin 5.
3. **Power (15–27).** U5 and U6 split across the board width — each can dissipate up to
   ~0.26 W, so they do not share a copper island. Each gets its 4u7 input cap within
   TI's 1 cm rule. U6's output runs right and must arrive at U2 >= 3.30 V at 118 mA:
   >= 0.4 mm wide, nothing else on the rail.
4. **MCU (27–46).** U1 rotated **90° CCW**: the pin 46–60 side (VREG buck, USB,
   QSPI/BOOTSEL) faces LEFT toward power/connector; the pin 16–30 side (SPI1, crystal,
   SWD) faces RIGHT toward the radio. Buck loop C46→L2→C28 immediately left of U1,
   minimal area, VREG_LX kept off the USB pair's edge. One decoupler per supply pin —
   each cap's Description field names its pin. Y1 in the gap right of U1, guarded,
   nothing routed under it. R1/R2 within ~5 mm of U1's USB pins. LEDs + SW1 + TP row on
   the board edges.
5. **Radio (46–63).** U2 rotated **90° CW**: the pin 19–24 side (RFO, RFI_P/N, VR_PA,
   NSS) faces RIGHT into FL1; XTA/DIO3 side faces UP toward Y2; SPI side faces DOWN where
   the bus arrives on L3. Chain U2 → FL1 → U4 dead straight at the board's vertical
   centre. Y2 >= 5 mm from U2's exposed pad (230 mW at TX); C40 within 2 mm of XTA.
   L1 bridges VR_PA to RFO along the top of the corridor. Every RF shunt ground via
   within 0.3 mm of its pad.
6. **Antenna (63–75).** C32 DC block, then the pi lands (R15 = 0R link fitted, C33/C34
   DNP) — the FCC contingency: if the harmonic pre-scan fails, a filter section drops in
   with three parts instead of a respin. J1's five THT barrels carry the SMA mating
   torque; flood ground to the edge and fence the corridor.

## Non-negotiable rules

1. **L2 unbroken under zones 5–6.** The 0.0994 mm prepreg is the reason this board is
   4 layers; one routed trace through that plane undoes the stack-up decision.
2. RF = 0.15 mm grounded coplanar, 0.22 mm gap, fence vias <= 1.5 mm pitch both sides
   (lambda/20 at the 5th harmonic).
3. Exposed pads are U1's and U2's ONLY grounds. Via arrays solid to L2/L4, never relieved.
4. USB pair 0.153/0.211 mm, coupled end to end, no vias, no stubs. R1/R2 at the U1 end.
5. QSPI pins get no copper (bus is live inside the RP2354A package); only QSPI_SS routes,
   to R4/TP5.
6. Bottom side carries only J2's B-row pads. One paste side; J2 hand-fitted after reflow.
7. Fiducials: 3 global + 2 local at U1 (0.4 mm pitch). Panel: 3-up, ~74 × 85 mm, 5 mm
   rails (board alone is under the assembler's 70 × 70 minimum).
8. Stencil 0.12 mm — U1's lead apertures fall below IPC's 0.66 area ratio at 0.15 mm.

## Route in this order

1. Board outline + tongue profile from the JAE drawing (the outline is the first component).
2. Fixed parts: J2, then J1.
3. The complete RF corridor — trace, gaps, fence, shunt vias — while the board is empty.
4. U1 + buck + decoupling + crystal, then the USB pair end to end.
5. SPI/control/power on L3.
6. Pours, stitching, DRC with the J2 edge exception already scoped.

## Do not

- Split or route through L2 under zones 5–6.
- Run anything under Y1/Y2 or between a shunt cap and its via.
- Thermally relieve any EP or RF ground.
- Tidy away C33/C34/R15.
- Touch the USB pair with a stub, via or test point between U7 and R1/R2.
- Shrink or re-tent the EP via arrays — the paste windows are tuned to clear them.
