import math
import os
import json
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely import affinity
from shapely.geometry.polygon import orient
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.fontBuilder import FontBuilder
from fontTools.agl import UV2AGL
from fontTools.ttLib import newTable
from fontTools.ttLib.tables.O_S_2f_2 import Panose
from fontTools.ttLib.tables import ttProgram
from fontTools.feaLib.builder import addOpenTypeFeatures
from fontTools.misc.transform import Offset

VERSION = "2.007"       # semantic version; drives name ID 5 and head.fontRevision

# ---- two design axes: WEIGHT (stroke) × WIDTH (proportion) ----
# The monoline IS the ADN, so NEITHER axis touches the perpendicular stroke:
#   * a heavier WEIGHT is just a thicker monoline (W: 90 -> 130);
#   * a WIDER master keeps W and grows the round half-widths (RW/CRW/DRW) and
#     the spacing by a width_factor — counters open, stems stay 90.
# Because every stem is drawn as a fixed-W bar/stroke, widening can't thicken it:
# the monoline gate holds by construction at any width_factor.
#
# Masters ship as RIBBI families: "Beeraw Hex" (Regular+Bold) and the wider
# "Beeraw Hex Wide" (Regular+Bold), width_factor 1.35 (a confident wide that
# stays elegant short of an "extended").
def _master(family, style, stroke, width_factor, weight_class, width_class,
            panose_weight, bold, filename, amp_buf, at_buf):
    return dict(family=family, style=style, stroke=stroke, width_factor=width_factor,
                weight_class=weight_class, width_class=width_class,
                panose_weight=panose_weight, bold=bold, filename=filename,
                amp_buf=amp_buf, at_buf=at_buf)

MASTERS = {
    "Regular":  _master("Beeraw Hex",      "Regular", 90,  1.00, 400, 5, 5, False,
                        "BeerawHex-Regular",     amp_buf=7,  at_buf=0),
    "Bold":     _master("Beeraw Hex",      "Bold",    130, 1.00, 700, 5, 8, True,
                        "BeerawHex-Bold",        amp_buf=32, at_buf=25),
    "Wide":     _master("Beeraw Hex Wide", "Regular", 90,  1.35, 400, 7, 5, False,
                        "BeerawHexWide-Regular", amp_buf=7,  at_buf=0),
    "WideBold": _master("Beeraw Hex Wide", "Bold",    130, 1.35, 700, 7, 8, True,
                        "BeerawHexWide-Bold",    amp_buf=32, at_buf=25),
}
# back-compat alias (older tooling / docs referred to the weight-only table)
WEIGHTS = MASTERS

# ---- vertical metrics (Phase 6) ----
# fontbakery's googlefonts profile (os2_metrics_match_hhea + typoAscender>yMax)
# requires hhea == sTypo, both clearing the ink bounds. So a single unified pair
# drives hhea.ascent, sTypo.ascender AND usWin.ascent, all >= head.yMax (915).
# (This deliberately supersedes the brief's older split-metrics recipe, which
#  the current fontbakery FAILs — normative source over the brief's memo.)
V_ASC  = 960            # >= yMax 915, with margin for accents/overshoots
V_DESC = 260            # >= |yMin| 215

# ================= metrics (font units, y-up, baseline=0) =================
UPM  = 1000
XH   = 500          # x-height
CAP  = 700          # cap height
ASC  = 735          # ascender top (b d f h k l)
DESC = -215         # descender bottom (g j p q y)
W    = 90           # stroke width  (WEIGHT axis: 90 Regular, 130 Bold)
WF   = 1.0          # width factor  (WIDTH axis: 1.00 normal, 1.35 Wide)
SB   = 46           # side bearing

# traced glyphs (& @) are pre-vectorised and can't be re-drawn at the stroke, so
# they're brought up to the current weight by an outward buffer. These knobs are
# reset per master by _apply_master(); the defaults reproduce the Regular master.
AMP_BUF = 7         # ampersand thickening (source drawing sits below the monoline)
AT_BUF  = 0         # arobase thickening (source drawing already at Regular weight)
RAD  = 26           # corner rounding radius
MIT  = dict(join_style=2, mitre_limit=12)
RES  = 6            # buffer resolution for rounded corners

# ---- optical overshoots (Phase 2) ----
# Round/pointed glyphs extend past the flat reference lines so they don't read
# smaller than the flat glyphs. Set to 0 to sit flush on the grid. These move
# the round EXTREMES only; the perpendicular stroke stays 90 u (monoline gate).
OV_LC = 9           # lowercase rounds (o c e a b d g p q, arches of n m h u r)
OV_UC = 11          # capital rounds (O C Q) and round digits (0)
OV_PT = 8           # pointed apices (A V W v w)

# ---------- primitives ----------
SH = 0.58           # cell(): vertical-side half-height as a fraction of rh
                    # (a true constant — never per-master, safe as a default arg)

def cell(cx, cy, rh, rw, sh=SH, topf=0.42):
    """alveole: flat top/bottom, vertical sides, bevelled corners (zero point)."""
    tf = rw * topf
    return Polygon([
        (cx - tf, cy + rh), (cx + tf, cy + rh),        # flat top
        (cx + rw, cy + sh * rh), (cx + rw, cy - sh * rh),  # right vertical
        (cx + tf, cy - rh), (cx - tf, cy - rh),        # flat bottom
        (cx - rw, cy - sh * rh), (cx - rw, cy + sh * rh),  # left vertical
    ])

def ring(c):
    return c.difference(c.buffer(-W, **MIT))

def flat_left_cell(cx, cy, rh, rw):
    # alveole cell but with a straight vertical left side (no bevels on the left)
    return U(cell(cx, cy, rh, rw), box(cx - rw, cy - rh, cx, cy + rh))

def vbar(xl, y0, y1):
    return box(xl, y0, xl + W, y1)

def hbar(x0, x1, yb):
    return box(x0, yb, x1, yb + W)

def dstroke(p0, p1, w=None):
    # resolved at call time, not bound at import (W changes per master)
    w = W if w is None else w
    ang = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
    length = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    s = box(0, -w / 2, length, w / 2)
    s = affinity.rotate(s, ang, origin=(0, 0))
    return affinity.translate(s, p0[0], p0[1])

def clip(g, ylo, yhi):
    return g.intersection(box(-3000, ylo, 6000, yhi))

def U(*parts):
    return unary_union(list(parts))

def dot(cx, cy, r):
    return cell(cx, cy, r, r, sh=0.5, topf=0.55)

# ================= lowercase =================
RW = 200            # x-height round half-width

def a():
    cx = RW
    bowl = cell(cx, 250, 250 + OV_LC, RW)
    stem = vbar(2 * RW - W, 0, XH)
    return U(bowl, stem).difference(bowl.buffer(-W, **MIT))

def b():
    cx = RW
    bowl = cell(cx, 250, 250 + OV_LC, RW)
    stem = vbar(0, 0, ASC)
    return U(stem, bowl).difference(bowl.buffer(-W, **MIT))

def d():
    cx = RW
    bowl = cell(cx, 250, 250 + OV_LC, RW)
    stem = vbar(2 * RW - W, 0, ASC)
    return U(stem, bowl).difference(bowl.buffer(-W, **MIT))

def p():
    cx = RW
    bowl = cell(cx, 250, 250 + OV_LC, RW)
    stem = vbar(0, DESC, XH)
    return U(stem, bowl).difference(bowl.buffer(-W, **MIT))

def q():
    cx = RW
    bowl = cell(cx, 250, 250 + OV_LC, RW)
    stem = vbar(2 * RW - W, DESC, XH)
    return U(stem, bowl).difference(bowl.buffer(-W, **MIT))

def o():
    return ring(cell(RW, 250, 250 + OV_LC, RW))

def _aperture(rh, k):
    """Mouth half-height for the C/c family, bounded by BOTH limits:

      * the counter (rh - W)  — a fixed mouth overflows it as soon as the wall
        thickens (Bold: counter 129 vs the old hard-coded 150) and starts biting
        into the ring's top/bottom bars, which is what made the terminals
        protrude and mismatch;
      * the cell's vertical-side span (SH * rh) — keeps the cut inside the
        straight wall, so the terminal is a clean vertical face and the letter
        keeps its full width at every weight (bounding by the counter alone made
        the Regular c 360 u wide against the Bold's 398).
    """
    return min(SH * rh, rh - W) * k

AP_LC = 0.96        # lowercase c
AP_UC = 0.81        # uppercase C (170 / 209.4)

