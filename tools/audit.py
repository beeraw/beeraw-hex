#!/usr/bin/env python3
"""Structural audit of a Beeraw Hex TTF -> Markdown report.

Reusable acceptance-criteria audit for any TrueType file. Emits a Markdown
report to stdout (redirect to a file), covering:

  * points per glyph (+ total, mean, top-10 heaviest)
  * missing extrema, with the deviation in font units
  * consecutive duplicate points
  * semi-vertical / semi-horizontal straight segments (threshold configurable)
  * signed area and winding direction per contour
  * table inventory, GPOS kern pair count, cmap coverage
  * key vertical metrics + OS/2 / name sanity flags

Usage:
    python tools/audit.py [font.ttf] [--threshold 2.0] [--title "..."]

The threshold (default 2.0 u) governs both the extrema-deviation cutoff and the
semi-straight-segment detection, matching the brief's acceptance criteria.
"""
import argparse
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.areaPen import AreaPen


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------
def _quad_extrema_dev(p0, c, p1):
    """Interior extrema (x and y) of a quadratic segment p0->(control c)->p1.

    Returns the max deviation, in units, by which the curve overshoots the
    on-curve endpoints' bounding box on the axis where an interior extremum
    exists. 0.0 when both extrema fall at (or outside) the endpoints, i.e. the
    on-curve points already bracket the curve so no extremum is missing.
    """
    dev = 0.0
    for axis in (0, 1):
        a0, ac, a1 = p0[axis], c[axis], p1[axis]
        denom = (a0 - 2 * ac + a1)
        if abs(denom) < 1e-9:
            continue
        t = (a0 - ac) / denom
        if not (1e-6 < t < 1 - 1e-6):
            continue
        mt = 1 - t
        val = mt * mt * a0 + 2 * mt * t * ac + t * t * a1
        lo, hi = min(a0, a1), max(a0, a1)
        if val > hi:
            dev = max(dev, val - hi)
        elif val < lo:
            dev = max(dev, lo - val)
    return dev


def _iter_segments(contour):
    """Yield geometric segments from a RecordingPen contour (list of (op, pts)).
    TrueType qCurveTo runs with N off-curve points are expanded into N implied
    quadratic segments. Emits ('line', p0, p1) and ('quad', p0, ctrl, p1)."""
    if not contour:
        return
    start = contour[0][1][-1]
    cur = start
    for op, pts in contour[1:]:
        if op == "lineTo":
            yield ("line", cur, pts[0])
            cur = pts[0]
        elif op == "qCurveTo":
            offs = list(pts)
            on_end = offs.pop()
            if on_end is None:          # all-off-curve contour: closes on start
                on_end = start
            prev = cur
            for i, off in enumerate(offs):
                if i < len(offs) - 1:
                    nxt = offs[i + 1]
                    implied = ((off[0] + nxt[0]) / 2.0, (off[1] + nxt[1]) / 2.0)
                else:
                    implied = on_end
                yield ("quad", prev, off, implied)
                prev = implied
            cur = on_end
        elif op == "curveTo":           # cubic (robustness; not expected in TTF)
            yield ("cubic", cur, pts[0], pts[1], pts[2])
            cur = pts[2]
        elif op == "closePath":
            if cur != start:
                yield ("line", cur, start)


