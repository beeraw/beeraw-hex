#!/usr/bin/env python3
"""Phase 7 — build the final TTF from the working UFO.

  1. compile UFO -> TTF via ufo2ft/cu2qu at the chosen tolerance (1.0 u).
  2. strip Macintosh (platform 1) name records -> fixes universal no_mac_entries.
  3. normalise name ID 5 to "Version 1.000".
  4. autohint with ttfautohint (documented params).

Output: build/BeerawHex-Regular.ttf

Usage:  python tools/build.py [--tol 1.0] [--no-hint]
"""
import os
import argparse
import ufoLib2
from ufo2ft import compileTTF

UPM = 1000
OUT = "build/BeerawHex-Regular.ttf"

# ttfautohint parameters (documented):
#   hinting range 8..48 ppem (display font; below 8 falls back to bytecode-less)
#   --stem-width-mode: nnn = natural stem widths in all 3 modes (gray/GDI/DW),
#     so the 90u monoline is NOT snapped to artificial stems.
#   -f latn : latin fallback script ; -W : windows compatibility off (default)
HINT_PARAMS = dict(hinting_range_min=8, hinting_range_max=48,
                   hinting_limit=0, fallback_script="latn", default_script="latn",
                   # nnn: natural stem widths in all 3 modes -> the 90u monoline
                   # is never snapped to artificial stems.
                   gray_stem_width_mode=-1,
                   gdi_cleartype_stem_width_mode=-1,
                   dw_cleartype_stem_width_mode=-1)


def strip_mac_names(ttf):
    before = len(ttf["name"].names)
    ttf["name"].names = [r for r in ttf["name"].names if r.platformID != 1]
    return before - len(ttf["name"].names)


def fix_version_name(ttf, major, minor):
    vstr = f"Version {major}.{minor:03d}"
    ttf["name"].setName(vstr, 5, 3, 1, 0x409)
    ttf["head"].fontRevision = round(major + minor / 1000.0, 3)
    return vstr


def build(tol, do_hint):
    ufo = ufoLib2.Font.open("sources/BeerawHex-Regular.ufo")
    major = ufo.info.versionMajor or 1
    minor = ufo.info.versionMinor or 0

    # keep the UFO's AGL glyph names (eacute, egrave, ...) rather than rewriting
    # them to uniXXXX production names — the shipped baseline used AGL names.
    ttf = compileTTF(ufo, convertCubics=True,
                     cubicConversionError=tol / UPM,
                     flattenComponents=False,
                     useProductionNames=False)

    n = strip_mac_names(ttf)
    vstr = fix_version_name(ttf, major, minor)

    os.makedirs("build", exist_ok=True)
    unhinted = "build/.unhinted.ttf"
    ttf.save(unhinted)
    print(f"compiled TTF: tol={tol}u  stripped {n} Mac name records  {vstr}")
    print(f"  gasp present: {'gasp' in ttf}   GSUB present: {'GSUB' in ttf}")

    if do_hint:
        from ttfautohint import ttfautohint
        with open(unhinted, "rb") as f:
            data = f.read()
        hinted = ttfautohint(in_buffer=data, **HINT_PARAMS)
        with open(OUT, "wb") as f:
            f.write(hinted)
        # hinted fonts must force integer ppem: head.flags bit 3 (0x0008).
        from fontTools.ttLib import TTFont
        hf = TTFont(OUT)
        hf["head"].flags |= (1 << 3)
        hf.save(OUT)
        print(f"hinted -> {OUT}  (head.flags bit3 set)  params={HINT_PARAMS}")
    else:
        os.replace(unhinted, OUT)
        print(f"unhinted -> {OUT}")
    if os.path.exists(unhinted):
        os.remove(unhinted)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=1.0)
    ap.add_argument("--no-hint", action="store_true")
    args = ap.parse_args()
    build(args.tol, not args.no_hint)