def c():
    rh = 250 + OV_LC
    g = ring(cell(RW, 250, rh, RW))
    ap = _aperture(rh, AP_LC)
    mouth = box(RW + 20, 250 - ap, 2 * RW + 30, 250 + ap)
    return g.difference(mouth)

def e():
    rh = 250 + OV_LC
    outer = cell(RW, 250, rh, RW)
    g = U(ring(outer), box(0, 250 - W / 2, 2 * RW, 250 + W / 2))
    # Same bounded aperture as the c: a fixed 150 dropped below the counter once
    # the wall thickened (Bold: counter bottom 121 vs mouth bottom 100) and cut
    # into the bottom arc, leaving a burr on the terminal. Sharing AP_LC also
    # puts the e's terminal at exactly the c's height.
    ap = _aperture(rh, AP_LC)
    mouth = box(RW - 10, 250 - ap, 2 * RW + 30, 250 - W / 2)
    return g.difference(mouth)

def n():
    outer = cell(RW, 250, 250 + OV_LC, RW)
    arch = clip(ring(outer), 250, XH + OV_LC)
    left = vbar(0, 0, XH)                 # main stem: flat top may overshoot (ok)
    right = vbar(2 * RW - W, 0, 250 + W)  # capped by arch (no overshoot)
    return U(arch, left, right)

def h():
    outer = cell(RW, 250, 250 + OV_LC, RW)
    arch = clip(ring(outer), 250, XH + OV_LC)
    return U(arch, vbar(0, 0, ASC), vbar(2 * RW - W, 0, 250 + W))

def m():
    o1 = cell(RW, 250, 250 + OV_LC, RW)
    o2 = cell(3 * RW - W, 250, 250 + OV_LC, RW)
    arch1 = clip(ring(o1), 250, XH + OV_LC)
    arch2 = clip(ring(o2), 250, XH + OV_LC)
    left = vbar(0, 0, XH)                       # main stem: overshoot ok
    mid = vbar(2 * RW - W, 0, 250 + W)          # capped
    right = vbar(4 * RW - 2 * W, 0, 250 + W)    # capped
    return U(arch1, arch2, left, mid, right)

def u():
    outer = cell(RW, 250, 250 + OV_LC, RW)
    arch = clip(ring(outer), -OV_LC, 250)
    left = vbar(0, 250, XH)               # capped by arch below (no overshoot)
    right = vbar(2 * RW - W, 0, XH)       # main stem: flat bottom may overshoot (ok)
    return U(arch, left, right)

def r():
    stem = vbar(0, 0, XH)
    tf = RW * 0.42
    shoulder = clip(ring(cell(RW, 250, 250 + OV_LC, RW)), 250, XH + OV_LC)  # top arch, like n
    shoulder = shoulder.intersection(box(-3000, 250, RW + tf, XH + 3000))  # left+top, stop before it redescends
    return U(stem, shoulder)

def i():
    return U(vbar(0, 0, XH), dot(W / 2, XH + 120, W / 2))

def j():
    stem = vbar(RW - W, DESC + 90, XH)
    hook = hbar(20, RW, DESC)
    return U(stem, hook, dot(RW - W / 2, XH + 120, W / 2))

def l():
    return vbar(0, 0, ASC)

def f():
    fx = 90
    stem = vbar(fx, 0, ASC)
    arm = hbar(fx, fx + round(220 * WF), ASC - W)   # abrupt right-angle top (like the foot of j)
    cross = hbar(-10, fx + round(195 * WF), XH - W / 2)  # arm reach follows the WIDTH axis
    return U(stem, arm, cross)

def t():
    stem = vbar(90, 0, XH + 160)
    cross = hbar(-10, round(320 * WF), XH - W / 2)   # crossbar & foot widen with the master
    foot = hbar(90, 90 + round(150 * WF), 0)
    return U(stem, cross, foot)

def k():
    stem = vbar(0, 0, ASC)                       # full ascender height, like l
    arm = dstroke((W, XH * 0.5), (W + RW, XH), W)
    leg = dstroke((W, XH * 0.5), (W + RW, 0), W)
    diag = clip(U(arm, leg), 0, XH)              # clip only the diagonals, not the stem
    return U(stem, diag)

def v():
    mid = RW
    g = U(dstroke((0, XH), (mid, -30), W), dstroke((2 * mid, XH), (mid, -30), W))
    return clip(g, -OV_PT, XH)

def w_():
    dx = RW * 0.72          # narrower
    OV = 24
    P = [(0, XH + OV), (dx, -OV), (2 * dx, XH * 0.60), (3 * dx, -OV), (4 * dx, XH + OV)]  # higher middle
    g = U(*[dstroke(P[k], P[k + 1], W) for k in range(4)])
    return clip(g, -OV_PT, XH)

def x():
    g = U(dstroke((0, XH), (2 * RW, 0), W), dstroke((0, 0), (2 * RW, XH), W))
    return clip(g, 0, XH)

def y():
    mid = RW
    left = dstroke((0, XH), (mid, 150), W)
    right = dstroke((2 * mid, XH), (mid - RW, DESC), W)
    return clip(U(left, right), DESC, XH)

def z():
    top = hbar(0, 2 * RW, XH - W)
    bot = hbar(0, 2 * RW, 0)
    diag = dstroke((2 * RW - W / 2, XH - W / 2), (W / 2, W / 2), W)
    return clip(U(top, bot, diag), 0, XH)

def _s_shape(rw, ty, by, ov=0):
    h = ty - by
    # The bowl must keep a real counter. h*0.33 is a pure proportion, so at Bold
    # the 130 u wall eats it down to ~35 u: the inner octagon degenerates into
    # nothing but bevels and the two apertures come out stair-stepped and
    # mismatched. Floor the bowl so the counter never drops below the Regular's
    # 75 u — this leaves the Regular s / S / $ untouched (their proportion
    # already wins) and only opens up the bold lowercase s.
    bh = max(h * 0.33, W + 75)
    cx = rw
    # overshoot: translate the top/bottom bowls out by ov (radius, hence the
    # 90 u stroke, is unchanged); the spine join at midy stays put.
    ucy = ty - bh + ov
    lcy = by + bh - ov
    midy = (ty + by) / 2
    # Each aperture is the union of the bowl's counter and the box that opens it,
    # so the box edge must land exactly on the counter's edge (ucy + bh - W) or
    # the two leave a step. The old bh*0.45 only matched by luck at Regular, where
    # (bh-W)/bh = 0.4545; at Bold it drifts to 0.37 and stair-steps the terminals.
    inner = bh - W                                    # counter half-height
    # top arc: keep the LEFT half of the upper bowl + a short top-right terminal
    up = ring(cell(cx, ucy, bh, rw))
    up = up.difference(box(cx, midy, 2 * rw + 60, ucy + inner))       # open the middle-right (keep top curl)
    up = clip(up, midy - W / 2, ty + ov + 60)                        # clip at the spine, no hanging nub
    # bottom arc: mirror
    lo = ring(cell(cx, lcy, bh, rw))
    lo = lo.difference(box(-60, lcy - inner, cx, midy))               # open the middle-left (keep bottom curl)
    lo = clip(lo, by - ov - 60, midy + W / 2)
    mid = box(0, midy - W / 2, 2 * rw, midy + W / 2)
    return U(up, lo, mid)

def s():
    return _s_shape(RW, XH, 0, OV_LC)

# ================= UPPERCASE (cap height) =================
CH = CAP
CRW = 250           # cap round half-width
CCY = CAP / 2

def C_ring(rw=None):
    # NB: resolve CRW at CALL time. As a default argument it would be bound once
    # at import (CRW=250), so O and C would keep the normal width in every Wide
    # master while every other cap widened.
    rw = CRW if rw is None else rw
    return ring(cell(rw, CCY, CCY + OV_UC, rw))

def A():
    apex = CRW
    diag = U(dstroke((0, 0), (apex, CAP + 20), W),
             dstroke((2 * apex, 0), (apex, CAP + 20), W))
    # The crossbar is trimmed to the legs' own silhouette (their convex hull), so
    # its ends land flush on the diagonals instead of poking out. A fixed x-range
    # would protrude as soon as the legs splay (wide) or thicken (bold), because
    # the legs sit further in at the bar's TOP edge than at its bottom.
    bar = hbar(-200, 2 * apex + 200, CAP * 0.34).intersection(diag.convex_hull)
    return clip(U(diag, bar), 0, CAP + OV_PT)

