#!/usr/bin/env python3
"""Render a glyph with its outline + control points, plus a zoom on a fault
region, for the Phase 4 kink analysis. Reads the working UFO (composites are
decomposed so accented letters show their base + mark).

Output per glyph:  <outdir>/<name>.png       full glyph, all points labelled
                   <outdir>/<name>_zoom.png   window around the fault point

Usage:  python tools/render_kinks.py
"""
import os
import math
import ufoLib2
from fontTools.pens.recordingPen import DecomposingRecordingPen
from PIL import Image, ImageDraw, ImageFont

UFO = "sources/BeerawHex-Regular.ufo"
OUTDIR = "audit/04-kinks"

# glyph -> approximate fault coordinate (font units) from the brief
KINKS = {
    "U":            (450, 543),
    "Ugrave":       (450, 543),
    "Ucircumflex":  (450, 543),
    "Udieresis":    (450, 543),
    "braceleft":    (175, 381),
    "braceright":   (122, 319),
}

PX = 900          # canvas size
MARGIN = 70


def flatten_cubic(p0, p1, p2, p3, n=24):
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        pts.append((mt**3*p0[0] + 3*mt**2*t*p1[0] + 3*mt*t**2*p2[0] + t**3*p3[0],
                    mt**3*p0[1] + 3*mt**2*t*p1[1] + 3*mt*t**2*p2[1] + t**3*p3[1]))
    return pts


def get_contours(ufo, name):
    """Return list of contours; each is (nodes, segments) where nodes is the
    list of (x,y,on_curve) points and segments a flattened polyline."""
    rec = DecomposingRecordingPen(ufo)
    ufo[name].draw(rec)
    contours = []
    cur_nodes = None
    cur_flat = None
    cur = None
    for op, pts in rec.value:
        if op == "moveTo":
            cur_nodes = [(pts[0][0], pts[0][1], True)]
            cur_flat = [pts[0]]
            cur = pts[0]
            contours.append((cur_nodes, cur_flat))
        elif op == "lineTo":
            cur_nodes.append((pts[0][0], pts[0][1], True))
            cur_flat.append(pts[0])
            cur = pts[0]
        elif op == "curveTo":
            c1, c2, p3 = pts
            cur_nodes.append((c1[0], c1[1], False))
            cur_nodes.append((c2[0], c2[1], False))
            cur_nodes.append((p3[0], p3[1], True))
            cur_flat.extend(flatten_cubic(cur, c1, c2, p3)[1:])
            cur = p3
        elif op == "closePath":
            if cur_flat and cur_flat[0] != cur_flat[-1]:
                cur_flat.append(cur_flat[0])
    return contours


def render(ufo, name, fault, zoom=False):
    contours = get_contours(ufo, name)
    allpts = [(x, y) for nodes, _ in contours for (x, y, _o) in nodes]
    xs = [p[0] for p in allpts]; ys = [p[1] for p in allpts]
    if zoom:
        win = 130
        x0, x1 = fault[0]-win, fault[0]+win
        y0, y1 = fault[1]-win, fault[1]+win
    else:
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
    span = max(x1-x0, y1-y0) or 1
    scale = (PX - 2*MARGIN) / span

    def T(p):
        return (MARGIN + (p[0]-x0)*scale,
                PX - (MARGIN + (p[1]-y0)*scale))     # y-up -> y-down

    img = Image.new("RGB", (PX, PX), "white")
    d = ImageDraw.Draw(img)
    try:
        fnt = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 15)
        fntS = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 12)
    except Exception:
        fnt = fntS = ImageFont.load_default()

    # baseline + x-height + cap guides
    for gy, lbl in ((0, "base"), (500, "x"), (700, "cap")):
        if y0-5 <= gy <= y1+5:
            yy = T((x0, gy))[1]
            d.line([(0, yy), (PX, yy)], fill=(220, 220, 220))
            d.text((4, yy-16), lbl, fill=(180, 180, 180), font=fntS)

    # filled shape (very light)
    for nodes, flat in contours:
        d.polygon([T(p) for p in flat], fill=(245, 245, 248))
    # outline (flattened) in blue
    for nodes, flat in contours:
        d.line([T(p) for p in flat], fill=(70, 110, 200), width=2)
    # control-point handles (grey) + points
    for nodes, flat in contours:
        prev_on = None
        for (x, y, on) in nodes:
            P = T((x, y))
            if on:
                d.ellipse([P[0]-6, P[1]-6, P[0]+6, P[1]+6], fill=(210, 40, 40))
                if not zoom or True:
                    d.text((P[0]+8, P[1]-6), f"{round(x)},{round(y)}",
                           fill=(140, 20, 20), font=fntS)
            else:
                d.ellipse([P[0]-5, P[1]-5, P[0]+5, P[1]+5],
                          outline=(30, 150, 60), width=2)
                if zoom:
                    d.text((P[0]+7, P[1]-4), f"{round(x)},{round(y)}",
                           fill=(20, 110, 40), font=fntS)

    # fault crosshair
    F = T(fault)
    d.line([(F[0]-18, F[1]), (F[0]+18, F[1])], fill=(240, 140, 0), width=2)
    d.line([(F[0], F[1]-18), (F[0], F[1]+18)], fill=(240, 140, 0), width=2)
    d.text((F[0]+20, F[1]+6), f"fault ~{fault}", fill=(210, 120, 0), font=fnt)

    d.text((10, 10), f"{name}  {'[zoom]' if zoom else '[full]'}",
           fill=(0, 0, 0), font=fnt)
    suffix = "_zoom" if zoom else ""
    path = os.path.join(OUTDIR, f"{name}{suffix}.png")
    img.save(path)
    return path


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    ufo = ufoLib2.Font.open(UFO)
    for name, fault in KINKS.items():
        render(ufo, name, fault, zoom=False)
        render(ufo, name, fault, zoom=True)
        print("rendered", name)


if __name__ == "__main__":
    main()
