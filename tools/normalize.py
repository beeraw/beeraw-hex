#!/usr/bin/env python3
"""Deterministic outline normalisation filter for the Beeraw Hex UFO.

Three journalised passes, applied to every outline glyph (composites are left
alone — they carry no points of their own):

  1. Remove consecutive duplicate on-curve points (drop zero-length segments).
  2. Insert missing extrema. For each cubic segment, solve the derivative = 0 on
     x and on y with fontTools.misc.bezierTools.solveQuadratic, then split with
     splitCubicAtT at the interior roots -- but ONLY where the curve overshoots
     the segment's on-curve endpoint box by >= THRESH units (default 2 u), so we
     never add noise. Coordinates are rounded to integers.
  3. Straighten semi-straight lines. A line with |dx| <= 2 and |dy| > 8 is forced
     vertical (dx = 0); |dy| <= 2 and |dx| > 8 is forced horizontal (dy = 0).
     Strict <= 2 gate: anything beyond might be intentional drawing.

Every change is logged (glyph + before/after coords) to a Markdown report.

Usage:  python tools/normalize.py [in.ufo] [out.ufo] [--report FILE]
                                  [--thresh 2.0] [--straighten-dy 8]
"""
import argparse
import ufoLib2
from fontTools.misc.bezierTools import solveQuadratic, splitCubicAtT
from fontTools.pens.recordingPen import RecordingPen


def _round_pt(p):
    return (round(p[0]), round(p[1]))


# --------------------------------------------------------------------------
# contour <-> segment model
#   a contour is: {"start": (x,y), "segs": [(kind, pts...), ...], "closed": bool}
#   kind "L": (end,)              straight line to end
#   kind "C": (c1, c2, end)       cubic
# --------------------------------------------------------------------------
def glyph_to_contours(glyph):
    rec = RecordingPen()
    glyph.draw(rec)
    contours = []
    cur = None
    for op, pts in rec.value:
        if op == "moveTo":
            cur = {"start": pts[0], "segs": [], "closed": False}
            contours.append(cur)
        elif op == "lineTo":
            cur["segs"].append(("L", pts[0]))
        elif op == "curveTo":
            cur["segs"].append(("C", pts[0], pts[1], pts[2]))
        elif op == "qCurveTo":
            cur["segs"].append(("Q",) + tuple(pts))
        elif op == "closePath":
            cur["closed"] = True
        elif op == "endPath":
            cur["closed"] = False
    return contours


def contours_to_glyph(glyph, contours):
    glyph.clearContours()
    pen = glyph.getPen()
    for c in contours:
        pen.moveTo(_round_pt(c["start"]))
        for seg in c["segs"]:
            if seg[0] == "L":
                pen.lineTo(_round_pt(seg[1]))
            elif seg[0] == "C":
                pen.curveTo(_round_pt(seg[1]), _round_pt(seg[2]), _round_pt(seg[3]))
            elif seg[0] == "Q":
                pen.qCurveTo(*[_round_pt(p) for p in seg[1:]])
        if c["closed"]:
            pen.closePath()
        else:
            pen.endPath()


def seg_end(seg):
    return seg[-1]


# --------------------------------------------------------------------------
# pass 1 — dedupe consecutive on-curve points (drop zero-length segments)
# --------------------------------------------------------------------------
def pass_dedupe(contours, gname, log):
    n = 0
    for c in contours:
        new = []
        cur = _round_pt(c["start"])
        for seg in c["segs"]:
            end = _round_pt(seg_end(seg))
            if seg[0] == "L" and end == cur:
                log.append((gname, "dedupe", f"drop zero-length line at {cur}"))
                n += 1
                continue
            if seg[0] == "C" and end == cur and \
               _round_pt(seg[1]) == cur and _round_pt(seg[2]) == cur:
                log.append((gname, "dedupe", f"drop degenerate curve at {cur}"))
                n += 1
                continue
            new.append(seg)
            cur = end
        c["segs"] = new
    return n


