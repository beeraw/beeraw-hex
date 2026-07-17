#!/usr/bin/env python3
"""Complete the Google-Fonts "Latin Core" coverage: draw the 12 missing glyphs
in the monoline hexagonal style and add them to the working UFO.

Full-width strokes (¢ £ ¥ ¨ ´ ¯ ¸) keep the 90 u monoline. Symbols/ordinals
(ª º ® § ¶) are scaled/geometric interpretations — recognisable, on-style, but
the aesthetic of §/¶/® is a designer's call (rough geometric stand-ins).

Usage:  python tools/draw_latin_core.py [ufo]
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ufoLib2
import font_build as fb
from shapely import affinity
from fontTools.pens.qu2cuPen import Qu2CuPen

RW, W, XH, CAP = fb.RW, fb.W, fb.XH, fb.CAP


# ---- currency ------------------------------------------------------------
def cent():
    return fb.U(fb.c(), fb.vbar(RW - W // 2, -70, XH + 70))


def sterling():
    foot = fb.hbar(46, 470, 0)
    stem = fb.vbar(150, 55, 360)
    bowl = fb.ring(fb.cell(240, 520, 150, 160))
    top = bowl.difference(fb.box(240, 300, 500, 560))     # open the curl right
    cross = fb.hbar(96, 366, 292)
    return fb.U(foot, stem, top, cross)


def yen():
    y = fb.Y()
    bars = fb.U(fb.hbar(96, 404, 250), fb.hbar(96, 404, 120))   # two crossbars
    return fb.U(y, bars)


# ---- spacing diacritics (monoline, full stroke) --------------------------
def dieresis():
    return fb._dieresis(180, 470)


def acute():
    return fb._acute(150, 470)


def macron():
    return fb.hbar(40, 320, 560)


def cedilla():
    return fb._cedilla(150)


# ---- ordinals (small superscript letter + underline) ---------------------
def _ordinal(letter_fn):
    small = affinity.scale(letter_fn(), 0.5, 0.5, origin=(0, 0))
    x0, y0, x1, y1 = small.bounds
    small = affinity.translate(small, -x0, 330 - y0)       # raise to superscript
    x0, _, x1, _ = small.bounds
    underline = fb.hbar(round(x0), round(x1), 300)
    return fb.U(small, underline)


def ordfeminine():
    return _ordinal(fb.a)


def ordmasculine():
    return _ordinal(fb.o)


# ---- symbols (geometric interpretations) ---------------------------------
def registered():
    R = 345
    outer = fb.ring(fb.cell(R, fb.CCY, R, R))
    inner = fb.UPPER["R"]()
    x0, y0, x1, y1 = inner.bounds
    s = 370.0 / (y1 - y0)
    inner = affinity.scale(inner, s, s, origin=(0, 0))
    x0, y0, x1, y1 = inner.bounds
    inner = affinity.translate(inner, R - (x0 + x1) / 2, fb.CCY - (y0 + y1) / 2)
    return fb.U(outer, inner)


def section():
    # two opposed alveole rings stacked into an S-spine (geometric §)
    up = fb.ring(fb.cell(200, 470, 130, 150))
    up = up.difference(fb.box(200, 340, 400, 480))         # open lower-right
    lo = fb.ring(fb.cell(200, 230, 130, 150))
    lo = lo.difference(fb.box(0, 220, 200, 360))           # open upper-left
    spine = fb.vbar(200 - W // 2, 200, 500)
    return fb.U(up, lo, spine)


def pilcrow():
    body = fb.box(150, 350, 470, 700)                      # solid top
    return fb.U(body, fb.vbar(150, 0, 700), fb.vbar(380, 0, 700))


# Only the monoline-clean, unambiguous glyphs are shipped. The symbol/ordinal
# builders below (ordfeminine/ordmasculine/registered/section/pilcrow) are kept
# as DRAFTS but left OUT of the shipped set: §/¶/® read poorly as geometric
# stand-ins and ª/º come out too thin — their aesthetic is a designer decision,
# pending the scope call on full GF-Latin-Core expansion (see audit/08-latin-core.md).
GLYPHS = {
    "cent":     (0x00A2, cent,     (40, 30), True),
    "sterling": (0x00A3, sterling, (40, 40), True),
    "yen":      (0x00A5, yen,      (20, 20), True),
    "dieresis": (0x00A8, dieresis, (40, 40), True),
    "macron":   (0x00AF, macron,   (40, 40), True),
    "acute":    (0x00B4, acute,    (40, 40), True),
    "cedilla":  (0x00B8, cedilla,  (40, 40), True),
}
DRAFTS = {   # not shipped — need design sign-off
    "ordfeminine": (0x00AA, ordfeminine),
    "registered":  (0x00AE, registered),
    "paragraph":   (0x00B6, pilcrow),
    "cedilla_": (0x00B8, cedilla),
    "section":     (0x00A7, section),
    "ordmasculine": (0x00BA, ordmasculine),
}


def add_to_ufo(ufo_path):
    ufo = ufoLib2.Font.open(ufo_path)
    order = list(ufo.lib.get("public.glyphOrder", [g.name for g in ufo]))
    for name, (uv, fn, (lsb, rsb), smooth) in GLYPHS.items():
        ttg, adv, xmn, xmx = fb.geom_to_glyph(fn(), lsb, rsb, smooth=smooth)
        if name in ufo:
            del ufo[name]
        g = ufo.newGlyph(name)
        g.unicodes = [uv]
        g.width = adv
        q2c = Qu2CuPen(g.getPen(), 0.1, all_cubic=True, reverse_direction=True)
        ttg.draw(q2c, None)
        if name not in order:
            order.append(name)
        print(f"  + `{name}` U+{uv:04X}  adv={adv}")
    ufo.lib["public.glyphOrder"] = order
    ufo.save(ufo_path, overwrite=True)
    print("saved", ufo_path)


if __name__ == "__main__":
    add_to_ufo(sys.argv[1] if len(sys.argv) > 1 else "sources/BeerawHex-Regular.ufo")
