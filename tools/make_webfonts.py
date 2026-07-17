#!/usr/bin/env python3
"""Derive OTF (CFF) + WOFF2 + WOFF from the built TTF.

TrueType (quadratic) -> OTF (cubic CFF) via qu2cu; then WOFF2 (needs brotli) and
WOFF (zlib). Run after font_build.py. Outputs alongside the TTF in fonts/.

Usage:  python tools/make_webfonts.py
"""
import os
from fontTools.ttLib import TTFont, newTable
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.qu2cuPen import Qu2CuPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.cffLib import CFFFontSet

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "fonts")
TTF = os.path.join(FONTS, "BeerawHex-Regular.ttf")
OTF = os.path.join(FONTS, "BeerawHex-Regular.otf")


def ttf_to_otf(ttf_path, otf_path):
    ttf = TTFont(ttf_path)
    order = ttf.getGlyphOrder()
    glyphSet = ttf.getGlyphSet()
    hmtx = ttf["hmtx"]

    charstrings = {}
    for gn in order:
        adv = hmtx[gn][0]
        t2 = T2CharStringPen(adv, glyphSet)
        q2c = Qu2CuPen(t2, max_err=1.0, all_cubic=True)
        drp = DecomposingRecordingPen(glyphSet)   # flatten composites for CFF
        glyphSet[gn].draw(drp)
        drp.replay(q2c)
        charstrings[gn] = t2.getCharString()

    from fontTools.fontBuilder import FontBuilder
    ps = ttf["name"].getDebugName(6) or "BeerawHex-Regular"
    fb = FontBuilder(ttf["head"].unitsPerEm, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(ttf.getBestCmap())
    fb.setupCFF(ps, {"FullName": ttf["name"].getDebugName(4) or ps}, charstrings, {})
    fb.setupHorizontalMetrics({gn: hmtx[gn] for gn in order})
    hhea = ttf["hhea"]
    fb.setupHorizontalHeader(ascent=hhea.ascent, descent=hhea.descent, lineGap=hhea.lineGap)
    # carry the name table verbatim, and OS/2 + post
    fb.font["name"] = ttf["name"]
    fb.font["OS/2"] = ttf["OS/2"]
    fb.font["post"] = ttf["post"]
    fb.font["post"].formatType = 3.0
    for tag in ("GPOS", "GSUB"):
        if tag in ttf:
            fb.font[tag] = ttf[tag]
    # sync head bits that FontBuilder didn't set from the TTF
    fb.font["head"].fontRevision = ttf["head"].fontRevision
    fb.font["head"].macStyle = ttf["head"].macStyle
    fb.font.save(otf_path)
    return otf_path


def flavor(ttf_path, out_path, flav):
    f = TTFont(ttf_path)
    f.flavor = flav
    f.save(out_path)


def main():
    import sys
    ttf = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else TTF
    outdir = os.path.dirname(ttf)
    stem = os.path.join(outdir, "BeerawHex-Regular")
    if not os.path.exists(ttf):
        raise SystemExit(f"build the TTF first ({ttf})")
    ttf_to_otf(ttf, stem + ".otf")
    print("wrote", stem + ".otf")
    try:
        import brotli  # noqa: F401
        flavor(ttf, stem + ".woff2", "woff2")
        print("wrote", stem + ".woff2")
    except ImportError:
        print("skipped woff2 (pip install brotli)")
    flavor(ttf, stem + ".woff", "woff")
    print("wrote", stem + ".woff")


if __name__ == "__main__":
    main()
