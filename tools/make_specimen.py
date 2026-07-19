#!/usr/bin/env python3
"""Generate a self-contained HTML type specimen for Beeraw Hex.

Embeds every master as a base64 @font-face and writes specimen.html at the repo
root. No external dependencies — opens in any browser.

The @font-face block is generated from font_build.MASTERS, so adding a master to
that table is enough for it to appear here. WOFF2 is embedded rather than TTF:
the specimen is a browser artifact, and it keeps eight masters lighter than four
TTFs were (~100 KB instead of ~170 KB).

Usage:  python tools/make_specimen.py
"""
import base64
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "fonts")
OUT = os.path.join(ROOT, "specimen.html")

sys.path.insert(0, ROOT)
from font_build import MASTERS, TYPO_FAMILY          # noqa: E402


def embed(name):
    return base64.b64encode(open(os.path.join(FONTS, name), "rb").read()).decode("ascii")


def font_faces():
    """One @font-face per master, keyed by typographic family + weight class."""
    out = []
    for cfg in MASTERS.values():
        woff2 = cfg["filename"] + ".woff2"
        if not os.path.exists(os.path.join(FONTS, woff2)):
            continue
        fam = TYPO_FAMILY.get(cfg.get("width_class", 5), "Beeraw Hex")
        out.append(
            "@font-face {\n"
            "  font-family: '%s';\n"
            "  src: url(data:font/woff2;base64,%s) format('woff2');\n"
            "  font-weight: %d; font-style: normal; font-display: block;\n"
            "}" % (fam, embed(woff2), cfg["weight_class"])
        )
    return "\n".join(out)


FACES = font_faces()

HTML = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>beeraw·hex — spécimen</title>
<style>
{faces}
:root {{
  --bg: #faf9f5; --ink: #1c1a16; --muted: #9a8f7d; --line: #e7e0d2;
  --amber: #B8860B;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#16140f; --ink:#f2ede2; --muted:#7c7361; --line:#2c281f; --amber:#B8860B; }}
}}
* {{ box-sizing: border-box; }}
html {{ background: var(--bg); }}
body {{
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: 'Beeraw Hex', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
}}
.wrap {{ max-width: 1040px; margin: 0 auto; padding: 6vw 5vw 10vw; }}
.tag {{ font-family: ui-monospace, monospace; font-size: 12px; letter-spacing:.14em;
        text-transform: uppercase; color: var(--muted); }}
.masthead {{ font-size: clamp(64px, 16vw, 190px); line-height: .92; margin:.15em 0 .1em;
             letter-spacing:-.01em; }}
.masthead .hl {{ color: #B8860B; }}
.sub {{ font-size: clamp(18px, 3vw, 26px); color: var(--muted); max-width: 30ch; }}
section {{ border-top: 1px solid var(--line); margin-top: 5.5rem; padding-top: 1.6rem; }}
h2 {{ font-family: ui-monospace, monospace; font-weight: 400; font-size: 12px;
      letter-spacing:.14em; text-transform: uppercase; color: var(--amber);
      margin: 0 0 1.4rem; }}
.set {{ font-size: clamp(26px, 4.4vw, 40px); line-height: 1.55; word-spacing:.12em; margin:.2em 0; }}
.set .lbl {{ display:block; font-family: ui-monospace, monospace; font-size:11px;
             letter-spacing:.1em; text-transform:uppercase; color:var(--muted);
             margin-top:1.1rem; }}
.ladder > div {{ line-height: 1.05; margin:.12em 0; letter-spacing:-.005em; }}
.s96 {{ font-size: clamp(40px, 9vw, 92px); }} .s64 {{ font-size: clamp(30px,6vw,60px); }}
.s40 {{ font-size: 40px; }} .s28 {{ font-size: 28px; }} .s20 {{ font-size: 20px; }}
.para {{ font-size: 22px; line-height: 1.5; max-width: 42ch; }}
.para.small {{ font-size: 15px; max-width: 60ch; color: var(--ink); }}
.grid {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(210px,1fr)); gap:2rem 1.2rem; }}
.card .big {{ font-size: clamp(26px, 3.2vw, 33px); line-height:1.05; overflow-wrap:break-word; }}
.card .cap {{ font-family: ui-monospace, monospace; font-size:11px; color:var(--muted);
              letter-spacing:.06em; margin-top:.4rem; }}