def B():
    mid = CCY
    mb2 = W * 0.42                # half of the middle bar (=> ~0.84*W, only slightly thinner)
    urw, lrw = CRW * 0.92, CRW    # upper bowl a touch narrower
    # two bowls: bevelled (curved) on the RIGHT, flat only on the LEFT
    uy0 = mid + mb2 - W
    ub = U(cell(urw, (uy0 + CAP) / 2, (CAP - uy0) / 2, urw), box(0, uy0, urw, CAP))
    ly1 = mid - mb2 + W
    lb = U(cell(lrw, ly1 / 2, ly1 / 2, lrw), box(0, 0, lrw, ly1))
    outer = U(vbar(0, 0, CAP), ub, lb)
    return outer.difference(ub.buffer(-W, **MIT)).difference(lb.buffer(-W, **MIT))

# The C's bowl relative to the O's. An open shape reads narrower than a closed
# one at equal width, so the C is drawn 6 % wider to sit optically level with the
# O (500 -> 530 u at Regular). Classic optical correction, not a metric one.
C_WIDE = 1.06

def C():
    rw = CRW * C_WIDE
    rh = CCY + OV_UC
    g = C_ring(rw)
    ap = _aperture(rh, AP_UC)                  # weight-safe aperture, like the c
    return g.difference(box(rw + 20, CCY - ap, 2 * rw + 30, CCY + ap))

def D():
    base = cell(CRW, CCY, CCY, CRW)
    flat_left = box(0, 0, CRW, CAP)          # square off the left half (no alveole on left)
    outer = U(base, flat_left)
    return ring(outer)

def E():
    return U(vbar(0, 0, CAP), hbar(0, 2 * CRW - 40, CAP - W), hbar(0, 2 * CRW - 40, 0),
             hbar(0, 2 * CRW - 90, CCY - W / 2))

def F():
    return U(vbar(0, 0, CAP), hbar(0, 2 * CRW - 40, CAP - W), hbar(0, 2 * CRW - 90, CCY - W / 2))

def G():
    ov = OV_UC                                                    # whole top crown overshoots together
    base = cell(CRW, CCY, CCY + ov, CRW)
    tf = CRW * 0.42
    base = U(base, box(CRW + tf, CCY + 0.58 * CCY, 2 * CRW, CAP + ov))  # square top-right follows the crown
    g = ring(base)
    g = g.difference(box(CRW + 40, CCY + 20, 2 * CRW + 40, CAP - W + ov))  # aperture below the raised top bar
    g = g.difference(box(2 * CRW - 38, CAP - W - 6, 2 * CRW + 60, CAP + 60 + ov))  # top bar a chouillat shorter
    bar = hbar(CRW + 10, 2 * CRW, CCY - W / 2)                     # inner crossbar
    spur = vbar(2 * CRW - W, CCY - W / 2, CCY + 40)                # short spur closing the jaw
    return U(g, bar, spur)

def H():
    return U(vbar(0, 0, CAP), vbar(2 * CRW - W, 0, CAP), hbar(0, 2 * CRW, CCY - W / 2))

def I():
    return vbar(0, 0, CAP)

def J():
    jw = CRW * 0.86
    rh = CAP * 0.30
    cy = rh
    hook = clip(ring(cell(jw, cy, rh, jw)), 0, cy)   # curved (bevelled) bottom, like the U
    stem = vbar(2 * jw - W, cy - W, CAP)             # right stem to the top
    return U(hook, stem)

def K():
    stem = vbar(0, 0, CAP)
    arm = dstroke((W, CCY), (W + 2 * CRW - W, CAP), W)
    leg = dstroke((W, CCY), (W + 2 * CRW - W, 0), W)
    return clip(U(stem, arm, leg), 0, CAP)

def L():
    return U(vbar(0, 0, CAP), hbar(0, 2 * CRW - 60, 0))

def M():
    g = U(vbar(0, 0, CAP), vbar(2 * CRW - W, 0, CAP),
          dstroke((W / 2, CAP), (CRW, CAP * 0.34), W),
          dstroke((2 * CRW - W / 2, CAP), (CRW, CAP * 0.34), W))
    return clip(g, 0, CAP)

def N():
    g = U(vbar(0, 0, CAP), vbar(2 * CRW - W, 0, CAP),
          dstroke((W / 2, CAP), (2 * CRW - W / 2, 0), W * 1.05))
    return clip(g, 0, CAP)

def O():
    return C_ring()

def _pr_bowl():
    bh = CAP * 0.33          # taller bowl
    bcy = CAP - bh
    brw = CRW * 0.98
    base = cell(brw, bcy, bh, brw)
    # square the LEFT half (the stem side) like B: no bevel where the bowl meets
    # the vertical stroke; only the right side stays round/bevelled
    base = U(base, box(0, bcy - bh, brw, bcy + bh))
    return base, bcy, bh, brw

def P():
    stem = vbar(0, 0, CAP)
    bowl, bcy, bh, brw = _pr_bowl()
    return U(stem, bowl).difference(bowl.buffer(-W, **MIT))

TAIL_OUT = 140      # how far the Q tail reaches past the bowl's outer contour

def Q():
    base = cell(CRW, CCY, CCY + OV_UC, CRW)
    g = ring(base)
    counter = base.buffer(-W, **MIT)
    # A long 45° ray from the bowl centre, then trimmed at BOTH ends:
    #  - minus the counter, so it can't cut a stub across the inside of the bowl
    #    (the old tail started at the centre and did exactly that);
    #  - intersected with the bowl grown by TAIL_OUT, so it always protrudes the
    #    same amount past the outer edge whatever the width/weight.
    ray = dstroke((CRW, CCY), (4 * CRW, CCY - 3 * CRW), W)
    tail = ray.difference(counter).intersection(
        base.buffer(TAIL_OUT, join_style=1, resolution=RES))
    return U(g, clip(tail, DESC, CCY))

def R():
    stem = vbar(0, 0, CAP)
    bowl, bcy, bh, brw = _pr_bowl()
    g = U(stem, bowl).difference(bowl.buffer(-W, **MIT))
    # leg starts from the RIGHT of the bowl (its bottom-right junction), not the left stem
    leg = dstroke((brw + 15, bcy - bh + W / 2), (2 * brw, 0), W)
    return clip(U(g, leg), 0, CAP)

def S():
    return _s_shape(CRW, CAP, 0, OV_UC)

def T():
    return U(hbar(0, 2 * CRW, CAP - W), vbar(CRW - W / 2, 0, CAP - W))

def UU():
    # Straight-sided from the shoulder up: the outer shape is the alveole bottom
    # plus a plain box, so the ring's INNER wall stays vertical all the way to the
    # top. (The old build clipped the O's ring at the OUTER cell's shoulder and
    # butted stems onto it — but the inner bevel starts lower, and lower still as
    # W grows, so it bulged past the stems' inner edge as a nub in the counter.)
    base = U(cell(CRW, CCY, CCY, CRW), box(0, CCY, 2 * CRW, CAP))
    g = ring(base)
    # open the top: drop the bar that would otherwise close the ring between stems
    return g.difference(box(W, CAP - W - 2, 2 * CRW - W, CAP + 50))

def V():
    g = U(dstroke((0, CAP), (CRW, -30), W), dstroke((2 * CRW, CAP), (CRW, -30), W))
    return clip(g, -OV_PT, CAP)

def WW():
    dx = CRW * 0.72         # narrower
    OV = 24
    P = [(0, CAP + OV), (dx, -OV), (2 * dx, CAP * 0.58), (3 * dx, -OV), (4 * dx, CAP + OV)]  # higher middle
    g = U(*[dstroke(P[k], P[k + 1], W) for k in range(4)])
    return clip(g, -OV_PT, CAP)

def X():
    g = U(dstroke((0, CAP), (2 * CRW, 0), W), dstroke((0, 0), (2 * CRW, CAP), W))
    return clip(g, 0, CAP)

def Y():
    g = U(dstroke((0, CAP), (CRW, CCY), W), dstroke((2 * CRW, CAP), (CRW, CCY), W),
          vbar(CRW - W / 2, 0, CCY + W / 2))
    return clip(g, 0, CAP)

def Z():
    return clip(U(hbar(0, 2 * CRW, CAP - W), hbar(0, 2 * CRW, 0),
                  dstroke((2 * CRW - W / 2, CAP - W / 2), (W / 2, W / 2), W)), 0, CAP)

# ================= digits =================
DRW = 200

def n0():
    return ring(cell(DRW, CCY, CCY + OV_UC, DRW))

def n1():
    cx = DRW                                   # stem centre
    stem = vbar(cx - W / 2, 0, CAP)
    # flag reach and base half-width follow the WIDTH axis — as plain absolutes
    # the 1 stayed 369 u wide while every other digit grew to 540 in the Wide
    # masters, leaving it stunted and under-spaced in figures.
    flag = dstroke((cx - W / 2 - round(140 * WF), CAP - 185), (cx - W / 2, CAP), W)
    base = hbar(cx - round(160 * WF), cx + round(160 * WF), 0)   # centred under the stem
    return clip(U(stem, flag, base), 0, CAP)

