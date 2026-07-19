#!/usr/bin/env bash
# Build the GENERATOR masters (Bold, Wide, Wide Bold) from font_build.py into
# fonts/, then package web fonts and refresh the specimen.
#
# The base "Beeraw Hex" Regular ships *normalised* (ccmp/gasp/GDEF/hinting +
# extra glyphs) and is maintained by tools/pipeline.sh — NOT by this script.
# font_build.py refuses to overwrite it (safety net), so this script only
# (re)builds the masters whose final == the raw generator output. To rebuild the
# Regular, run tools/pipeline.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"

# generator masters = everything in MASTERS except the normalised Regular
GEN=$("$PY" -c "import font_build as fb; print(' '.join('fonts/'+m['filename']+'.ttf' for k,m in fb.MASTERS.items() if k!='Regular'))")

echo ">> font_build.py  -> generator masters"
"$PY" font_build.py            # builds all masters; skips the normalised Regular

# optional TrueType hinting (per master)
if command -v ttfautohint >/dev/null 2>&1; then
  echo ">> ttfautohint"
  for ttf in $GEN; do
    ttfautohint --stem-width-mode nnn "$ttf" fonts/.autohint.ttf \
      && mv fonts/.autohint.ttf "$ttf"
  done
fi

echo ">> OTF + WOFF2 + WOFF (per master)"
# shellcheck disable=SC2086
"$PY" tools/make_webfonts.py $GEN

echo ">> specimen.html"
"$PY" tools/make_specimen.py

# specimen.pdf needs a browser to print it; skip where there isn't one (CI).
if [ -n "${CHROME:-}" ] || [ -e "/Applications/Google Chrome.app" ] \
   || command -v google-chrome chromium chromium-browser >/dev/null 2>&1; then
  echo ">> specimen.pdf"
  "$PY" tools/make_specimen_pdf.py
else
  echo "(no Chrome — skipping specimen.pdf)"
fi

echo ">> done"
ls -1 fonts/
