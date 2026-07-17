import base64, os
ROOT = "/Users/jeanluc/working/logo"
b64 = base64.b64encode(open(f"{ROOT}/fonts/BeerawHex-Regular.ttf", "rb").read()).decode()

HTML = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family:'BH'; src:url(data:font/ttf;base64,{b64}) format('truetype'); }}
:root {{ --bg:#faf9f5; --ink:#1c1a16; --gold:#B8860B; --cream:#faf9f5; }}
* {{ margin:0; box-sizing:border-box; }}
body {{ font-family:'BH'; background:var(--bg); color:var(--ink);
        -webkit-font-smoothing:antialiased; }}
.poster {{ width:1200px; }}
.pad {{ padding:0 60px; }}
.tag {{ font-family:ui-monospace,monospace; font-size:15px; letter-spacing:.32em;
        text-transform:uppercase; color:var(--gold); padding:54px 60px 0; }}
.name {{ font-size:210px; line-height:.86; letter-spacing:-.015em; padding:6px 60px 0; }}
.name .g {{ color:var(--gold); }}
.sub {{ font-family:ui-monospace,monospace; font-size:16px; letter-spacing:.06em;
        color:#8a8172; padding:16px 60px 40px; }}
.bar {{ overflow:hidden; white-space:nowrap; line-height:1; padding:26px 60px; }}
.bar.ink   {{ background:var(--ink);  color:var(--cream); }}
.bar.gold  {{ background:var(--gold); color:var(--ink); }}
.bar.ink .g {{ color:var(--gold); }}
.b-lg {{ font-size:120px; letter-spacing:-.01em; }}
.b-md {{ font-size:96px; }}
.hero {{ font-size:300px; line-height:.9; letter-spacing:-.02em; padding:30px 60px 10px; }}
.hero .g {{ color:var(--gold); }}
.word {{ font-size:150px; line-height:1.02; padding:30px 60px 6px; letter-spacing:-.01em; }}
.foot {{ display:flex; justify-content:space-between; align-items:baseline;
         font-family:ui-monospace,monospace; font-size:15px; letter-spacing:.05em;
         color:#8a8172; padding:34px 60px 56px; }}
.rule {{ height:8px; background:var(--gold); }}
</style></head><body>
<div class="poster">
  <div class="tag">Fonte alvéolaire monolinéaire · 90 u</div>
  <div class="name"><span class="g">b</span>ee<span class="g">r</span>aw·hex</div>
  <div class="sub">Display géométrique hexagonal · 153 glyphes · OFL 1.1</div>

  <div class="bar ink b-lg">ABCDEFGHIJKLM</div>
  <div class="bar gold b-lg">NOPQRSTUVWXYZ</div>
  <div class="bar b-md" style="color:var(--ink)">abcdefghijklmnopqrstuvwxyz</div>
  <div class="bar ink b-md">0123456789 <span class="g">&amp; @ % € ©</span></div>

  <div class="hero">Ça<span class="g">&amp;</span></div>
  <div class="word">Voix<br>ambiguë</div>

  <div class="rule"></div>
  <div class="foot"><span>« C'est l'été ! » — 20 °C</span><span>beeraw.yt</span></div>
</div>
</body></html>"""
open(f"{ROOT}/poster.html", "w").write(HTML)
print("wrote poster.html")
