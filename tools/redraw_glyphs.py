#!/usr/bin/env python3
"""Design overrides for the normalised Regular: re-emit specific glyphs into the
working UFO straight from font_build.py, right after the Latin additions, so
they go through normalize + the monoline gate like any other.

The shapes themselves live in font_build.py and are shared by all eight
masters (they used to be drawn here, which left the Regular with a Z, a tilde
and chevrons the other masters did not have). What remains specific to this
step is the fixed advance some of them must keep in the Regular.

Usage:  python tools/redraw_glyphs.py [ufo]
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ufoLib2
import font_build as fb
from shapely.geometry.polygon import orient
from fontTools.pens.qu2cuPen import Qu2CuPen

# glyph name -> (unicode, shapely builder, (lsb, rsb), mode, fixed_adv)
#   mode "geom" : via geom_to_glyph (round_corners + refit) — for angular shapes.
#   mode "poly" : emit the shapely polygon directly as line segments (bypassing
#                 the refit, which collapses inflecting curves like the tilde).
#   fixed_adv   : preserve the original advance (None = use the computed one).
#                 less/greater MUST stay 412 (googlefonts math_signs_width).
OVERRIDES = {
    "Z":              (0x005A, fb.Z, (34, 34), "geom", None),
    "z":              (0x007A, fb.z, (34, 34), "geom", None),
    "asciitilde":     (0x007E, fb.asciitilde, (46, 46), "geom", None),
    "less":           (0x003C, fb.less, (75, 75), "geom", 412),
    "greater":        (0x003E, fb.greater, (75, 75), "geom", 412),
    "guilsinglleft":  (0x2039, fb.guilsinglleft, (46, 46), "geom", 224),
    "guilsinglright": (0x203A, fb.guilsinglright, (46, 46), "geom", 224),
    "guillemotleft":  (0x00AB, lambda: fb._guill(False), (40, 30), "geom", None),
    "guillemotright": (0x00BB, lambda: fb._guill(True), (30, 40), "geom", None),
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
