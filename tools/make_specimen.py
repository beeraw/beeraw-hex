#!/usr/bin/env python3
"""Generate a self-contained HTML type specimen for Beeraw Hex.

Reads BeerawHex-Regular.ttf, embeds it as a base64 @font-face, and writes
specimen.html at the repo root. No external dependencies — opens in any browser.

Usage:  python tools/make_specimen.py
"""
import base64
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTF = os.path.join(ROOT, "fonts", "BeerawHex-Regular.ttf")
OUT = os.path.join(ROOT, "specimen.html")

b64 = base64.b64encode(open(TTF, "rb").read()).decode("ascii")

HTML = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>beeraw·hex — spécimen</title>
<style>
@font-face {{
  font-family: 'Beeraw Hex';
  src: url(data:font/ttf;base64,{b64}) format('truetype');
  font-weight: 400; font-style: normal; font-display: block;
}}
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
.caps-acc {{ font-size: clamp(30px, 6vw, 58px); letter-spacing:.02em; }}
footer {{ margin-top: 6rem; border-top:1px solid var(--line); padding-top:1.4rem;
          font-family: ui-monospace, monospace; font-size:12px; color:var(--muted);
          line-height:1.7; }}
a {{ color: var(--amber); }}
</style>
</head>
<body>
<div class="wrap">

  <p class="tag">Fonte alvéolaire monolinéaire · 90 u · beeraw</p>
  <div class="masthead"><span class="hl">b</span>ee<span class="hl">r</span>aw·hex</div>
  <p class="sub">Un display géométrique hexagonal.</p>

  <section>
    <h2>Jeu de caractères</h2>
    <div class="set">
      <span class="lbl">Capitales</span>ABCDEFGHIJKLMNOPQRSTUVWXYZ
      <span class="lbl">Bas de casse</span>abcdefghijklmnopqrstuvwxyz
      <span class="lbl">Chiffres &amp; signes</span>0123456789 &nbsp; + − = &lt; &gt; % ° $ ¢ £ ¥ € © •
      <span class="lbl">Accents</span>àâäéèêëîïôöùûüÿç ÀÂÄÉÈÊËÎÏÔÖÙÛÜŸÇ œ æ Œ Æ
      <span class="lbl">Diacritiques</span>´ ¨ ¯ ¸ ¢ £ ¥
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
      <div class="card"><div class="big">£12 ¢5 ¥9</div><div class="cap">devises</div></div>
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

open(OUT, "w", encoding="utf-8").write(HTML.format(b64=b64))
kb = (len(HTML) + len(b64)) / 1024
print(f"wrote {OUT}  (~{kb:.0f} KB, font embedded)")
