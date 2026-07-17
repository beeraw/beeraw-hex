#!/usr/bin/env python3
"""Phase 4bis — apply the kink corrections proposed in audit/04-kinks.md, now
that they're authorised. Conservative, coordinate-boxed snaps on the working UFO
(deterministic from the fixed reconstruction), journalised.

  * U (=> Ugrave/Ucircumflex/Udieresis via components): straighten the inner-wall
    dent — snap the inward cluster (x 445..455.9, y 512..556) back to the wall
    x = 456, restoring a clean vertical.
  * braceleft: make the central-beak apex a symmetric vertical tangent — snap the
    asymmetric outgoing handle (x 175.5..178, y 383..390) to the apex x = 175.
  * braceright: mirror — snap the outgoing handle (x 120.5..121.9, y 313..317)
    to the apex x = 122.

These are the "arrondi" (vertical-tangent) resolution of the beaks. Flip to a
sharp corner by editing SNAPS.

Usage:  python tools/fix_kinks.py [ufo] [--report FILE]
"""
import argparse
import ufoLib2

# glyph -> list of (xmin, xmax, ymin, ymax, axis, target)
# U is symmetric: BOTH inner walls carry the same refit dent -> snap both back
# to their wall x (left = 136, right = 456). The brief's "<450,543>" pointed at
# the right wall while its label said "gauche"; the shape needs both.
SNAPS = {
    "U":          [(445, 455.9, 512, 556, "x", 456),    # right inner wall
                   (136.5, 146, 512, 556, "x", 136)],   # left inner wall
    "braceleft":  [(175.5, 178, 383, 390, "x", 175)],
    "braceright": [(120.5, 121.9, 313, 317, "x", 122)],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ufo", nargs="?", default="sources/BeerawHex-Regular.ufo")
    ap.add_argument("--report", default="audit/04-kinks-applied.md")
    args = ap.parse_args()

    ufo = ufoLib2.Font.open(args.ufo)
    log = []
    for name, boxes in SNAPS.items():
        if name not in ufo:
            continue
        g = ufo[name]
        for c in g.contours:
            for p in c.points:
                for (xmn, xmx, ymn, ymx, axis, target) in boxes:
                    if xmn <= p.x <= xmx and ymn <= p.y <= ymx:
                        before = (round(p.x), round(p.y))
                        if axis == "x":
                            p.x = target
                        else:
                            p.y = target
                        log.append((name, before, (round(p.x), round(p.y)),
                                    p.type or "off"))
    ufo.save(args.ufo, overwrite=True)

    L = ["# Phase 4bis — corrections de kinks appliquées", "",
         "Résolution **arrondi** (tangente verticale) des becs `{ }` et redressement",
         "du fût de `U`. Voir `04-kinks.md` pour le diagnostic.", "",
         "| glyphe | point | avant | après |", "|---|---|---|---|"]
    for name, b, a, t in log:
        L.append(f"| `{name}` | {t} | {b} | {a} |")
    with open(args.report, "w") as f:
        f.write("\n".join(L))
    print(f"kink fixes applied: {len(log)} points")
    for name, b, a, t in log:
        print(f"  {name}: {b} -> {a} ({t})")


if __name__ == "__main__":
    main()
