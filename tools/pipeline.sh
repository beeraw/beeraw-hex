#!/usr/bin/env bash
# Full normalisation pipeline, deterministic, from the shipped TTF to the final
# build. Regenerates the UFO source, normalises it, prepares tables/features,
# and builds + hints. Idempotent: always starts from fonts/BeerawHex-Regular.ttf.
#
#   1. ttf_to_ufo    reconstruct cubic UFO from the TTF (faithful, qu2cu)
#   2. normalize     dedupe + insert extrema + straighten (Phase 3)
#   3. prepare_source  gasp + ccmp + combining marks + dottedcircle (Phase 5)
#   4. build         UFO -> TTF via cu2qu @ tol 1.0, strip Mac names, ttfautohint
#
# Ongoing edits should be made to sources/BeerawHex-Regular.ufo directly; then
# run only step 4 (tools/build.py). Steps 1-3 are the one-time source genesis.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"

echo ">> 1/5  reconstruct UFO from TTF"
# baseline-2.004 = the generator's raw Regular with the A/Q/U/s corrections
# (2.000 is kept as history). Regenerate it with:
#   python -c "import font_build as fb; fb.build_font('sources/baseline.ttf', fb.MASTERS['Regular'])"
"$PY" tools/ttf_to_ufo.py sources/baseline.ttf sources/BeerawHex-Regular.ufo
echo ">> 2/5  add monoline-clean Latin glyphs (¢ £ ¥ ¨ ¯ ´ ¸)"
"$PY" tools/draw_latin_core.py
echo ">> 2b/5 redraw glyphs (Z: spur type-7, aux deux coins)"
"$PY" tools/redraw_glyphs.py
echo ">> 3/5  normalize (dedupe / extrema / straighten) — all glyphs incl. new"
"$PY" tools/normalize.py sources/BeerawHex-Regular.ufo sources/BeerawHex-Regular.ufo \
    --report audit/03-corrections.md
echo ">> 3b/5 fix kinks (U / braceleft / braceright)"
"$PY" tools/fix_kinks.py
echo ">> 4/5  prepare source (gasp / ccmp / marks / dottedcircle)"
"$PY" tools/prepare_source.py
echo ">> 5/5  build + hint"
"$PY" tools/build.py --tol 1.0

echo ">> QA"
"$PY" tools/audit.py build/BeerawHex-Regular.ttf --title "Final" > audit/07-final.md
"$PY" tools/qa_monoline.py build/BeerawHex-Regular.ttf | tail -2
echo ">> done -> build/BeerawHex-Regular.ttf"
