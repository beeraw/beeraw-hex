#!/usr/bin/env bash
# QA gate for Beeraw Hex.
#   1. structural audit (points, names, metrics, tables)
#   2. monoline non-regression (distance transform, band 88.5-91.9)   <- blocking
#   3. fontbakery googlefonts profile (if installed)
set -uo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
TTF="${1:-fonts/BeerawHex-Regular.ttf}"

echo "==================== AUDIT ===================="
"$PY" tools/audit.py "$TTF"

echo
echo "================= MONOLINE QA ================="
"$PY" tools/qa_monoline.py "$TTF"
MONO=$?

echo
if "$PY" -c "import fontbakery" 2>/dev/null; then
  echo "================= FONTBAKERY =================="
  mkdir -p qa
  "$PY" -m fontbakery check-googlefonts -l WARN --html qa/report.html "$TTF" || true
else
  echo "(fontbakery not installed — skipping; pip install fontbakery)"
fi

exit $MONO