# --------------------------------------------------------------------------
# pass 2 — insert missing extrema on cubic segments (deviation >= thresh)
# --------------------------------------------------------------------------
def _cubic_extrema_ts(p0, p1, p2, p3):
    """t values in (0,1) where dx/dt = 0 or dy/dt = 0."""
    ts = set()
    for a0, a1, a2, a3 in ((p0[0], p1[0], p2[0], p3[0]),
                           (p0[1], p1[1], p2[1], p3[1])):
        # derivative of a cubic Bezier = quadratic; coefficients:
        #   B'(t)/3 = A t^2 + B t + C
        A = (a3 - 3 * a2 + 3 * a1 - a0)
        B = 2 * (a2 - 2 * a1 + a0)
        C = (a1 - a0)
        for t in solveQuadratic(A, B, C):
            if isinstance(t, complex):
                continue
            if 1e-4 < t < 1 - 1e-4:
                ts.add(round(t, 6))
    # merge x-root and y-root that fall at (nearly) the same parameter, so we
    # never split twice at one location and coin a coincident point.
    merged = []
    for t in sorted(ts):
        if not merged or t - merged[-1] > 0.02:
            merged.append(t)
    return merged


def _overshoot(p0, p3, pt):
    """How far pt lies outside the [p0,p3] endpoint box, per axis (max)."""
    dev = 0.0
    for axis in (0, 1):
        lo, hi = sorted((p0[axis], p3[axis]))
        if pt[axis] > hi:
            dev = max(dev, pt[axis] - hi)
        elif pt[axis] < lo:
            dev = max(dev, lo - pt[axis])
    return dev


def _eval_cubic(p0, p1, p2, p3, t):
    mt = 1 - t
    return (mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0],
            mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1])


def pass_extrema(contours, gname, log, thresh):
    n = 0
    for c in contours:
        cur = c["start"]
        new = []
        for seg in c["segs"]:
            if seg[0] != "C":
                new.append(seg)
                cur = seg_end(seg)
                continue
            p0, (p1, p2, p3) = cur, (seg[1], seg[2], seg[3])
            ts = _cubic_extrema_ts(p0, p1, p2, p3)
            # keep only extrema that overshoot the endpoint box by >= thresh
            keep = [t for t in ts if _overshoot(p0, p3, _eval_cubic(p0, p1, p2, p3, t)) >= thresh]
            if not keep:
                new.append(seg)
                cur = p3
                continue
            pieces = splitCubicAtT(p0, p1, p2, p3, *keep)
            for piece in pieces:
                _, c1, c2, end = piece
                new.append(("C", c1, c2, end))
            for t in keep:
                ex = _eval_cubic(p0, p1, p2, p3, t)
                log.append((gname, "extrema",
                            f"insert on-curve {_round_pt(ex)} "
                            f"(dev {_overshoot(p0, p3, ex):.2f}u) on seg {_round_pt(p0)}->{_round_pt(p3)}"))
                n += 1
            cur = p3
        c["segs"] = new
    return n