# --------------------------------------------------------------------------
# per-glyph analysis
# --------------------------------------------------------------------------
def analyse_glyph(glyphset, gname, threshold):
    pen = RecordingPen()
    try:
        glyphset[gname].draw(pen)
    except Exception:
        return None
    contours = []
    cur = []
    for op, pts in pen.value:
        if op == "moveTo":
            if cur:
                contours.append(cur)
            cur = [(op, pts)]
        else:
            cur.append((op, pts))
    if cur:
        contours.append(cur)

    info = {
        "n_contours": len(contours),
        "n_points": 0,
        "missing_extrema": [],   # (dev, x, y)
        "dup_points": [],        # (x, y)
        "semi_vert": [],         # (p0, p1, dx, dy)
        "semi_horz": [],
        "areas": [],             # signed area per contour
    }

    for contour in contours:
        # (x, y, on_curve) node list, so we count only *genuine* on-curve
        # duplicates -- coincident on/off points are normal TrueType encoding
        # (a control point tangent at a node) and not a defect.
        raw = []
        for op, pts in contour:
            if op in ("closePath", "endPath", "addComponent"):
                continue
            if op == "moveTo" or op == "lineTo":
                raw.append((round(pts[0][0]), round(pts[0][1]), True))
            elif op == "curveTo":
                raw.append((round(pts[0][0]), round(pts[0][1]), False))
                raw.append((round(pts[1][0]), round(pts[1][1]), False))
                raw.append((round(pts[2][0]), round(pts[2][1]), True))
            elif op == "qCurveTo":
                for p in pts[:-1]:
                    raw.append((round(p[0]), round(p[1]), False))
                if pts[-1] is not None:
                    raw.append((round(pts[-1][0]), round(pts[-1][1]), True))
        info["n_points"] += len(raw)
        # the pen closes a contour by ending on its moveTo point; that trailing
        # coincidence is protocol, not a defect -- drop it before counting dups.
        nodes = raw[:]
        if len(nodes) > 1 and nodes[-1][:2] == nodes[0][:2]:
            nodes.pop()
        if len(nodes) > 1:
            for i in range(len(nodes)):
                a, b = nodes[i], nodes[(i + 1) % len(nodes)]
                if a[:2] == b[:2] and a[2] and b[2]:      # both on-curve
                    info["dup_points"].append(a[:2])

        ap = AreaPen(glyphset)
        try:
            sub = RecordingPen()
            tail = [] if contour[-1][0] == "closePath" else [("closePath", ())]
            sub.value = contour + tail
            sub.replay(ap)
            info["areas"].append(round(ap.value))
        except Exception:
            info["areas"].append(0.0)

        for seg in _iter_segments(contour):
            if seg[0] == "quad":
                dev = _quad_extrema_dev(seg[1], seg[2], seg[3])
                if dev >= threshold:
                    mid = seg[2]
                    info["missing_extrema"].append(
                        (round(dev, 2), round(mid[0]), round(mid[1])))
            elif seg[0] == "line":
                p0, p1 = seg[1], seg[2]
                dx, dy = p1[0] - p0[0], p1[1] - p0[1]
                if 0 < abs(dx) <= threshold and abs(dy) > threshold:
                    info["semi_vert"].append(
                        ((round(p0[0]), round(p0[1])), (round(p1[0]), round(p1[1])),
                         round(dx), round(dy)))
                elif 0 < abs(dy) <= threshold and abs(dx) > threshold:
                    info["semi_horz"].append(
                        ((round(p0[0]), round(p0[1])), (round(p1[0]), round(p1[1])),
                         round(dx), round(dy)))
    return info