def n2():
    top = hbar(0, 2 * DRW, CAP - W)
    mid = hbar(0, 2 * DRW, CCY - W / 2)
    bot = hbar(0, 2 * DRW, 0)
    ur = vbar(2 * DRW - W, CCY - W / 2, CAP)
    ll = vbar(0, 0, CCY + W / 2)
    return U(top, mid, bot, ur, ll)

def n3():
    top = hbar(0, 2 * DRW, CAP - W)
    mid = hbar(DRW - 40, 2 * DRW, CCY - W / 2)
    bot = hbar(0, 2 * DRW, 0)
    right = vbar(2 * DRW - W, 0, CAP)
    return U(top, mid, bot, right)

def n4():
    diag = dstroke((2 * DRW - W - 30, CAP), (0, CAP * 0.32), W)
    base = hbar(-10, 2 * DRW, CAP * 0.32 - W / 2)
    stem = vbar(2 * DRW - W - 30, 0, CAP)
    return clip(U(diag, base, stem), 0, CAP)

def n5():
    my = CCY - W / 2                                           # mid-bar level
    Rc = 180                                                   # bottom-right corner radius
    top = hbar(0, 2 * DRW, CAP - W)                            # top bar
    mid = hbar(0, 2 * DRW, my)                                 # mid bar
    ul = vbar(0, my, CAP)                                      # upper-left arm
    right = vbar(2 * DRW - W, Rc, my)                          # right side, mid down to the curve
    botbar = hbar(0, 2 * DRW - Rc, 0)                          # bottom bar (belly stays open on the left)
    corner = ring(cell(2 * DRW - Rc, Rc, Rc, Rc)).intersection(
        box(2 * DRW - Rc, -10, 2 * DRW + 20, Rc))             # rounded bottom-right corner
    return U(top, mid, ul, right, botbar, corner)

def n6():
    rh = CAP * 0.29
    cy_lo = rh
    cy_hi = CAP - rh
    bowl = ring(cell(DRW, cy_lo, rh, DRW))                       # closed lower circle
    upper = ring(cell(DRW, cy_hi, rh, DRW))                      # same circle, upper
    tf = DRW * 0.42
    top = upper.intersection(box(-3000, cy_hi, DRW + tf, CAP + 3000))
    extend = box(DRW, CAP - W, DRW * 1.62, CAP)                  # flat top, longer but not to the edge
    stem = vbar(0, cy_lo, cy_hi)                                 # left side joins the two
    return U(bowl, top, extend, stem)

def n9():
    return affinity.rotate(n6(), 180, origin=(DRW, CCY))         # 9 = 6 rotated 180 deg

def n8():
    up = ring(cell(DRW, CAP * 0.72, CAP * 0.28, DRW))
    lo = ring(cell(DRW, CAP * 0.28, CAP * 0.28, DRW))
    return U(up, lo)

def n7():
    drop = 130
    top = hbar(0, 2 * DRW, CAP - W)
    spur = vbar(2 * DRW - W, CAP - W - drop, CAP)               # short vertical drop, top-right
    diag = dstroke((2 * DRW - W / 2, CAP - W - drop + 25), (DRW * 0.60, 0), W)  # then oblique
    return clip(U(top, spur, diag), 0, CAP)

# ================= punctuation =================
def period():
    return dot(W / 2, W / 2, W / 2)

def comma():
    d = dot(W / 2, W / 2, W / 2)
    tail = dstroke((W / 2, W / 2), (W / 2 - 30, -170), W)
    return U(d, clip(tail, -190, W))

def hyphen():
    return hbar(0, 260, CCY - W / 2)

def apostrophe():
    return dstroke((W / 2, CAP), (W / 2 - 25, CAP - 190), W)

def colon():
    return U(dot(W / 2, W / 2, W / 2), dot(W / 2, XH - W / 2, W / 2))

def slash():
    return dstroke((0, -60), (260, CAP + 60), W)

def notdef():
    # real .notdef: barred rectangle at the monoline stroke (Phase 5)
    wbox = 2 * RW
    outer = box(0, 0, wbox, CAP)
    frame = outer.difference(outer.buffer(-W, **MIT))
    diag = clip(dstroke((0, 0), (wbox, CAP), W), 0, CAP)
    return U(frame, diag)

# ================= extra punctuation & symbols (Phase 5 drawn set) =================
def exclam():
    return U(vbar(0, W + 130, CAP), dot(W / 2, W / 2, W / 2))

def exclamdown():
    return U(vbar(0, 0, CAP - W - 130), dot(W / 2, CAP - W / 2, W / 2))

def question():
    rw = 150
    cy = CAP - rw                                       # bowl centre (bowl spans CAP-2rw..CAP)
    bowl = ring(cell(rw, cy, rw, rw))
    bowl = bowl.difference(box(-120, cy - rw - 30, rw, cy + 4))   # open the lower-left quadrant
    stem = vbar(rw - W / 2, W + 150, cy - rw + W)                 # short stem from the hook down
    return U(bowl, stem, dot(rw, W, W / 2))

def questiondown():
    return affinity.rotate(question(), 180, origin=(150, CAP / 2))

def quotedbl():
    return U(vbar(0, CAP - 190, CAP), vbar(150, CAP - 190, CAP))

def quotesingle_():
    return vbar(0, CAP - 190, CAP)

def _comma_top(x):                      # a comma shape hanging from cap height
    d = dot(x + W / 2, CAP - W / 2, W / 2)
    tail = dstroke((x + W / 2, CAP - W / 2), (x + W / 2 - 30, CAP - 200), W)
    return U(d, clip(tail, CAP - 220, CAP))

def quoteright():                        # ’  (also U+2019, defined earlier via apostrophe)
    return apostrophe()

def quoteleft():                         # ‘
    return affinity.rotate(apostrophe(), 180, origin=(W / 2, CAP - 95))

def quotedblright():                     # ”
    return U(apostrophe(), affinity.translate(apostrophe(), 150, 0))

def quotedblleft():                      # “
    return U(quoteleft(), affinity.translate(quoteleft(), 150, 0))

def semicolon():
    return U(dot(W / 2, XH - W / 2, W / 2), comma())

def numbersign():
    v1 = dstroke((150, 0), (110, CAP), W * 0.8)
    v2 = dstroke((300, 0), (260, CAP), W * 0.8)
    h1 = hbar(-20, 430, CAP * 0.62)
    h2 = hbar(-20, 430, CAP * 0.30)
    return clip(U(v1, v2, h1, h2), 0, CAP)

def plus():
    return U(hbar(0, 320, CCY - W / 2), vbar(160 - W / 2, CCY - 160, CCY + 160))

def minus():
    return hbar(0, 320, CCY - W / 2)

def equal():
    return U(hbar(0, 320, CCY + 30), hbar(0, 320, CCY - 30 - W))

def _chevron(right, x0, y0, y1, half):
    ym = (y0 + y1) / 2
    if right:
        return U(dstroke((x0, y0), (x0 + half, ym), WA), dstroke((x0 + half, ym), (x0, y1), WA))
    return U(dstroke((x0 + half, y0), (x0, ym), WA), dstroke((x0, ym), (x0 + half, y1), WA))

def less():
    return _chevron(False, 20, CCY - 170, CCY + 170, 240)

def greater():
    return _chevron(True, 20, CCY - 170, CCY + 170, 240)

def guilsinglleft():
    return _chevron(False, 20, 175, 385, 100)

def guilsinglright():
    return _chevron(True, 20, 175, 385, 100)

def _paren(left):
    rw, cy, rh = 150, CAP / 2, (CAP + 160) / 2
    r = ring(cell(rw, cy, rh, rw, sh=0.30))            # sh low -> smooth curve, not octagonal
    keep = box(-999, -999, rw, 9999) if left else box(rw, -999, 9999, 9999)
    return clip(r.intersection(keep), -90, CAP + 90)

def parenleft():
    return _paren(True)

def parenright():
    return _paren(False)

def _bracket(left):
    w = 150
    stem = vbar(0 if left else w - W, -70, CAP + 70)
    arms = U(hbar(0, w, CAP + 70 - W), hbar(0, w, -70))
    return U(stem, arms)

def bracketleft():
    return _bracket(True)

def bracketright():
    return _bracket(False)

