#!/usr/bin/env python3
"""CI gate: fail (exit 1) if fontbakery reports any FAIL/FATAL check, except the
ones on ALLOW — tracked design gaps that are not build regressions.

  * glyph_coverage : ¢ (U+00A2) and £ (U+00A3) are not drawn. Adding them is a
    design task (monoline currency glyphs), tracked separately — not a
    regression introduced by the build.

Usage:  python tools/ci_gate.py <fontbakery.json>
"""
import sys
import re
import json

ALLOW = {"glyph_coverage"}


def check_id(key):
    # find the "<FontBakeryCheck:googlefonts/glyph_coverage>" element and return
    # its last path component ("glyph_coverage").
    for part in (key if isinstance(key, list) else [key]):
        m = re.search(r"FontBakeryCheck:([^>]+)>", str(part))
        if m:
            return m.group(1).rsplit("/", 1)[-1]
    return "?"


def main(path):
    data = json.load(open(path))
    blocking = []
    for section in data.get("sections", []):
        for check in section.get("checks", []):
            if check.get("result") in ("FAIL", "FATAL"):
                cid = check_id(check.get("key"))
                if cid not in ALLOW:
                    blocking.append((check.get("result"), cid))
    if blocking:
        print("CI GATE: blocking fontbakery failures:")
        for res, cid in blocking:
            print(f"  {res}  {cid}")
        sys.exit(1)
    print("CI GATE: no blocking fontbakery failures "
          f"(allowlisted: {', '.join(sorted(ALLOW))}).")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "audit/ci-fontbakery.json")
