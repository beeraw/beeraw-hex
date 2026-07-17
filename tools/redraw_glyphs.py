#!/usr/bin/env python3
"""Design overrides: redraw specific glyphs in the working UFO, replacing the
reconstructed outlines with new in-style shapes built from font_build.py's
monoline primitives. Runs in the pipeline right after the Latin additions, so
the redrawn glyphs go through normalize + the monoline gate like any other.

  * Z (U+005A) and z (U+007A): given the "7" DNA — a short vertical spur (right
    angle) before the oblique, mirrored at BOTH corners (top-right + bottom-
    left), 180°-symmetric. The spur+oblique+spur is built as ONE bent monoline
    stroke (a buffered centreline with mitre joins) rather than a union of
    overlapping boxes, so the junctions are clean — no bump like the box-union
    version had. Spur heights Z_SPUR / z_SPUR.

Usage:  python tools/redraw_glyphs.py [ufo]
"""
import sys
import os
import math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ufoLib2
import font_build as fb
from shapely.geometry import LineString
from shapely.geometry.polygon import orient
from fontTools.pens.qu2cuPen import Qu2CuPen

W = fb.W
Z_SPUR = 90        # uppercase spur height (the 7 uses 130; this is shorter, both corners)
z_SPUR = 64        # lowercase, scaled to x-height (~90 * XH/CAP)
TILDE_L = 360      # asciitilde wave length
TILDE_A = 66       # asciitilde amplitude


def _bent_Z(half_width, top, drop):
    """Z with a right-angle spur at the top-right and bottom-left, built as one
    bent stroke so the spur/oblique junctions have clean mitres (no bump)."""
    HW, TOP = half_width, top
    # centreline: down the top-right spur, across the oblique, down the bottom-
    # left spur — endpoints sit at the centres of the horizontal bars.
    centre = LineString([
        (2 * HW - W / 2, TOP - W / 2),      # top bar, right
        (2 * HW - W / 2, TOP - W - drop),   # spur bottom (top-right corner)
        (W / 2,          W + drop),         # oblique to bottom-left corner
        (W / 2,          W / 2),            # bottom bar, left
    ])
    stroke = centre.buffer(W / 2, cap_style=2, join_style=2, mitre_limit=12)
    top_bar = fb.hbar(0, 2 * HW, TOP - W)
    bot_bar = fb.hbar(0, 2 * HW, 0)
    return fb.clip(fb.U(top_bar, bot_bar, stroke), 0, TOP)


def Z():
    return _bent_Z(fb.CRW, fb.CAP, Z_SPUR)


def z():
    return _bent_Z(fb.RW, fb.XH, z_SPUR)


def _chev(right, x0, y0, y1, half, w=None):
    """One chevron arm-pair as a single bent stroke (mitre vertex) instead of a
    union of two boxes — clean point, no bump."""
    w = fb.WA if w is None else w
    ym = (y0 + y1) / 2
    pts = ([(x0, y0), (x0 + half, ym), (x0, y1)] if right
           else [(x0 + half, y0), (x0, ym), (x0 + half, y1)])
    return LineString(pts).buffer(w / 2, cap_style=2, join_style=2, mitre_limit=12)


def less():           return _chev(False, 20, fb.CCY - 170, fb.CCY + 170, 240)
def greater():        return _chev(True,  20, fb.CCY - 170, fb.CCY + 170, 240)
def guilsinglleft():  return _chev(False, 20, 175, 385, 100)
def guilsinglright(): return _chev(True,  20, 175, 385, 100)
# the two chevrons of a double guillemet must sit far enough apart that
# round_corners' dilate step (+26 u) does NOT bridge them (needs > ~52 u ink gap).
# x0 20 and 175 (was 135, which welded them) with half 72 gives a clean gap.
def guillemotleft():  return fb.U(_chev(False, 20, 175, 385, 72), _chev(False, 175, 175, 385, 72))
def guillemotright(): return fb.U(_chev(True,  20, 175, 385, 72), _chev(True,  175, 175, 385, 72))