def _brace(left):
    w, mid = 150, CCY
    rh = (CAP + 140) / 4
    top = clip(ring(cell(w, mid + rh, rh, w)), mid + W / 2, CAP + 70)   # upper quarter arc
    bot = clip(ring(cell(w, mid - rh, rh, w)), -70, mid - W / 2)        # lower quarter arc
    keep = box(-999, -999, w, 9999)
    top = top.intersection(keep)
    bot = bot.intersection(keep)
    tongue = hbar(-55, w * 0.5, mid - W / 2)                            # mid point, outward
    g = U(top, bot, tongue)
    if not left:
        g = affinity.scale(g, xfact=-1, origin=(w / 2, mid))
    return g

def braceleft():
    return _brace(True)

def braceright():
    return _brace(False)

def bar():
    return vbar(0, -70, CAP + 70)

def backslash():
    return dstroke((0, CAP + 60), (260, -60), W)

def asciicircum():
    pk = (150, CAP)
    return U(dstroke((30, CAP - 190), pk, W), dstroke(pk, (270, CAP - 190), W))

def asciitilde():
    y, a = CCY, 95
    P = [(0, y - 10), (85, y + a), (175, y - 10), (200, y - 20), (285, y - a), (370, y + 10)]
    return clip(U(*[dstroke(P[k], P[k + 1], W) for k in range(len(P) - 1)]), y - a - W, y + a + W)

def underscore():
    return hbar(0, 2 * RW, -120)

def grave_ch():
    return _grave(90, CAP - 190)

def asterisk():
    cx, cy, r = 150, CAP - 150, 150
    arms = [dstroke((cx, cy), (cx + r * math.cos(math.radians(a)),
                               cy + r * math.sin(math.radians(a))), W * 0.8)
            for a in (90, 90 + 72, 90 + 144, 90 + 216, 90 + 288)]
    return U(*arms)

def periodcentered():
    return dot(W / 2, CCY - W / 2, W / 2)

def bullet():
    return dot(120, CCY, 120)

def ellipsis():
    return U(dot(W / 2, W / 2, W / 2),
             dot(W / 2 + 240, W / 2, W / 2),
             dot(W / 2 + 480, W / 2, W / 2))

def endash():
    return hbar(0, 360, CCY - W / 2)

def emdash():
    return hbar(0, 560, CCY - W / 2)

def degree():
    r = 115          # same radius as the percent dots -> visibly hollow centre
    return ring(cell(r, CAP - r - 20, r, r, sh=0.5, topf=0.55))

def _cring(rw, cy):
    g = ring(cell(rw, cy, rw, rw))
    return g.difference(box(rw + 15, cy - rw * 0.62, 2 * rw + 40, cy + rw * 0.62))

def euro():
    rw, cy = 250, CCY
    g = clip(_cring(rw, cy), 0, CAP)
    bars = U(hbar(-40, rw + 30, cy + 25), hbar(-40, rw + 30, cy - 25 - W))
    return U(g, bars)

def copyright_ch():
    R = 345
    outer = ring(cell(R, CCY, R, R))
    ic = c()                                     # the real lowercase c, scaled into the ring
    x0, y0, x1, y1 = ic.bounds
    s = 370.0 / (y1 - y0)
    ic = affinity.scale(ic, s, s, origin=(0, 0))
    x0, y0, x1, y1 = ic.bounds
    ic = affinity.translate(ic, R - (x0 + x1) / 2, CCY - (y0 + y1) / 2)
    return U(outer, ic)

def percent():
    r, gap = 115, 130
    def ringlet(cx, cy):
        c = cell(r, cy, r, r, sh=0.5, topf=0.55)
        return affinity.translate(c.difference(c.buffer(-W, **MIT)), cx, 0)
    ul = ringlet(0, CAP - r)             # top-left circle
    lr = ringlet(2 * r + gap, r)         # bottom-right circle
    xmax = 2 * r + gap + 2 * r
    # slash on the exact opposite diagonal, centred between the two circles
    slash_ = clip(dstroke((0, 0), (xmax, CAP), W), 0, CAP)
    return U(ul, lr, slash_)

def dollar():
    rw = 210                                    # wider S so it doesn't look cramped
    return U(_s_shape(rw, CAP - 30, 30, 0), vbar(rw - W / 2, -80, CAP + 80))

def ampersand():
    # Traced from the user's reference drawing (sources/esperluette.png -> vectorised
    # to sources/ampersand.json). Geometric primitives couldn't capture a real
    # ampersand at this stroke weight, so we honour the supplied design. Kept out
    # of round_corners (PRESMOOTHED) so the loops aren't thickened.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources", "ampersand.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    poly = Polygon(data["outer"], data["holes"])
    return poly.buffer(AMP_BUF, join_style=1, resolution=8)   # thicken to the current monoline weight

PRESMOOTHED = {"&", "@"}   # already-vectorised glyphs: skip round_corners

def at():
    # traced from the user's reference (sources/arobase.png -> arobase.json)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources", "arobase.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    poly = Polygon(data["outer"], data["holes"])
    return poly.buffer(AT_BUF, join_style=1, resolution=8) if AT_BUF else poly

# ================= build map =================
LOWER = dict(a=a, b=b, c=c, d=d, e=e, f=f, g=None, h=h, i=i, j=j, k=k, l=l,
             m=m, n=n, o=o, p=p, q=q, r=r, s=s, t=t, u=u, v=v, w=w_, x=x, y=y, z=z)
UPPER = dict(A=A, B=B, C=C, D=D, E=E, F=F, G=G, H=H, I=I, J=J, K=K, L=L, M=M,
             N=N, O=O, P=P, Q=Q, R=R, S=S, T=T, U=UU, V=V, W=WW, X=X, Y=Y, Z=Z)
DIGIT = {'0': n0, '1': n1, '2': n2, '3': n3, '4': n4, '5': n5, '6': n6, '7': n7,
         '8': n8, '9': n9}
PUNCT = {'.': period, ',': comma, '-': hyphen, "'": apostrophe, ':': colon, '/': slash}

# g single-story fallback
def g_():
    bowl = cell(RW, 250, 250 + OV_LC, RW)
    body = bowl.difference(bowl.buffer(-W, **MIT))
    stem = vbar(2 * RW - W, DESC + 90, XH)
    hook = hbar(20, 2 * RW, DESC)
    return U(body, stem, hook)
LOWER['g'] = g_

# ================= diacritics & accented letters =================
WA = W * 0.82   # accent stroke width

def _acute(cx, by):
    return dstroke((cx - 48, by + 20), (cx + 48, by + 150), WA)

def _grave(cx, by):
    return dstroke((cx - 48, by + 150), (cx + 48, by + 20), WA)

def _circum(cx, by):
    pk = (cx, by + 165)
    return U(dstroke((cx - 92, by + 20), pk, WA), dstroke(pk, (cx + 92, by + 20), WA))

def _dieresis(cx, by):
    r = W * 0.44
    return U(dot(cx - 66, by + 80, r), dot(cx + 66, by + 80, r))

def _cedilla(cx):
    # traced from the user's reference (sources/cedille.png -> cedille.json),
    # centred at x=0, hanging below the baseline. Placed under C/c as a component.
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources", "cedille.json")
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return affinity.translate(Polygon(data["outer"], data["holes"]), cx, 0)

def dotless_i():
    return vbar(0, 0, XH)

# canonical accent marks — drawn centred at x=0, at lowercase accent height.
# Used as TrueType components (Phase 7 §composites): accented letters reference
# a base glyph + one of these, instead of duplicating contours.
MARKS = {
    'acute':      lambda: _acute(0, XH + 40),
    'grave':      lambda: _grave(0, XH + 40),
    'circumflex': lambda: _circum(0, XH + 40),
    'dieresis':   lambda: _dieresis(0, XH + 40),
    'cedilla':    lambda: _cedilla(0),
}
DYUP = CAP - XH        # lift a mark from lowercase to uppercase height

