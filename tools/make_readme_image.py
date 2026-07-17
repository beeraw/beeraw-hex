#!/usr/bin/env python3
"""Render the README specimen image (light + dark) from the shipped TTF.

HTML -> PNG: the page is built with the font embedded as base64, then captured
with headless Chrome, so the browser does the typography (baselines, tracking,
kerning, coloured runs). PIL is only used to trim the trailing background.

Chrome is located automatically; override with CHROME=/path/to/chrome.

Usage:  python tools/make_readme_image.py
"""
import base64
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTF = os.path.join(ROOT, "fonts", "BeerawHex-Regular.ttf")
OUTDIR = os.path.join(ROOT, "images")

WIDTH = 1200        # CSS px; captured at 2x -> 2400 px PNG
SCALE = 2
MAX_HEIGHT = 2000   # generous viewport; trimmed afterwards

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]

THEMES = {
    "light": dict(bg="#faf9f5", ink="#1c1a16", gold="#B8860B", muted="#8a8172",
                  band="#1c1a16", band_fg="#faf9f5"),
    "dark":  dict(bg="#16140f", ink="#f2ede2", gold="#D9A420", muted="#8a8172",
                  band="#2c281f", band_fg="#f2ede2"),
}

HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family:'BH'; src:url(data:font/ttf;base64,{b64}) format('truetype'); }}
:root {{ --bg:{bg}; --ink:{ink}; --gold:{gold}; --muted:{muted};
         --band:{band}; --band-fg:{band_fg}; }}
* {{ margin:0; box-sizing:border-box; }}
html,body {{ background:var(--bg); }}
body {{ font-family:'BH'; color:var(--ink); -webkit-font-smoothing:antialiased; }}
.poster {{ width:{width}px; }}
.tag {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:15px;
        letter-spacing:.32em; text-transform:uppercase; color:var(--gold);
        padding:54px 60px 0; }}
.name {{ font-size:190px; line-height:.9; letter-spacing:-.015em; padding:10px 60px 0; }}
.name .g {{ color:var(--gold); }}
.sub {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:16px;
        letter-spacing:.06em; color:var(--muted); padding:18px 60px 42px; }}
.bar {{ overflow:hidden; white-space:nowrap; line-height:1; padding:26px 60px; }}
.bar.band {{ background:var(--band); color:var(--band-fg); }}
.bar.gold {{ background:var(--gold); color:#1c1a16; }}
.bar.band .g {{ color:var(--gold); }}
.b-lg {{ font-size:118px; letter-spacing:-.01em; }}
.b-md {{ font-size:92px; }}
.word {{ font-size:150px; line-height:1.05; padding:38px 60px 10px;
         letter-spacing:-.01em; }}
.word .g {{ color:var(--gold); }}
.rule {{ height:8px; background:var(--gold); margin-top:30px; }}
.foot {{ display:flex; justify-content:space-between; align-items:baseline;
         font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:15px;
         letter-spacing:.05em; color:var(--muted); padding:30px 60px 46px; }}
</style></head><body>
<div class="poster">
  <div class="tag">Fonte alvéolaire monolinéaire · 90 u</div>
  <div class="name"><span class="g">b</span>ee<span class="g">r</span>aw·hex</div>
  <div class="sub">Display géométrique hexagonal · 172 glyphes · OFL 1.1</div>

  <div class="bar band b-lg">ABCDEFGHIJKLM</div>
  <div class="bar gold b-lg">NOPQRSTUVWXYZ</div>
  <div class="bar b-md">abcdefghijklmnopqrstuvwxyz</div>
  <div class="bar band b-md">0123456789 <span class="g">&amp; @ % € ©</span></div>

  <div class="word">Voix ambigu<span class="g">ë</span></div>

  <div class="rule"></div>
  <div class="foot"><span>« C'est l'été ! » — 20 °C</span><span>beeraw.yt</span></div>
</div>
</body></html>"""


def find_chrome():
    env = os.environ.get("CHROME")
    if env:
        return env
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    for name in ("google-chrome", "chromium", "chromium-browser"):
        p = shutil.which(name)
        if p:
            return p
    sys.exit("Chrome not found — set CHROME=/path/to/chrome")


def complete(path):
    """True once the PNG is fully written (PIL can decode it end to end)."""
    try:
        with Image.open(path) as im:
            im.load()
        return True
    except Exception:
        return False


def screenshot(chrome, page_url, out, profile):
    """Capture page_url to out.

    Chrome 149's headless mode writes the screenshot but then never exits, so
    waiting on the process would hang forever. Poll for a complete file
    instead, then take the process down ourselves.
    """
    if os.path.exists(out):
        os.remove(out)
    proc = subprocess.Popen([
        chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
        "--force-color-profile=srgb", f"--user-data-dir={profile}",
        f"--force-device-scale-factor={SCALE}",
        f"--window-size={WIDTH},{MAX_HEIGHT}",
        f"--screenshot={out}", page_url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            if os.path.exists(out) and os.path.getsize(out) > 0 and complete(out):
                return
            if proc.poll() is not None and not os.path.exists(out):
                raise RuntimeError(f"chrome exited ({proc.returncode}) without a screenshot")
            time.sleep(0.3)
        raise RuntimeError("timed out waiting for the screenshot")
    finally:
        # Wait for Chrome to actually die: it keeps writing its profile while
        # shutting down, and the temp dir cannot be removed under it.
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(os.getpgid(proc.pid), sig)
            except (ProcessLookupError, PermissionError):
                break
            try:
                proc.wait(timeout=10)
                break
            except subprocess.TimeoutExpired:
                continue


def trim(path):
    """Crop the empty background below the poster.

    The background colour is sampled from the bottom-left pixel rather than
    assumed: Chrome's colour management can shift the CSS value by a hair, and
    comparing against the hex literal would mark every pixel as content.
    """
    from PIL import ImageChops

    img = Image.open(path).convert("RGB")
    bg = img.getpixel((0, img.height - 1))
    flat = Image.new("RGB", img.size, bg)
    diff = ImageChops.difference(img, flat).convert("L").point(
        lambda p: 255 if p > 6 else 0)       # ignore antialiasing noise
    box = diff.getbbox()
    if box:
        bottom = min(img.height, box[3] + 46 * SCALE)   # keep the footer padding
        img = img.crop((0, 0, img.width, bottom))
    img.save(path, optimize=True)
    return img


def render(theme, chrome):
    t = THEMES[theme]
    b64 = base64.b64encode(open(TTF, "rb").read()).decode("ascii")
    html = HTML.format(b64=b64, width=WIDTH, **t)

    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, f"specimen-{theme}.png")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        page = os.path.join(tmp, "page.html")
        open(page, "w", encoding="utf-8").write(html)
        screenshot(chrome, f"file://{page}", out, os.path.join(tmp, "profile"))

    img = trim(out)
    kb = os.path.getsize(out) / 1024
    print(f"wrote {out}  ({img.width}x{img.height}, {kb:.0f} KB)")


if __name__ == "__main__":
    chrome = find_chrome()
    for name in THEMES:
        render(name, chrome)
