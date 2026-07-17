# Beeraw Hex

A geometric, strictly **monolinear** (90-unit stroke) display sans, derived from
the hexagonal *alveole* cells of the beeraw honey-brand logo. Flat-topped /
flat-bottomed hexagonal cells, vertical side edges, bevelled and rounded corners.

- **Version:** 1.0 · 172 glyphs · one style (Regular)
- **Scope:** French / Western-European Latin — ASCII, digits, punctuation,
  guillemets, `œ æ Œ Æ`, the full set of French accents, math signs and
  `€ © ® § ¢ £ ¥ …`
- **License:** SIL Open Font License 1.1, Reserved Font Name *"Beeraw Hex"*
  (see [`OFL.txt`](OFL.txt))

## Install

Grab a file from [`fonts/`](fonts/):

| Use | File |
| --- | --- |
| Desktop (hinted) | `BeerawHex-Regular.ttf` |
| Desktop (CFF)    | `BeerawHex-Regular.otf` |
| Web              | `BeerawHex-Regular.woff2` (+ `.woff` fallback) |

```css
@font-face {
  font-family: "Beeraw Hex";
  src: url("BeerawHex-Regular.woff2") format("woff2"),
       url("BeerawHex-Regular.woff")  format("woff");
  font-weight: 400;
  font-display: swap;
}
```

See [`specimen.html`](specimen.html) for a self-contained type specimen.

## Source-first

The single source of truth is the UFO **`sources/BeerawHex-Regular.ufo`**
(+ `sources/features.fea`). The files in `fonts/` are build artifacts — they are
regenerated from the source and never edited by hand.

```
sources/
  BeerawHex-Regular.ufo    # THE SOURCE (cubic UFO)
  features.fea             # OpenType features (ccmp, kern, marks)
  baseline.ttf             # frozen baseline the genesis pipeline reconstructs the UFO from
  ampersand.json           # vectorised design inputs…
  arobase.json / .png      #   …and their reference drawings
  cedille.json / .png
  esperluette.png
features/kern.fea          # GPOS kerning
tools/                     # build + QA pipeline (see below)
font_build.py              # historical parametric generator — kept only for its
                           #   shapely primitives, reused by tools/draw_latin_core.py
fonts/                     # BUILD ARTIFACTS (ttf / otf / woff2 / woff)
specimen.html              # self-contained type specimen
qa/NOTES.md                # fontbakery WARN justifications
OFL.txt / OFL-FAQ.txt      # SIL Open Font License 1.1
FONTLOG.txt                # changelog
.github/workflows/         # CI: build + monoline gate + fontbakery
```

## Build

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r tools/requirements.txt
```

Day-to-day, edit `sources/BeerawHex-Regular.ufo`, then rebuild the artifacts:

```bash
python tools/build.py --tol 1.0                       # UFO -> build/BeerawHex-Regular.ttf (hinted)
cp build/BeerawHex-Regular.ttf fonts/                 # promote to the shipped TTF
python tools/make_webfonts.py fonts/BeerawHex-Regular.ttf   # -> .otf + .woff2 + .woff
```

`tools/pipeline.sh` runs the full deterministic genesis (reconstruct the UFO
from the baseline TTF → add monoline Latin glyphs → normalize → fix kinks →
prepare tables → build + hint into `build/`). Steps 1–3 are the one-time source
genesis; routine work only needs the three commands above.

## The monoline is the DNA

The perpendicular stroke must stay at **90 u** everywhere (measured by distance
transform, not horizontal scan). `tools/qa_monoline.py` fails the build if a
glyph's median band leaves the **88.5–91.9 u** window. Any cleanup must keep
this gate green.

```bash
python tools/qa_monoline.py fonts/BeerawHex-Regular.ttf   # monoline non-regression
python tools/audit.py       fonts/BeerawHex-Regular.ttf   # structural audit
```

CI ([`.github/workflows/font-qa.yml`](.github/workflows/font-qa.yml)) runs the
build, the monoline gate and `fontbakery` (Google Fonts profile) on every push
that touches `sources/`, `features/` or `tools/`. One `fontbakery` check is
allow-listed in `tools/ci_gate.py`: `glyph_coverage` — the font deliberately
targets French/Western-European Latin, not the full GF Latin Core.
