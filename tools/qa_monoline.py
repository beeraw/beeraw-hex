#!/usr/bin/env python3
"""Non-regression test for the Beeraw Hex monolinear stroke.

The identity of this font is a strictly monolinear stroke of W = 90 units.
The brief's acceptance criterion #5 requires the *perpendicular* stroke width,
measured by distance transform (NOT a horizontal scan, which overstates
diagonals), to stay inside the p5-p95 band 88.5-91.9 u across the core glyphs.

Method (matches the audit that produced the 88.5-91.9 band):
  1. Rasterise each glyph at 1000 px/em  =>  1 px = 1 font unit.
  2. distance_transform_edt on the filled mask  =>  half-stroke at each pixel.
  3. Keep ridge pixels (local maxima of the distance field); ridge value x2
     is the local stroke width.
  4. Per glyph  =>  median ridge width (its dominant stroke).
  5. Gate: p5-p95 of the per-glyph medians over the CORE set
     (a-z A-Z 0-9) must lie within [MIN, MAX].

Accent marks and guillemets are intentionally thinner (WA = 0.82*W) and are
reported for information but excluded from the gate.

Usage:  python tools/qa_monoline.py [path-to.ttf]
Exit code 0 = pass, 1 = fail (band exceeded).
"""
import sys
import numpy as np
from PIL import ImageFont
from fontTools.ttLib import TTFont
from scipy.ndimage import distance_transform_edt, maximum_filter

# The gate is anchored on the weight's nominal stroke W (90 Regular, 130 Bold),
# which each master stamps into post.underlineThickness. The tolerance band is
# the Regular acceptance window (W-1.5 .. W+1.9) carried across weights, so the
# 90 master keeps its exact historical 88.5-91.9 gate.
BAND_LO, BAND_HI = -1.5, 1.9
# Render 2 px per unit. At 1 px/unit the distance transform quantises stroke
# widths to ~1 u steps: harmless at W=90 (~1 %) but 2.5 % at the UltraLight's
# W=40, where it pushed p95 to a spurious 42.0 and failed the gate on a font
# whose geometry measures a clean 40.0. Oversampling collapses that spread
# (UltraLight p5-p95: 2.00 u -> 0.46 u) without touching the band.
EM = 2000
SCALE = EM / 1000.0
PAD = 16


def nominal_stroke(path):
    """The weight's target stroke, read from post.underlineThickness (== W)."""
    try:
        return float(TTFont(path)["post"].underlineThickness) or 90.0
    except Exception:
        return 90.0

CORE = ("abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789")
ACCENTED = "éèêëàâäîïôöùûüÿçÉÈÊËÀÂÄÎÏÔÖÙÛÜŸ"
OTHER = "œæŒÆ«».,-:/'"


def glyph_median_width(font, ch):
    """Return (median, p5, p95) local stroke width in units for one char, or None."""
    mask = font.getmask(ch, mode="L")
    if mask is None or mask.size[0] == 0 or mask.size[1] == 0:
        return None
    w, h = mask.size
    arr = np.frombuffer(bytes(mask), dtype=np.uint8).reshape((h, w))
    binimg = np.pad(arr > 128, PAD, mode="constant")
    if binimg.sum() == 0:
        return None
    dist = distance_transform_edt(binimg)
    ridge = (dist == maximum_filter(dist, size=3)) & (dist > 1.5)
    vals = dist[ridge] * 2.0 / SCALE        # px -> font units
    if vals.size == 0:
        return None
    return float(np.median(vals)), float(np.percentile(vals, 5)), float(np.percentile(vals, 95))


def main(path):
    font = ImageFont.truetype(path, EM)
    W = nominal_stroke(path)
    band_min, band_max = W + BAND_LO, W + BAND_HI

    def measure(chars):
        out = {}
        for ch in chars:
            r = glyph_median_width(font, ch)
            if r is not None:
                out[ch] = r
        return out

    core = measure(CORE)
    med = np.array([v[0] for v in core.values()])
    p5, p50, p95 = (np.percentile(med, 5), np.percentile(med, 50), np.percentile(med, 95))

    print(f"== Monoline stroke QA  ({path}) ==")
    print(f"core glyphs measured : {len(core)}  (nominal stroke W={W:.0f})")
    print(f"per-glyph median band: p5={p5:.1f}  p50={p50:.1f}  p95={p95:.1f}  (target [{band_min:.1f}, {band_max:.1f}])")

    # widest deviations, for the eye
    dev = sorted(core.items(), key=lambda kv: abs(kv[1][0] - W))[::-1][:6]
    print("most deviant core glyphs:", ", ".join(f"{c}={v[0]:.1f}" for c, v in dev))

    acc = measure(ACCENTED)
    if acc:
        am = np.array([v[0] for v in acc.values()])
        print(f"accented (info only) : median {np.median(am):.1f}  (marks are WA=0.82*W by design)")
    oth = measure(OTHER)
    if oth:
        print("punct/lig (info only):", ", ".join(f"{c}={v[0]:.0f}" for c, v in oth.items()))

    ok = band_min <= p5 and p95 <= band_max
    print("RESULT:", "PASS" if ok else "FAIL — monoline band exceeded")
    return 0 if ok else 1


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "fonts/BeerawHex-Regular.ttf"
    sys.exit(main(path))
