# -*- coding: utf-8 -*-
"""Render tour.html to a PDF.

Chromium prints the page using the @media print rules in build_tour_page.py,
so the PDF is the same content re-laid-out for paper: light palette, one flow
per page break, and no step split across a page.

    python3 dashboard-mockup/build_tour_page.py
    python3 dashboard-mockup/build_tour_pdf.py
"""
import os

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "tour.html")
OUT = os.path.join(ROOT, "DCO_top_flows.pdf")

_CACHE = os.path.expanduser("~/Library/Caches/ms-playwright")


def _chromium():
    if os.environ.get("DCO_CHROME"):
        return os.environ["DCO_CHROME"]
    for d in sorted(os.listdir(_CACHE), reverse=True) if os.path.isdir(_CACHE) else []:
        if d.startswith("chromium_headless_shell-"):
            exe = os.path.join(_CACHE, d, "chrome-headless-shell-mac-arm64",
                               "chrome-headless-shell")
            if os.path.exists(exe):
                return exe
    return None


with sync_playwright() as p:
    exe = _chromium()
    browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    page = browser.new_page()
    page.goto("file://" + SRC, wait_until="networkidle")
    page.emulate_media(media="print")
    page.wait_for_timeout(1800)          # let the webfonts land before paginating
    page.pdf(path=OUT, format="A4", print_background=True,
             margin={"top": "13mm", "bottom": "15mm", "left": "12mm", "right": "12mm"},
             display_header_footer=True,
             header_template="<div></div>",
             footer_template=(
                 '<div style="width:100%;font:9px Arial;color:#8c8a86;'
                 'padding:0 12mm;display:flex;justify-content:space-between">'
                 "<span>DCO campaign &middot; five paths through the dashboard</span>"
                 '<span class="pageNumber"></span></div>'))
    browser.close()

print(f"wrote {OUT} ({os.path.getsize(OUT) // 1024} KB)")