.amp {{ font-size: clamp(120px, 28vw, 300px); line-height:.8; }}
.wt {{ line-height: 1.02; margin:.08em 0; letter-spacing:-.005em; font-size: clamp(40px, 9vw, 92px); }}
.wt .lbl {{ display:inline-block; width:5.5ch; font-family: ui-monospace, monospace;
            font-size:11px; letter-spacing:.1em; text-transform:uppercase;
            color:var(--muted); vertical-align:middle; }}
.b {{ font-weight: 700; }}
.w100 {{ font-weight: 100; }} .w300 {{ font-weight: 300; }} .w400 {{ font-weight: 400; }}
.wide {{ font-family: 'Beeraw Hex Wide', system-ui, sans-serif; }}
.axis {{ display:grid; grid-template-columns: 1fr 1fr; gap: 0 2.2rem; }}
.axis h3 {{ font-family: ui-monospace, monospace; font-weight:400; font-size:11px;
            letter-spacing:.12em; text-transform:uppercase; color:var(--muted);
            margin:0 0 .6rem; }}
.axis .row {{ font-size: clamp(24px, 3.6vw, 40px); line-height:1.25; }}
.caps-acc {{ font-size: clamp(30px, 6vw, 58px); letter-spacing:.02em; }}
footer {{ margin-top: 6rem; border-top:1px solid var(--line); padding-top:1.4rem;
          font-family: ui-monospace, monospace; font-size:12px; color:var(--muted);
          line-height:1.7; }}
