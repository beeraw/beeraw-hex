#!/usr/bin/env bash
# Build Beeraw Hex from the parametric source into fonts/.
# The source of truth is font_build.py; the fonts are pure build artifacts.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"

echo ">> font_build.py  -> fonts/BeerawHex-Regular.ttf"
"$PY" font_build.py

# optional TrueType hinting
if command -v ttfautohint >/dev/null 2>&1; then
  echo ">> ttfautohint"
  ttfautohint --stem-width-mode nnn fonts/BeerawHex-Regular.ttf fonts/.autohint.ttf \
    && mv fonts/.autohint.ttf fonts/BeerawHex-Regular.ttf
fi

echo ">> OTF + WOFF2 + WOFF"
"$PY" tools/make_webfonts.py

echo ">> specimen.html"
"$PY" tools/make_specimen.py

echo ">> done"
ls -1 fonts/