# accented letter -> (base glyph name, mark glyph name, mark dy)
COMPOSITE = {
    'é': ('e', 'acute', 0), 'è': ('e', 'grave', 0), 'ê': ('e', 'circumflex', 0), 'ë': ('e', 'dieresis', 0),
    'à': ('a', 'grave', 0), 'â': ('a', 'circumflex', 0), 'ä': ('a', 'dieresis', 0),
    'î': ('dotlessi', 'circumflex', 0), 'ï': ('dotlessi', 'dieresis', 0),
    'ô': ('o', 'circumflex', 0), 'ö': ('o', 'dieresis', 0),
    'ù': ('u', 'grave', 0), 'û': ('u', 'circumflex', 0), 'ü': ('u', 'dieresis', 0),
    'ÿ': ('y', 'dieresis', 0), 'ç': ('c', 'cedilla', 0),
    'É': ('E', 'acute', DYUP), 'È': ('E', 'grave', DYUP), 'Ê': ('E', 'circumflex', DYUP), 'Ë': ('E', 'dieresis', DYUP),
    'À': ('A', 'grave', DYUP), 'Â': ('A', 'circumflex', DYUP), 'Ä': ('A', 'dieresis', DYUP),
    'Î': ('I', 'circumflex', DYUP), 'Ï': ('I', 'dieresis', DYUP),
    'Ô': ('O', 'circumflex', DYUP), 'Ö': ('O', 'dieresis', DYUP),
    'Ù': ('U', 'grave', DYUP), 'Û': ('U', 'circumflex', DYUP), 'Ü': ('U', 'dieresis', DYUP),
    'Ÿ': ('Y', 'dieresis', DYUP), 'Ç': ('C', 'cedilla', 0),
}

# ligatures
def _oe():
    return U(o(), affinity.translate(e(), 2 * RW - W, 0))

def _ae():
    return U(a(), affinity.translate(e(), 2 * RW - W, 0))

def _OE():
    return U(O(), affinity.translate(E(), 2 * CRW - W, 0))

def _AE():
    return U(A(), affinity.translate(E(), 2 * CRW - W, 0))

# french guillemets
def _guill(right):
    def chev(x0):
        if right:
            return U(dstroke((x0, 175), (x0 + 78, 280), WA), dstroke((x0 + 78, 280), (x0, 385), WA))
        return U(dstroke((x0 + 78, 175), (x0, 280), WA), dstroke((x0, 280), (x0 + 78, 385), WA))
    return U(chev(20), chev(135))

LIGS = {'œ': _oe, 'æ': _ae, 'Œ': _OE, 'Æ': _AE, '«': lambda: _guill(False), '»': lambda: _guill(True)}

# typographic apostrophe U+2019 — same shape as the ASCII apostrophe (Phase 5)
EXTRA = {'’': apostrophe}

# drawn symbols & extra punctuation (Phase 5 charset completion)
SYM = {
    '!': exclam, '¡': exclamdown, '?': question, '¿': questiondown,
    '"': quotedbl, '#': numbersign, '$': dollar, '%': percent, '&': ampersand,
    '(': parenleft, ')': parenright, '*': asterisk, '+': plus, ';': semicolon,
    '<': less, '=': equal, '>': greater, '@': at, '[': bracketleft,
    '\\': backslash, ']': bracketright, '^': asciicircum, '_': underscore,
    '`': grave_ch, '{': braceleft, '|': bar, '}': braceright, '~': asciitilde,
    '–': endash, '—': emdash, '…': ellipsis, '°': degree, '€': euro,
    '©': copyright_ch, '‘': quoteleft, '“': quotedblleft, '”': quotedblright,
    '‹': guilsinglleft, '›': guilsinglright, '·': periodcentered, '•': bullet,
    '−': minus,
}

BUILDERS = {}
BUILDERS.update(LOWER); BUILDERS.update(UPPER); BUILDERS.update(DIGIT); BUILDERS.update(PUNCT)
BUILDERS.update(LIGS); BUILDERS.update(EXTRA); BUILDERS.update(SYM)   # accents = composites

# ---------- corner rounding ----------
def round_corners(g, r=RAD):
    g = g.buffer(-r, join_style=1, resolution=RES).buffer(r, join_style=1, resolution=RES)
    g = g.buffer(r * 0.6, join_style=1, resolution=RES).buffer(-r * 0.6, join_style=1, resolution=RES)
    return g

# ---------- contour refit: polyline -> lines + quadratic Béziers ----------
REFIT = True          # emit real curves instead of one lineTo per polygon vertex