a {{ color: var(--amber); }}
</style>
</head>
<body>
<div class="wrap">

  <p class="tag">Fonte alvéolaire monolinéaire · 8 masters · 2 axes · beeraw</p>
  <div class="masthead"><span class="hl">b</span>ee<span class="hl">r</span>aw·hex</div>
  <p class="sub">Un display géométrique hexagonal, en quatre graisses et deux chasses.</p>

  <section>
    <h2>Graisses</h2>
    <div class="wt w100"><span class="lbl">100 · 40</span>beeraw hexagone</div>
    <div class="wt w300"><span class="lbl">300 · 64</span>beeraw hexagone</div>
    <div class="wt w400"><span class="lbl">400 · 90</span>beeraw hexagone</div>
    <div class="wt b"><span class="lbl">700 · 130</span>beeraw hexagone</div>
    <p class="para small">La monoline est l'ADN : une graisse n'est pas un dessin
    à part, c'est la même ossature — mêmes chasses, même crénage — dont le trait
    passe de 40 à 130 unités. UltraLight et Light portent leurs propres noms
    typographiques ; Regular et <b class="b">Bold</b> restent liés en RIBBI.</p>
  </section>

  <section>
    <h2>Chasses — les deux axes</h2>
    <div class="axis">
      <div>
        <h3>Normal</h3>
        <div class="row w100">hexagone</div>
        <div class="row w300">hexagone</div>
        <div class="row w400">hexagone</div>
        <div class="row b">hexagone</div>
      </div>
      <div class="wide">
        <h3>Wide ×1,35</h3>
        <div class="row w100">hexagone</div>
        <div class="row w300">hexagone</div>
        <div class="row w400">hexagone</div>
        <div class="row b">hexagone</div>
      </div>
    </div>
    <p class="para small" style="margin-top:1.6rem">L'axe de chasse élargit les
    demi-largeurs des ronds et l'espacement de 35 % <b class="b">sans toucher au
    trait</b>. Comme chaque fût est tracé à largeur fixe, élargir ne peut pas
    l'épaissir : le gate monolinéaire tient par construction, à n'importe quelle
    graisse et n'importe quelle chasse.</p>
  </section>

  <section>
    <h2>Jeu de caractères</h2>
    <div class="set">
      <span class="lbl">Capitales</span>ABCDEFGHIJKLMNOPQRSTUVWXYZ
      <span class="lbl">Bas de casse</span>abcdefghijklmnopqrstuvwxyz
      <span class="lbl">Chiffres &amp; signes</span>0123456789 &nbsp; + − = &lt; &gt; % ° $ ¢ £ ¥ € © •
      <span class="lbl">Accents</span>àâäéèêëîïôöùûüÿç ÀÂÄÉÈÊËÎÏÔÖÙÛÜŸÇ œ æ Œ Æ
      <span class="lbl">Diacritiques</span>´ ¨ ¯ ¸ &nbsp; <span class="lbl">v2.001</span>¢ £ ¥ (nouveaux)
      <span class="lbl">Ponctuation &amp; symboles</span>. , ; : ! ? ¡ ¿ … – — · &nbsp; « » ‹ › ' ' " " &nbsp; ( ) [ ] {{ }} / \\ | @ # &amp; * _ ^ ~ `
    </div>
  </section>

  <section>
    <h2>Échelle</h2>
    <div class="ladder">
      <div class="s96">Voix ambiguë</div>
      <div class="s64">Portez ce vieux whisky au juge</div>
      <div class="s40">Le vif zéphyr jubile sur les kumquats du clown</div>
      <div class="s28">Dès Noël où un zéphyr haï me vêt de glaçons würmiens</div>
      <div class="s20">Voyez le brick géant que j'examine près du wharf — 20 % de réduction !</div>
    </div>
  </section>

  <section>
    <h2>Texte</h2>
    <p class="para">« C'est l'été », dit-elle — et le cœur de l'œuvre s'ouvre à midi
    précis. Où naître, être, paraître ? Ça œuvre.</p>
    <p class="para small">Le générateur paramétrique dessine chaque glyphe comme
    une réunion d'alvéoles hexagonales à bords verticaux et coins biseautés, puis
    l'exporte en contours TrueType. Le trait perpendiculaire reste rigoureusement
    monolinéaire à 90 unités sur tout le jeu — c'est l'ADN de la fonte. Espacement
    par groupes, crénage GPOS (207 paires), débords optiques et accentués en
    composants complètent l'ensemble. « Handgloves », « boulevard », « Ça y est ».</p>
  </section>

  <section>
    <h2>Esperluette</h2>
    <div class="amp">&amp;</div>
    <p class="para small">R&amp;D · Art &amp; Co · Léa &amp; Tom · Design &amp;
    Développement — tracée d'après un dessin original.</p>
  </section>

  <section>
    <h2>En vitrine</h2>
    <div class="grid">
      <div class="card"><div class="big">AVANT</div><div class="cap">crénage AV / NT</div></div>
      <div class="card"><div class="big">«Angleterre»</div><div class="cap">guillemets</div></div>
      <div class="card"><div class="big">cœur œuvre</div><div class="cap">ligatures œ</div></div>
      <div class="card"><div class="big">Ta Vo Ye</div><div class="cap">paires crénées</div></div>
      <div class="card"><div class="big">12,50 €</div><div class="cap">euro</div></div>
      <div class="card"><div class="big">TVA 20 %</div><div class="cap">pourcent</div></div>
      <div class="card"><div class="big">© 2026</div><div class="cap">copyright</div></div>
      <div class="card"><div class="big">£12 ¢5 ¥9</div><div class="cap">devises (v2.001)</div></div>
      <div class="card"><div class="big">Réf. #42</div><div class="cap">dièse</div></div>
    </div>
  </section>

  <section>
    <h2>Capitales accentuées (sans écrêtage)</h2>
    <div class="caps-acc">ÊTRE · OÙ · NAÎTRE · ÇA · ŒUVRE · FLÛTE · HÔTEL · ÉTÉ</div>
  </section>

  <footer>
    beeraw·hex — SIL Open Font License 1.1 ·
    <a href="https://beeraw.yt">beeraw.yt</a>
  </footer>

</div>
</body>
</html>
"""

page = HTML.format(faces=FACES)
open(OUT, "w", encoding="utf-8").write(page)
n = FACES.count("@font-face")
print(f"wrote {OUT}  (~{len(page)/1024:.0f} KB, {n} masters embedded)")