def _count_kern_pairs(f):
    if "GPOS" not in f:
        return 0
    gpos = f["GPOS"].table
    if not gpos.LookupList:
        return 0
    n = 0
    for lookup in gpos.LookupList.Lookup:
        if lookup.LookupType != 2:      # 2 = pair adjustment
            continue
        for st in lookup.SubTable:
            fmt = getattr(st, "Format", None)
            if fmt == 1 and getattr(st, "PairSet", None):
                n += sum(ps.PairValueCount for ps in st.PairSet)
            elif fmt == 2:
                n += st.Class1Count * st.Class2Count
    return n


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------
def audit(path, threshold=2.0, title=None):
    f = TTFont(path)
    order = f.getGlyphOrder()
    glyphset = f.getGlyphSet()
    cmap = f.getBestCmap()
    glyf = f["glyf"]

    per = {}
    tot_pts = tot_missing = tot_dup = tot_sv = tot_sh = drawn = 0
    detail = {}
    for gn in order:
        if glyf[gn].isComposite():
            per[gn] = 0
            continue
        info = analyse_glyph(glyphset, gn, threshold)
        if info is None:
            continue
        detail[gn] = info
        per[gn] = info["n_points"]
        tot_pts += info["n_points"]
        if info["n_points"] > 0:
            drawn += 1
        tot_missing += len(info["missing_extrema"])
        tot_dup += len(info["dup_points"])
        tot_sv += len(info["semi_vert"])
        tot_sh += len(info["semi_horz"])

    heaviest = sorted(per.items(), key=lambda kv: -kv[1])[:10]
    mean = tot_pts / drawn if drawn else 0

    head, hhea, os2 = f["head"], f["hhea"], f["OS/2"]
    name_ids = sorted({r.nameID for r in f["name"].names})
    mac_records = [r for r in f["name"].names if r.platformID == 1]
    kern_pairs = _count_kern_pairs(f)

    L = []
    w = L.append
    w(f"# {title or 'Structural audit'} — `{path}`")
    w("")
    w(f"threshold = {threshold} u")
    w("")

    w("## Summary")
    w("")
    w("| metric | value |")
    w("|---|---|")
    w(f"| glyphs (total / drawn) | {len(order)} / {drawn} |")
    w(f"| cmap entries | {len(cmap)} |")
    w(f"| total on+off points | **{tot_pts}** |")
    w(f"| mean points / drawn glyph | **{mean:.1f}** |")
    w(f"| missing extrema (dev ≥ {threshold} u) | **{tot_missing}** |")
    w(f"| consecutive duplicate points | **{tot_dup}** |")
    w(f"| semi-vertical segments | **{tot_sv}** |")
    w(f"| semi-horizontal segments | **{tot_sh}** |")
    w(f"| GPOS kern pairs | {kern_pairs} |")
    for t in ("GSUB", "GPOS", "gasp", "kern"):
        w(f"| table `{t}` | {'present' if t in f else 'absent'} |")
    w(f"| tables | {', '.join(sorted(f.keys()))} |")
    w("")

    w("## Metrics & OS/2")
    w("")
    b7 = bool(os2.fsSelection & (1 << 7))
    b6 = bool(os2.fsSelection & (1 << 6))
    w("| field | value |")
    w("|---|---|")
    w(f"| head yMin / yMax | {head.yMin} / {head.yMax} |")
    w(f"| head macStyle | {head.macStyle} |")
    w(f"| hhea asc/desc/gap | {hhea.ascent} / {hhea.descent} / {hhea.lineGap} |")
    w(f"| OS/2 sTypo A/D/G | {os2.sTypoAscender} / {os2.sTypoDescender} / {os2.sTypoLineGap} |")
    w(f"| OS/2 usWin A/D | {os2.usWinAscent} / {os2.usWinDescent} |")
    w(f"| fsSelection | {bin(os2.fsSelection)} (REGULAR bit6={b6}, USE_TYPO_METRICS bit7={b7}) |")
    w(f"| fsType | {os2.fsType} |")
    w(f"| name IDs present | {name_ids} |")
    w(f"| Macintosh (platformID 1) name records | {len(mac_records)} |")
    w("")

    w("## Heaviest glyphs (top 10 by point count)")
    w("")
    w("| glyph | points |")
    w("|---|---|")
    for gn, n in heaviest:
        w(f"| `{gn}` | {n} |")
    w("")

    w(f"## Missing extrema (deviation ≥ {threshold} u) — {tot_missing} total")
    w("")
    rows = [(gn, i) for gn, i in detail.items() if i["missing_extrema"]]
    rows.sort(key=lambda kv: -len(kv[1]["missing_extrema"]))
    if rows:
        w("| glyph | count | max dev (u) | sample control pts |")
        w("|---|---|---|---|")
        for gn, info in rows:
            devs = info["missing_extrema"]
            mx = max(d[0] for d in devs)
            sample = ", ".join(f"{d[0]}u@({d[1]},{d[2]})" for d in devs[:3])
            w(f"| `{gn}` | {len(devs)} | {mx} | {sample} |")
    else:
        w("_none_")
    w("")

    w(f"## Consecutive duplicate points — {tot_dup} total")
    w("")
    rows = [(gn, i) for gn, i in detail.items() if i["dup_points"]]
    rows.sort(key=lambda kv: -len(kv[1]["dup_points"]))
    if rows:
        w("| glyph | count | coords |")
        w("|---|---|---|")
        for gn, info in rows:
            pts = info["dup_points"]
            coords = ", ".join(f"({x},{y})" for x, y in pts[:5])
            w(f"| `{gn}` | {len(pts)} | {coords} |")
    else:
        w("_none_")
    w("")

    w(f"## Semi-vertical / semi-horizontal segments — {tot_sv} / {tot_sh}")
    w("")
    rows = [(gn, i) for gn, i in detail.items() if i["semi_vert"] or i["semi_horz"]]
    rows.sort(key=lambda kv: -(len(kv[1]["semi_vert"]) + len(kv[1]["semi_horz"])))
    if rows:
        w("| glyph | semi-V | semi-H | sample |")
        w("|---|---|---|---|")
        for gn, info in rows:
            allseg = info["semi_vert"] + info["semi_horz"]
            sample = "; ".join(f"<{p0[0]},{p0[1]}>--<{p1[0]},{p1[1]}>(d={dx},{dy})"
                               for p0, p1, dx, dy in allseg[:2])
            w(f"| `{gn}` | {len(info['semi_vert'])} | {len(info['semi_horz'])} | {sample} |")
    else:
        w("_none_")
    w("")

    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("font", nargs="?", default="fonts/BeerawHex-Regular.ttf")
    ap.add_argument("--threshold", type=float, default=2.0)
    ap.add_argument("--title", default=None)
    args = ap.parse_args()
    print(audit(args.font, args.threshold, args.title))


if __name__ == "__main__":
    main()
