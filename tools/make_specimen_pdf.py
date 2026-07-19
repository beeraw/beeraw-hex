#!/usr/bin/env python3
"""Render specimen.html to specimen.pdf with headless Chrome.

The PDF is a print/share artifact of the same self-contained specimen — the
fonts travel with it, subset by Chrome. Until now it was produced by hand
(Print to PDF), so it silently went stale: the committed file still embedded
BeerawHex-Regular alone, long after the family grew.

Chrome is located automatically; override with CHROME=/path/to/chrome.

Usage:  python tools/make_specimen_pdf.py
"""
import os
import shutil
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "specimen.html")
OUT = os.path.join(ROOT, "specimen.pdf")

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


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


def print_pdf(chrome, page_url, out, profile):
    """Print page_url to out.

    Like the README image step: Chrome 149's headless mode writes the file but
    then never exits, so poll for the artifact and take the process down
    ourselves instead of waiting on it.
    """
    if os.path.exists(out):
        os.remove(out)
    proc = subprocess.Popen([
        chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
        "--force-color-profile=srgb", f"--user-data-dir={profile}",
        f"--print-to-pdf={out}", page_url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    try:
        deadline = time.time() + 90
        last = -1
        while time.time() < deadline:
            if os.path.exists(out):
                size = os.path.getsize(out)
                # settled: same non-zero size twice in a row
                if size > 0 and size == last:
                    return
                last = size
            if proc.poll() is not None and not os.path.exists(out):
                raise RuntimeError(f"chrome exited ({proc.returncode}) without a PDF")
            time.sleep(0.4)
        raise RuntimeError("timed out waiting for the PDF")
    finally:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(os.getpgid(proc.pid), sig)
            except (ProcessLookupError, PermissionError):
                break
            time.sleep(0.3)
            if proc.poll() is not None:
                break


def main():
    if not os.path.exists(PAGE):
        sys.exit(f"build the specimen first ({PAGE})")
    chrome = find_chrome()
    profile = os.path.join(
        os.environ.get("TMPDIR", "/tmp"), "beerawhex-pdf-profile")
    os.makedirs(profile, exist_ok=True)
    try:
        print_pdf(chrome, "file://" + PAGE, OUT, profile)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    print(f"wrote {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