def _dedupe(pts, tol=0.9):
    out = [pts[0]]
    for p in pts[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= tol:
            out.append(p)
    if len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < tol:
        out.pop()
    return out

def _turn(a, b, c):
    d = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(b[1] - a[1], b[0] - a[0])
    while d > math.pi:  d -= 2 * math.pi
    while d < -math.pi: d += 2 * math.pi
    return d

def _isect(A, dA, B, dB):
    # intersection of line A+t*dA and line B+s*dB
    den = dA[0] * dB[1] - dA[1] * dB[0]
    if abs(den) < 1e-6:
        return None
    t = ((B[0] - A[0]) * dB[1] - (B[1] - A[1]) * dB[0]) / den
    return (A[0] + t * dA[0], A[1] + t * dA[1])

def _unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1.0
    return (dx / n, dy / n)

def _qeval(A, C, B, t):
    m = 1 - t
    return (m * m * A[0] + 2 * m * t * C[0] + t * t * B[0],
            m * m * A[1] + 2 * m * t * C[1] + t * t * B[1])

def _max_dev(A, C, B, pts):
    samp = [_qeval(A, C, B, i / 24.0) for i in range(25)]
    md = 0.0
    for p in pts[1:-1]:
        d = min(math.hypot(p[0] - s[0], p[1] - s[1]) for s in samp)
        if d > md:
            md = d
    return md

def _fit(sub, tol=2.0, depth=0):
    """Fit one closed polyline segment (list of points, endpoints fixed) with
    quadratic Béziers, recursively subdividing until the max deviation from the
    real points is <= tol. Subdivision naturally handles inflections & big arcs."""
    A, B = sub[0], sub[-1]
    if len(sub) <= 2:
        return [('L', B)]
    cp = _isect(A, _unit(sub[0], sub[1]), B, _unit(sub[-2], sub[-1]))
    if cp is not None and depth < 10 and _max_dev(A, cp, B, sub) <= tol:
        return [('Q', cp, B)]
    if depth >= 10:
        return [('L', p) for p in sub[1:]]     # give up gracefully -> polyline
    m = len(sub) // 2
    return _fit(sub[:m + 1], tol, depth + 1) + _fit(sub[m:], tol, depth + 1)

def refit_ring(coords, flat=4.0, corner=28.0, tol=1.0):
    """[('M',p0), ('L',p)|('Q',cp,p), ...] for one closed ring.
    Truly straight runs collapse to lines; everything else is fit with quads to
    <= tol units of the original polygon. Sharp corners stay on-curve.
    tol=1.0 keeps the tangent-intersection bulge under 1 u so the perpendicular
    stroke stays inside the 88.5-91.9 monoline band."""
    pts = _dedupe([(float(x), float(y)) for x, y in coords])
    n = len(pts)
    if n < 5:
        return [('M', pts[0])] + [('L', p) for p in pts[1:]]
    FLAT, CORN = math.radians(flat), math.radians(corner)
    turn = [_turn(pts[(i - 1) % n], pts[i], pts[(i + 1) % n]) for i in range(n)]
    flatv = [abs(t) <= FLAT for t in turn]
    # anchors = sharp corners + boundaries of straight runs
    anchor = [False] * n
    for i in range(n):
        if abs(turn[i]) > CORN:
            anchor[i] = True
        elif flatv[i] and (not flatv[(i - 1) % n] or not flatv[(i + 1) % n]):
            anchor[i] = True
    idx = [i for i in range(n) if anchor[i]]
    if len(idx) < 2:
        idx = list(range(0, n, max(1, n // 8)))
    # start on an anchor whose incoming edge is straight (so the closing segment
    # is a droppable line)
    s0 = next((k for k, i in enumerate(idx) if flatv[i]), 0)
    idx = idx[s0:] + idx[:s0]
    m = len(idx)

    ops = []
    for k in range(m):
        a, b = idx[k], idx[(k + 1) % m]
        seq, i, allflat = [pts[a]], (a + 1) % n, True
        while True:
            if i != a:
                seq.append(pts[i])
            if not flatv[i] and i != b:
                allflat = False
            if i == b:
                break
            i = (i + 1) % n
        if len(seq) <= 2 or allflat:
            ops.append(('L', pts[b]))
        else:
            ops.extend(_fit(seq, tol))
    # closing segment ends at start; drop it if it's a plain line
    if ops and ops[-1][0] == 'L' and ops[-1][1] == pts[idx[0]]:
        ops.pop()
    return [('M', pts[idx[0]])] + ops

# ---------- shapely -> TT glyph ----------
def _emit(pen, ops, dx):
    R = lambda p: (round(p[0] + dx), round(p[1]))
    pen.moveTo(R(ops[0][1]))
    for op in ops[1:]:
        if op[0] == 'L':
            pen.lineTo(R(op[1]))
        else:
            pen.qCurveTo(R(op[1]), R(op[2]))
    pen.closePath()

def geom_to_glyph(g, lsb=SB, rsb=SB, translate=True, smooth=True):
    """Return (glyph, advance, xMin, xMax) in final coords. translate=False keeps
    the drawn coordinates (accent marks, positioned later as components).
    smooth=False skips round_corners (for pre-vectorised glyphs like &)."""
    if smooth:
        g = round_corners(g)
    if g.is_empty:
        return TTGlyphPen(None).glyph(), 0, 0, 0
    polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
    minx = min(p.bounds[0] for p in polys)
    maxx = max(p.bounds[2] for p in polys)
    dx = (lsb - minx) if translate else 0
    pen = TTGlyphPen(None)
    for poly in polys:
        poly = orient(poly, sign=-1.0)   # exterior clockwise (TT y-up)
        rings = [poly.exterior.coords] + [h.coords for h in poly.interiors]
        for ring in rings:
            if REFIT:
                _emit(pen, refit_ring(list(ring)[:-1]), dx)
            else:
                pl = [(round(x + dx), round(y)) for x, y in ring][:-1]
                pen.moveTo(pl[0])
                for pt in pl[1:]:
                    pen.lineTo(pt)
                pen.closePath()
    adv = round(maxx - minx + lsb + rsb)
    return pen.glyph(), adv, minx + dx, maxx + dx

# ================= spacing (Phase 3) =================
# Per-group sidebearings instead of the single uniform (46, 46). References:
# straight n/H, round o/O. On a geometric monoline the round side reads ~13 %
# tighter than the straight side; diagonals and open terminals tighter still.
STR = 46   # straight vertical stem (reference)
RND = 40   # round curve  (~ STR - 13 %)
OPN = 30   # open terminal side (c/e/E/F/L/G right ...)
DIA = 20   # diagonal side (A V W X Y v w x y, k/K/R right)
NAR = 46   # i l I

SPACING = {
    # lowercase --------------------------------------------------
    'a': (RND, STR), 'b': (STR, RND), 'c': (RND, OPN), 'd': (RND, STR),
    'e': (RND, 34),  'f': (28, 30),   'g': (RND, STR), 'h': (STR, STR),
    'i': (NAR, NAR), 'j': (26, 40),   'k': (STR, DIA), 'l': (NAR, NAR),
    'm': (STR, STR), 'n': (STR, STR), 'o': (RND, RND), 'p': (STR, RND),
    'q': (RND, STR), 'r': (STR, 24),  's': (38, 38),   't': (26, 34),
    'u': (STR, STR), 'v': (DIA, DIA), 'w': (DIA, DIA), 'x': (DIA, DIA),
    'y': (DIA, DIA), 'z': (34, 34),
    # uppercase --------------------------------------------------
    'A': (18, 18),   'B': (STR, RND), 'C': (RND, OPN), 'D': (STR, RND),
    'E': (STR, OPN), 'F': (STR, OPN), 'G': (RND, OPN), 'H': (STR, STR),
    'I': (NAR, NAR), 'J': (28, STR),  'K': (STR, DIA), 'L': (STR, OPN),
    'M': (STR, STR), 'N': (STR, STR), 'O': (RND, RND), 'P': (STR, RND),
    'Q': (RND, RND), 'R': (STR, DIA), 'S': (38, 38),   'T': (26, 26),
    'U': (STR, STR), 'V': (DIA, DIA), 'W': (DIA, DIA), 'X': (DIA, DIA),
    'Y': (DIA, DIA), 'Z': (34, 34),
    # digits -----------------------------------------------------
    '0': (RND, RND), '1': (44, 50), '2': (34, 36), '3': (34, 34), '4': (24, 34),
    '5': (36, 36), '6': (RND, RND), '7': (30, 34), '8': (RND, RND), '9': (RND, RND),
    # ligatures --------------------------------------------------
    'œ': (RND, 34), 'æ': (RND, 34), 'Œ': (RND, OPN), 'Æ': (18, OPN),
    # guillemets / punctuation ----------------------------------
    '«': (40, 30), '»': (30, 40),
    '.': (50, 50), ',': (50, 50), ':': (50, 50), '-': (44, 44),
    '/': (24, 24), "'": (34, 34), '’': (34, 34),
    # math signs share a common advance (412) — fontbakery math_signs_width
    '<': (75, 75), '>': (75, 75),
    '&': (34, 30),   # traced glyph is wide; tighten a touch
}

# accented letters & apostrophe borrow their base letter's spacing
ACCENT_BASE = {
    'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e', 'à': 'a', 'â': 'a', 'ä': 'a',
    'î': 'i', 'ï': 'i', 'ô': 'o', 'ö': 'o', 'ù': 'u', 'û': 'u', 'ü': 'u',
    'ÿ': 'y', 'ç': 'c',
    'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E', 'À': 'A', 'Â': 'A', 'Ä': 'A',
    'Î': 'I', 'Ï': 'I', 'Ô': 'O', 'Ö': 'O', 'Ù': 'U', 'Û': 'U', 'Ü': 'U',
    'Ÿ': 'Y', 'Ç': 'C',
}

def sidebearings(ch):
    # spacing opens with the WIDTH axis so a Wide master isn't cramped between
    # its own widened glyphs (WF=1.0 -> the Regular numbers, unchanged).
    lsb, rsb = SPACING.get(ACCENT_BASE.get(ch, ch), (SB, SB))
    return round(lsb * WF), round(rsb * WF)

def name_for(ch):
    """AGLFN glyph name (Phase 7 — no more uniXXXX for named glyphs)."""
    specials = {'.': 'period', ',': 'comma', '-': 'hyphen', "'": 'quotesingle',
                ':': 'colon', '/': 'slash',
                '!': 'exclam', '"': 'quotedbl', '#': 'numbersign', '$': 'dollar',
                '%': 'percent', '&': 'ampersand', '(': 'parenleft', ')': 'parenright',
                '*': 'asterisk', '+': 'plus', ';': 'semicolon', '<': 'less',
                '=': 'equal', '>': 'greater', '?': 'question', '@': 'at',
                '[': 'bracketleft', '\\': 'backslash', ']': 'bracketright',
                '^': 'asciicircum', '_': 'underscore', '`': 'grave',
                '{': 'braceleft', '|': 'bar', '}': 'braceright', '~': 'asciitilde'}
    if ch in specials:
        return specials[ch]
    if ch.isdigit():
        return {'0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
                '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'}[ch]
    cp = ord(ch)
    if cp > 127:
        # AGL name if one exists (eacute, oe, guillemotleft, quoteright, ...),
        # else the standard production name uniXXXX (only for the truly
        # nameless code points, e.g. the spaces).
        return UV2AGL.get(cp, "uni%04X" % cp)
    return ch  # ASCII letters keep their own name


def _apply_master(cfg):
    """Point the parametric globals at one master (weight × width). Every glyph
    function reads W / WA / WF / RW / CRW / DRW / AMP_BUF / AT_BUF at call time,
    so mutating them here re-draws the whole font at a new stroke AND width — no
    per-glyph plumbing. The 200/250/200 bases are the Regular round half-widths."""
    global W, WA, WF, RW, CRW, DRW, AMP_BUF, AT_BUF
    W = cfg["stroke"]
    WA = W * 0.82
    WF = cfg.get("width_factor", 1.0)
    RW  = round(200 * WF)      # x-height round half-width
    CRW = round(250 * WF)      # cap round half-width
    DRW = round(200 * WF)      # digit round half-width
    AMP_BUF = cfg["amp_buf"]
    AT_BUF = cfg["at_buf"]

_set_weight = _apply_master   # back-compat alias


def build_font(path, cfg=None):
    if cfg is None:
        cfg = MASTERS["Regular"]
    _apply_master(cfg)
    style = cfg["style"]
    family = cfg.get("family", "Beeraw Hex")
    empty = TTGlyphPen(None).glyph()
    glyph_order = [".notdef"]
    cmap = {}
    glyphs = {}
    advances = {}

    bounds = {}   # glyph name -> (xMin, xMax) in final coords

    # .notdef: a real drawn glyph (Phase 5) — barred box at the 90 u stroke
    nd_glyph, nd_adv, _, _ = geom_to_glyph(notdef())
    glyphs[".notdef"] = nd_glyph
    advances[".notdef"] = nd_adv

    # spaces (no contour). U+0020 and U+00A0 share the space advance; U+202F is
    # the French narrow no-break space (Phase 5). Named uniXXXX legitimately —
    # these code points have no AGL name.
    for gname, cp, adv in (("space", 0x20, 460), ("uni00A0", 0xA0, 460),
                           ("uni202F", 0x202F, 220)):
        glyphs[gname] = empty
        advances[gname] = adv
        cmap[cp] = gname
        glyph_order.append(gname)

    # base letters, digits, punctuation, ligatures, apostrophe
    for ch, fn in BUILDERS.items():
        gname = name_for(ch)
        lsb, rsb = sidebearings(ch)
        glyph, adv, xmn, xmx = geom_to_glyph(fn(), lsb, rsb, smooth=ch not in PRESMOOTHED)
        glyphs[gname] = glyph
        advances[gname] = adv
        bounds[gname] = (xmn, xmx)
        cmap[ord(ch)] = gname
        glyph_order.append(gname)

    # dotless i — base for î ï (Phase 7 composites), cmapped to U+0131
    gl, adv, xmn, xmx = geom_to_glyph(dotless_i(), *sidebearings('i'))
    glyphs["dotlessi"] = gl; advances["dotlessi"] = adv; bounds["dotlessi"] = (xmn, xmx)
    cmap[0x0131] = "dotlessi"; glyph_order.append("dotlessi")

    # accent marks — uncmapped component glyphs (".comp" suffix avoids clashing
    # with the spacing grave/etc. AGL names), kept at their drawn coordinates
    for mname, mfn in MARKS.items():
        gn = mname + ".comp"
        gl, adv, xmn, xmx = geom_to_glyph(mfn(), translate=False, smooth=mname != "cedilla")
        glyphs[gn] = gl; advances[gn] = max(0, adv); bounds[gn] = (xmn, xmx)
        glyph_order.append(gn)

    # accented letters as TrueType composites: base + mark component. The mark is
    # centred over the base; sidebearings are applied around the *combined* ink
    # (so a wide accent like î's circumflex keeps its clearance).
    for ch, (base_gn, mark_gn, mdy) in COMPOSITE.items():
        gname = name_for(ch)
        mark_g = mark_gn + ".comp"
        bx0, bx1 = bounds[base_gn]
        mx0, mx1 = bounds[mark_g]
        mdx = round((bx0 + bx1) / 2 - (mx0 + mx1) / 2)     # centre mark over base
        cxmin = min(bx0, mx0 + mdx)
        cxmax = max(bx1, mx1 + mdx)
        lsb, rsb = sidebearings(ch)
        shift = round(lsb - cxmin)
        pen = TTGlyphPen(glyphs)                           # glyphSet resolves names
        pen.addComponent(base_gn, Offset(shift, 0))
        pen.addComponent(mark_g, Offset(mdx + shift, round(mdy)))
        glyphs[gname] = pen.glyph()
        advances[gname] = round((cxmax - cxmin) + lsb + rsb)
        cmap[ord(ch)] = gname
        glyph_order.append(gname)

    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    # recompute bounds (composites included) so lsb == xMin everywhere
    glyf = fb.font["glyf"]
    hmtx = {}
    for gn in glyph_order:
        gl = glyf[gn]
        gl.recalcBounds(glyf)
        hmtx[gn] = (advances[gn], getattr(gl, "xMin", 0))
    fb.setupHorizontalMetrics(hmtx)

    # ---- Phase 6: vertical metrics (fix the Ê/Ô/Ä clipping) ----
    # hhea == sTypo == usWin ascender, all clearing yMax 915.
    fb.setupHorizontalHeader(ascent=V_ASC, descent=-V_DESC, lineGap=0)

    # ---- Phase 7: name table ----
    # RIBBI family: familyName carries the WIDTH ("Beeraw Hex" / "Beeraw Hex
    # Wide"), styleName the WEIGHT (Regular/Bold), so each width links its own
    # Regular+Bold pair (nameID 1/2) and bold-toggle works within it.
    fb.setupNameTable({
        "copyright": "Copyright 2026 The Beeraw Hex Project Authors (https://beeraw.yt)",
        "familyName": family,
        "styleName": style,
        "fullName": "%s %s" % (family, style),
        "psName": cfg["filename"],
        "version": "Version %s" % VERSION,
        "manufacturer": "beeraw",
        "designer": "beeraw",
        "vendorURL": "https://beeraw.yt",
        "designerURL": "https://beeraw.yt",
        # fontbakery's `license` check wants this exact wording — note the colon
        # before the URL — whenever OFL.txt ships alongside the font.
        "licenseDescription": ("This Font Software is licensed under the SIL Open "
                               "Font License, Version 1.1. This license is available "
                               "with a FAQ at: https://openfontlicense.org"),
        "licenseInfoURL": "https://openfontlicense.org",
    })

    # ---- Phase 6/7: OS/2 ----
    panose = Panose()
    # bProportion: 4 = Modern (normal), 5 = Very Expanded for the Wide masters.
    bprop = 5 if cfg.get("width_class", 5) >= 7 else 4
    panose.bFamilyType, panose.bSerifStyle, panose.bWeight, panose.bProportion = \
        2, 11, cfg["panose_weight"], bprop
    # fsSelection: USE_TYPO_METRICS always; BOLD or REGULAR are mutually exclusive.
    fssel = (1 << 7) | ((1 << 5) if cfg["bold"] else (1 << 6))
    fb.setupOS2(
        version=4,                                                # bit 7 needs OS/2 v4
        sTypoAscender=V_ASC, sTypoDescender=-V_DESC, sTypoLineGap=0,  # == hhea
        usWinAscent=V_ASC, usWinDescent=V_DESC,                   # clipping box
        sxHeight=XH, sCapHeight=CAP,
        usWeightClass=cfg["weight_class"], usWidthClass=cfg.get("width_class", 5),
        fsType=0,                                                 # Installable (OFL)
        fsSelection=fssel,
        achVendID="BRAW",
        panose=panose,
    )

    fb.setupPost(underlinePosition=-100, underlineThickness=W, isFixedPitch=0)

    # semantic version -> head.fontRevision; keep head clean
    fb.font["head"].fontRevision = float(VERSION)
    fb.font["head"].macStyle = 0x01 if cfg["bold"] else 0        # bit 0 = Bold

    # tighten OS/2 metadata against the actual cmap
    os2 = fb.font["OS/2"]
    os2.recalcUnicodeRanges(fb.font)
    os2.recalcAvgCharWidth(fb.font)
    os2.ulCodePageRange1 = 0x00000001   # Latin 1 (CP1252) — >=1 code page required
    os2.ulCodePageRange2 = 0x00000000
    codes = sorted(c for c in cmap if c != 0)
    os2.usFirstCharIndex = min(codes)
    os2.usLastCharIndex = min(0xFFFF, max(codes))

    # smart-dropout control for the unhinted TTF (fontbakery smart_dropout):
    # PUSHW 0x01FF ; SCANCTRL ; PUSHB 0x04 ; SCANTYPE
    prep = newTable("prep")
    prep.program = ttProgram.Program()
    prep.program.fromBytecode(b"\xb8\x01\xff\x85\xb0\x04\x8d")
    fb.font["prep"] = prep
    maxp = fb.font["maxp"]
    maxp.maxZones = 1
    maxp.maxStackElements = max(maxp.maxStackElements, 2)

    # ---- Phase 4: kerning (GPOS) compiled from features/kern.fea ----
    fea = os.path.join(os.path.dirname(os.path.abspath(__file__)), "features", "kern.fea")
    if os.path.exists(fea):
        addOpenTypeFeatures(fb.font, fea)

    fb.font.save(path)
    print("saved", path, "glyphs:", len(glyph_order))

if __name__ == "__main__":
    import sys
    _here = os.path.dirname(os.path.abspath(__file__))
    _outdir = os.path.join(_here, "fonts")
    os.makedirs(_outdir, exist_ok=True)
    _force = "--force" in sys.argv
    # build every master (or just the ones named on the command line)
    _wanted = [a for a in sys.argv[1:] if a in MASTERS] or list(MASTERS)

    # Safety net: some masters ship a *normalised* build (tools/pipeline.sh adds
    # ccmp/gasp/GDEF/hinting + extra glyphs, bumping the glyph count well past the
    # generator's raw output). Don't silently regress those to the raw generator
    # font — skip them unless --force is given.
    def _is_normalised(path):
        if not os.path.exists(path):
            return False
        try:
            from fontTools.ttLib import TTFont
            return TTFont(path)["maxp"].numGlyphs > 160
        except Exception:
            return False

    for _style in _wanted:
        _cfg = MASTERS[_style]
        _target = os.path.join(_outdir, _cfg["filename"] + ".ttf")
        if _is_normalised(_target) and not _force:
            print(f"skip {_cfg['filename']}: shipped master is normalised "
                  f"(rebuild it via tools/pipeline.sh, or pass --force)")
            continue
        build_font(_target, _cfg)
