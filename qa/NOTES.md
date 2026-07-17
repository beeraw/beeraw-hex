# QA notes — Beeraw Hex

`tools/qa.sh` runs three gates: structural audit, the monoline non-regression
test (blocking), and `fontbakery check-googlefonts`.

## fontbakery `check-googlefonts` — status

**0 FAIL.** Remaining WARN, justified per acceptance criterion #1:

| Check | Verdict | Justification |
|---|---|---|
| `contour_count` | WARN | Heuristic: several drawn symbols (`#`, `&`, `@`, `%`, `$`) are built from geometric strokes/rings whose contour counts differ from fontbakery's reference table. The glyphs are correct; the reference just doesn't cover this display style. |
| `googlefonts/metadata/family` — lacks article | WARN | GF-onboarding artifact (`article/ARTICLE.en_us.html`, `METADATA.pb`). Only relevant when submitting to the Google Fonts library; not applicable to this standalone repo. |

(Phase 4 added GPOS kerning — 207 effective pairs from `features/kern.fea` —
so the earlier `gpos_kerning_info` WARN is resolved. `math_signs_width` resolved
by giving `< > + = −` a common 412 u advance.)

## Vertical metrics — deviation from the brief's §6 recipe

The brief prescribed a **split-metrics** scheme (sTypo = design values 735/-215,
hhea = usWin = 960/-260). Current fontbakery FAILs that:

- `os2_metrics_match_hhea` requires `hhea.ascent == OS/2.sTypoAscender`
  (and matching descender/lineGap) for consistent linespacing across OSes.
- `typoascender_exceeds_Agrave` requires `sTypoAscender > yMax(Àgrave)` (901).

So all three ascenders are unified at **960 / -260 / 0**, USE_TYPO_METRICS on.
This clears the ink bounds (yMax 915 / yMin -215) — **Ê/Ô/Ä no longer clip** —
and satisfies the normative checks. Line height ≈ 1.22 em.

## Known non-AGL glyph names (legitimate)

`uni00A0` (nbspace) and `uni202F` (narrow no-break space) have no AGLFN name;
`uniXXXX` is their correct production name. fontbakery accepts these.

## Monoline gate

`tools/qa_monoline.py` — per-glyph median stroke via distance transform must
stay in the p5–p95 band **88.5–91.9 u**. Current: **90.0 / 90.0 / 90.0** (PASS).
This is the font's ADN and is checked on every build.
