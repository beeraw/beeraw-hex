#!/usr/bin/env python3
"""Reconstruct a cubic UFO from the shipped Beeraw Hex TTF.

The mission's chosen path: the parametric generator is set aside and the UFO
becomes the working source, reconstructed from the binary via qu2cu. We inherit
the TTF's point density (that's the acknowledged cost of this route); the point
of the UFO is to give Phases 3/5/6 a real, editable, fontmake-buildable source.

Faithful reconstruction:
  * quadratic outlines -> cubic via Qu2CuPen (all_cubic, tiny max_err so the
    UFO reproduces the TTF to < 0.1 u).
  * TT winding (CW outer) -> PS winding (CCW outer) via reverse_direction, so
    the UFO obeys the PostScript convention ufo2ft/cu2qu expect on input.
  * composites kept as components (accented letters stay base + mark.comp).
  * unicodes, advance widths, glyph order preserved.
  * a full fontinfo.plist copied from the TTF's head/hhea/OS/2/post/name, with
    the version bumped to 2.001.

Usage:  python tools/ttf_to_ufo.py [in.ttf] [out.ufo]
"""
import sys
import ufoLib2
from fontTools.ttLib import TTFont
from fontTools.pens.qu2cuPen import Qu2CuPen

MAX_ERR = 0.1          # faithful: keep the cubic UFO within 0.1 u of the TTF
NEW_VERSION = (2, 8)   # released version (versionMajor, versionMinor)

# Set rather than copied from the baseline: fontbakery's `license` check wants
# this exact wording (note the colon before the URL) when OFL.txt is present.
OFL_DESCRIPTION = ("This Font Software is licensed under the SIL Open Font "
                   "License, Version 1.1. This license is available with a FAQ "
                   "at: https://openfontlicense.org")


def reverse_unicode_map(ttf):
    rev = {}
    for cp, name in ttf.getBestCmap().items():
        rev.setdefault(name, []).append(cp)
    # include non-BMP / all cmap subtables
    for table in ttf["cmap"].tables:
        for cp, name in table.cmap.items():
            rev.setdefault(name, [])
            if cp not in rev[name]:
                rev[name].append(cp)
    return {n: sorted(set(cps)) for n, cps in rev.items()}


def copy_fontinfo(ufo, ttf):
    head, hhea, os2, post = ttf["head"], ttf["hhea"], ttf["OS/2"], ttf["post"]
    names = {r.nameID: r.toUnicode() for r in ttf["name"].names
             if r.platformID == 3}
    info = ufo.info
    info.unitsPerEm = head.unitsPerEm
    info.familyName = names.get(1, "Beeraw Hex")
    info.styleName = names.get(2, "Regular")
    info.versionMajor, info.versionMinor = NEW_VERSION
    info.copyright = names.get(0)
    info.openTypeNameManufacturer = names.get(8)
    info.openTypeNameDesigner = names.get(9)
    info.openTypeNameLicense = OFL_DESCRIPTION
    info.openTypeNameLicenseURL = names.get(14)
    info.openTypeNameManufacturerURL = names.get(11)
    info.openTypeNameDesignerURL = names.get(12)
    info.trademark = names.get(7)

    # vertical metrics
    info.ascender = os2.sTypoAscender
    info.descender = os2.sTypoDescender
    info.capHeight = os2.sCapHeight
    info.xHeight = os2.sxHeight
    info.openTypeHheaAscender = hhea.ascent
    info.openTypeHheaDescender = hhea.descent
    info.openTypeHheaLineGap = hhea.lineGap
    info.openTypeOS2TypoAscender = os2.sTypoAscender
    info.openTypeOS2TypoDescender = os2.sTypoDescender
    info.openTypeOS2TypoLineGap = os2.sTypoLineGap
    info.openTypeOS2WinAscent = os2.usWinAscent
    info.openTypeOS2WinDescent = os2.usWinDescent

    # OS/2 identity
    info.openTypeOS2WeightClass = os2.usWeightClass
    info.openTypeOS2WidthClass = os2.usWidthClass
    info.openTypeOS2VendorID = os2.achVendID
    info.openTypeOS2Type = []                       # fsType 0 = installable
    info.openTypeOS2Panose = list(os2.panose.__dict__.values())
    # fsSelection bit 7 USE_TYPO_METRICS (bit 6 REGULAR is auto for Regular)
    info.openTypeOS2Selection = [7]
    info.postscriptUnderlinePosition = post.underlinePosition
    info.postscriptUnderlineThickness = post.underlineThickness
    info.styleMapStyleName = "regular"
    info.openTypeHeadFlags = [0, 1]                 # baseline@0, lsb@0


def build(in_ttf, out_ufo):
    ttf = TTFont(in_ttf)
    order = ttf.getGlyphOrder()
    glyphset = ttf.getGlyphSet()
    hmtx = ttf["hmtx"]
    unicodes = reverse_unicode_map(ttf)

    ufo = ufoLib2.Font()
    copy_fontinfo(ufo, ttf)

    n_contours = n_comp = 0
    for name in order:
        glyph = ufo.newGlyph(name)
        glyph.width = hmtx[name][0]
        glyph.unicodes = unicodes.get(name, [])
        pen = glyph.getPen()
        q2c = Qu2CuPen(pen, MAX_ERR, all_cubic=True, reverse_direction=True)
        glyphset[name].draw(q2c)
        if ttf["glyf"][name].isComposite():
            n_comp += 1
        elif ttf["glyf"][name].numberOfContours > 0:
            n_contours += 1

    ufo.lib["public.glyphOrder"] = order
    # persist as default-layer glyph order too
    ufo.save(out_ufo, overwrite=True)
    print(f"UFO written: {out_ufo}")
    print(f"  glyphs: {len(order)}  (outlines: {n_contours}, composites: {n_comp})")
    print(f"  version: {ufo.info.versionMajor}.{ufo.info.versionMinor:03d}")


if __name__ == "__main__":
    in_ttf = sys.argv[1] if len(sys.argv) > 1 else "sources/baseline.ttf"
    out_ufo = sys.argv[2] if len(sys.argv) > 2 else "sources/BeerawHex-Regular.ufo"
    build(in_ttf, out_ufo)
