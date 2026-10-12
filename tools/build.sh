#!/usr/bin/env bash
# Build the GENERATOR masters (every master but the Regular) from font_build.py
# into fonts/, then package web fonts and refresh the specimen. The generator
# delivers them complete: glyphs, ccmp / GDEF / gasp and ttfautohint hinting.
#
# The base "Beeraw Hex" Regular goes through tools/pipeline.sh (cubic UFO,
# normalised outlines) — NOT through this script. font_build.py skips it, so to
# rebuild the Regular, run tools/pipeline.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"

# generator masters = everything in MASTERS except the pipeline-built Regular
GEN=$("$PY" -c "import font_build as fb; print(' '.join('fonts/'+m['filename']+'.ttf' for k,m in fb.MASTERS.items() if k!='Regular'))")

echo ">> font_build.py  -> generator masters"
"$PY" font_build.py            # builds all masters; skips the pipeline-built Regular

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