# --------------------------------------------------------------------------
# pass 3 — straighten near-vertical / near-horizontal LINE segments
# --------------------------------------------------------------------------
def pass_straighten(contours, gname, log, max_off=2, min_run=8):
    """Force a line dx=0 when |dx|<=max_off and |dy|>min_run (and transposed).
    Moving the shared endpoint also moves the start of the next segment, which
    is handled because we mutate the point in place in the segment list and the
    contour start when needed."""
    n = 0
    for c in contours:
        # build an explicit node list: node[i] is the on-curve end of seg i-1,
        # node[-1] wraps to start for a closed contour.
        cur = list(c["start"])
        pts = [cur]                       # on-curve nodes, index aligned to segs ends
        for seg in c["segs"]:
            pts.append(list(seg_end(seg)))
        for i, seg in enumerate(c["segs"]):
            if seg[0] != "L":
                continue
            a = pts[i]                    # start node of this line
            b = pts[i + 1]                # end node
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            if 0 < abs(dx) <= max_off and abs(dy) > min_run:
                before = (round(b[0]), round(b[1]))
                b[0] = a[0]               # force vertical
                log.append((gname, "straighten",
                            f"vertical: {before} -> {(round(b[0]),round(b[1]))} "
                            f"(dx {dx:+.0f}, dy {dy:+.0f})"))
                n += 1
            elif 0 < abs(dy) <= max_off and abs(dx) > min_run:
                before = (round(b[0]), round(b[1]))
                b[1] = a[1]               # force horizontal
                log.append((gname, "straighten",
                            f"horizontal: {before} -> {(round(b[0]),round(b[1]))} "
                            f"(dx {dx:+.0f}, dy {dy:+.0f})"))
                n += 1
        # write nodes back: start + each segment endpoint
        c["start"] = tuple(pts[0])
        for i, seg in enumerate(c["segs"]):
            newend = tuple(pts[i + 1])
            c["segs"][i] = seg[:-1] + (newend,)
    return n


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------
def normalize(in_ufo, out_ufo, report_path, thresh=2.0, straighten_dy=8):
    ufo = ufoLib2.Font.open(in_ufo)
    log = []
    counts = {"dedupe": 0, "extrema": 0, "straighten": 0}
    touched = {"dedupe": set(), "extrema": set(), "straighten": set()}

    for glyph in ufo:
        if not len(glyph.contours):
            continue
        contours = glyph_to_contours(glyph)
        d = pass_dedupe(contours, glyph.name, log)
        e = pass_extrema(contours, glyph.name, log, thresh)
        s = pass_straighten(contours, glyph.name, log, min_run=straighten_dy)
        d += pass_dedupe(contours, glyph.name, log)   # safety net after splits
        if d or e or s:
            contours_to_glyph(glyph, contours)
        counts["dedupe"] += d
        counts["extrema"] += e
        counts["straighten"] += s
        if d: touched["dedupe"].add(glyph.name)
        if e: touched["extrema"].add(glyph.name)
        if s: touched["straighten"].add(glyph.name)

    ufo.save(out_ufo, overwrite=True)
    _write_report(report_path, counts, touched, log)
    print(f"normalized UFO -> {out_ufo}")
    print(f"  dedupe: {counts['dedupe']}  extrema: {counts['extrema']}  "
          f"straighten: {counts['straighten']}")
    return counts


def _write_report(path, counts, touched, log):
    L = ["# Phase 3 — corrections déterministes (normalize.py)", "",
         "Filtre appliqué à `sources/BeerawHex-Regular.ufo` (source cubique "
         "reconstruite depuis le TTF).", "",
         "## Récapitulatif", "",
         "| passe | occurrences | glyphes touchés |",
         "|---|---|---|",
         f"| 1. dédoublonnage points consécutifs | {counts['dedupe']} | {len(touched['dedupe'])} |",
         f"| 2. insertion extrema (dev ≥ 2 u) | {counts['extrema']} | {len(touched['extrema'])} |",
         f"| 3. redressement semi-droits (|dx|≤2, |dy|>8) | {counts['straighten']} | {len(touched['straighten'])} |",
         ""]
    for key, title in (("dedupe", "Passe 1 — dédoublonnage"),
                       ("extrema", "Passe 2 — insertion d'extrema"),
                       ("straighten", "Passe 3 — redressement semi-droits")):
        L += [f"## {title}", ""]
        rows = [x for x in log if x[1] == key]
        if not rows:
            L += ["_aucune correction_", ""]
            continue
        L += ["| glyphe | détail |", "|---|---|"]
        for gname, _, detail in rows:
            L.append(f"| `{gname}` | {detail} |")
        L.append("")
    with open(path, "w") as f:
        f.write("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("in_ufo", nargs="?", default="sources/BeerawHex-Regular.ufo")
    ap.add_argument("out_ufo", nargs="?", default="sources/BeerawHex-Regular.ufo")
    ap.add_argument("--report", default="audit/03-corrections.md")
    ap.add_argument("--thresh", type=float, default=2.0)
    ap.add_argument("--straighten-dy", type=float, default=8)
    args = ap.parse_args()
    normalize(args.in_ufo, args.out_ufo, args.report, args.thresh, args.straighten_dy)


if __name__ == "__main__":
    main()