def asciitilde():
    """Smooth monoline wave (one sine period) instead of the old union of straight
    dstroke segments, which bumped at every joint. Buffering a densely sampled
    sine centreline keeps the perpendicular stroke at W (monoline gate)."""
    y, n = fb.CCY, 60
    pts = [(TILDE_L * i / n, y + TILDE_A * math.sin(2 * math.pi * (i / n)))
           for i in range(n + 1)]
    return LineString(pts).buffer(W / 2, cap_style=2, join_style=1, resolution=8)


# glyph name -> (unicode, shapely builder, (lsb, rsb), mode, fixed_adv)
#   mode "geom" : via geom_to_glyph (round_corners + refit) — for angular shapes.
#   mode "poly" : emit the shapely polygon directly as line segments (bypassing
#                 the refit, which collapses inflecting curves like the tilde).
#   fixed_adv   : preserve the original advance (None = use the computed one).
#                 less/greater MUST stay 412 (googlefonts math_signs_width).
OVERRIDES = {
    "Z":              (0x005A, Z, (34, 34), "geom", None),
    "z":              (0x007A, z, (34, 34), "geom", None),
    "asciitilde":     (0x007E, asciitilde, (40, 40), "poly", None),
    "less":           (0x003C, less, (75, 75), "geom", 412),
    "greater":        (0x003E, greater, (75, 75), "geom", 412),
    "guilsinglleft":  (0x2039, guilsinglleft, (46, 46), "geom", 224),
    "guilsinglright": (0x203A, guilsinglright, (46, 46), "geom", 224),
    "guillemotleft":  (0x00AB, guillemotleft, (40, 30), "geom", None),
    "guillemotright": (0x00BB, guillemotright, (30, 40), "geom", None),
}
SIMPLIFY_TOL = 0.8     # polygon point reduction (keeps the wave visually smooth)


def _emit_geom(ufo, name, uv, geom, lsb, rsb, fixed_adv=None):
    ttg, adv, xmn, xmx = fb.geom_to_glyph(geom, lsb, rsb, smooth=True)
    if name in ufo:
        del ufo[name]
    g = ufo.newGlyph(name)
    g.unicodes = [uv]
    g.width = fixed_adv if fixed_adv else adv
    ttg.draw(Qu2CuPen(g.getPen(), 0.1, all_cubic=True, reverse_direction=True), None)
    return g.width


def _emit_poly(ufo, name, uv, geom, lsb, rsb, fixed_adv=None):
    """Draw the shapely polygon straight into the UFO as line segments (CCW
    exterior, PS winding), with sidebearing translation. No refit."""
    g0 = geom.simplify(SIMPLIFY_TOL)
    polys = list(g0.geoms) if g0.geom_type == "MultiPolygon" else [g0]
    minx = min(p.bounds[0] for p in polys)
    maxx = max(p.bounds[2] for p in polys)
    dx = lsb - minx
    if name in ufo:
        del ufo[name]
    g = ufo.newGlyph(name)
    g.unicodes = [uv]
    g.width = round(maxx - minx + lsb + rsb)
    pen = g.getPen()
    for poly in polys:
        poly = orient(poly, sign=1.0)      # CCW exterior (UFO/PS convention)
        for ring in [poly.exterior.coords] + [h.coords for h in poly.interiors]:
            pts = [(round(x + dx), round(y)) for x, y in list(ring)[:-1]]
            pen.moveTo(pts[0])
            for pt in pts[1:]:
                pen.lineTo(pt)
            pen.closePath()
    return g.width


def add_to_ufo(ufo_path):
    ufo = ufoLib2.Font.open(ufo_path)
    for name, (uv, fn, (lsb, rsb), mode, fixed_adv) in OVERRIDES.items():
        emit = _emit_geom if mode == "geom" else _emit_poly
        adv = emit(ufo, name, uv, fn(), lsb, rsb, fixed_adv)
        print(f"  ~ redrawn `{name}` U+{uv:04X}  adv={adv}  ({mode})")
    ufo.save(ufo_path, overwrite=True)
    print("saved", ufo_path)


if __name__ == "__main__":
    add_to_ufo(sys.argv[1] if len(sys.argv) > 1 else "sources/BeerawHex-Regular.ufo")
