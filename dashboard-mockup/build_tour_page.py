# -*- coding: utf-8 -*-
"""Assemble the captured screenshots into a click-through tutorial page.

Reads tour/manifest.json plus the jpgs beside it, embeds each image as a data
URI so the page is self-contained, and writes tour-s2.html at the repo root.

Run capture_tour.py first. Both are scripted so the tutorial can be rebuilt
from the live app whenever the UI changes, which is the whole reason for not
hand-cropping screenshots.
"""
import base64
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TOUR = os.path.join(HERE, "tour")
OUT = os.path.join(os.path.dirname(HERE), "tour.html")

with open(os.path.join(TOUR, "manifest.json")) as f:
    steps = json.load(f)


def data_uri(name):
    jpg = os.path.join(TOUR, name.replace(".png", ".jpg"))
    path = jpg if os.path.exists(jpg) else os.path.join(TOUR, name)
    mime = "jpeg" if path.endswith(".jpg") else "png"
    with open(path, "rb") as fh:
        return f"data:image/{mime};base64," + base64.b64encode(fh.read()).decode()


CSS = """
:root{--paper:#faf9f7;--card:#fff;--ink:#1b1b1a;--mid:#5f5d5a;--faint:#8c8a86;
  --rule:#dcd9d5;--tint:#f1efec;--acc:#b8296e;--acc-soft:#f6e3ed;--ok:#4a7c59;--warn:#a97b22}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --paper:#171514;--card:#201d1c;--ink:#ece9e6;--mid:#b3aeaa;--faint:#7d7873;
  --rule:#3a3634;--tint:#282524;--acc:#e0619b;--acc-soft:#3a2230;--ok:#7fb08e;--warn:#cfa254}}
:root[data-theme="dark"]{--paper:#171514;--card:#201d1c;--ink:#ece9e6;--mid:#b3aeaa;
  --faint:#7d7873;--rule:#3a3634;--tint:#282524;--acc:#e0619b;--acc-soft:#3a2230;
  --ok:#7fb08e;--warn:#cfa254}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font:16px/1.6 "Space Grotesk",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px 100px}
header.hero{padding:54px 0 4px}
.eyebrow{font:500 11px/1 "IBM Plex Mono",monospace;letter-spacing:.15em;
  text-transform:uppercase;color:var(--acc)}
h1{font-size:clamp(30px,5vw,42px);line-height:1.07;margin:12px 0 12px;text-wrap:balance;
  font-weight:700;letter-spacing:-.015em}
.lede{color:var(--mid);max-width:64ch;margin:0;font-size:17px}
.meta{display:flex;gap:9px;flex-wrap:wrap;margin:22px 0 0}
.meta span{font:500 12px/1 "IBM Plex Mono",monospace;background:var(--card);
  border:1px solid var(--rule);border-radius:3px;padding:8px 11px;color:var(--mid)}
.meta span.seat{background:var(--acc-soft);border-color:var(--acc);color:var(--acc);font-weight:600}
.trigger{margin:26px 0 0;padding:15px 18px;background:var(--card);border:1px solid var(--rule);
  border-left:3px solid var(--warn);border-radius:4px;font-size:15px;color:var(--mid)}
.trigger b{color:var(--ink)}
.step{margin:44px 0 0;border:1px solid var(--rule);border-radius:6px;background:var(--card);
  overflow:hidden}
.shead{display:flex;gap:14px;align-items:flex-start;padding:20px 22px 16px}
.num{flex:none;width:34px;height:34px;border-radius:50%;background:var(--acc);color:#fff;
  font:700 16px/34px "Space Grotesk",sans-serif;text-align:center}
.shead h2{font-size:19px;margin:3px 0 0;font-weight:600;flex:1;letter-spacing:-.01em}
.url{display:block;margin:9px 22px 0;font:500 12px/1.5 "IBM Plex Mono",monospace;
  background:var(--tint);border:1px solid var(--rule);border-radius:4px;padding:9px 12px;
  color:var(--ink);overflow-x:auto;white-space:nowrap}
.url b{color:var(--acc);font-weight:600}
figure{margin:16px 0 0;background:var(--tint);border-top:1px solid var(--rule);
  border-bottom:1px solid var(--rule)}
figure img{display:block;width:100%;height:auto}
figcaption{padding:15px 22px;font-size:14.5px;color:var(--mid);background:var(--card)}
figcaption b{color:var(--ink);font-weight:600}
.done{margin:44px 0 0;padding:20px 22px;border:1px solid var(--ok);border-radius:6px;
  background:var(--card);border-left:3px solid var(--ok)}
.done h2{margin:0 0 8px;font-size:19px}
.done p{margin:0;color:var(--mid);font-size:15px}
.note{margin:34px 0 0;padding:16px 18px;background:var(--tint);border-radius:5px;
  font-size:14px;color:var(--mid)}
.note b{color:var(--ink)}
footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--rule);
  font:400 12.5px/1.7 "IBM Plex Mono",monospace;color:var(--faint)}
.toc{display:grid;gap:1px;background:var(--rule);border:1px solid var(--rule);
  border-radius:5px;overflow:hidden;margin:26px 0 0}
.toc a{background:var(--card);padding:12px 16px;text-decoration:none;color:var(--mid);
  font-size:14.5px;transition:background .15s}
.toc a b{color:var(--acc);font-family:"IBM Plex Mono",monospace;font-size:12.5px;
  margin-right:10px;letter-spacing:.06em}
.toc a:hover,.toc a:focus-visible{background:var(--tint);color:var(--ink);outline:none}
.seatband{margin:64px 0 0;font:600 12px/1 "IBM Plex Mono",monospace;letter-spacing:.14em;
  text-transform:uppercase;color:var(--acc);display:flex;align-items:center;gap:14px}
.seatband::after{content:"";flex:1;height:1px;background:var(--rule)}
.flow{margin:26px 0 0;scroll-margin-top:20px}
.fhead{display:flex;gap:13px;align-items:baseline;flex-wrap:wrap}
.fid{font:600 12px/1 "IBM Plex Mono",monospace;color:var(--faint);letter-spacing:.1em}
.fhead h3{font-size:26px;margin:0;font-weight:700;letter-spacing:-.015em;flex:1;min-width:240px}
.rank{font:600 11px/1 "IBM Plex Mono",monospace;background:#fff3c4;color:#6b4e00;
  border-radius:3px;padding:6px 9px;text-transform:uppercase;letter-spacing:.06em}
.shead h4{font-size:18px;margin:3px 0 0;font-weight:600;flex:1;letter-spacing:-.01em}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}

/* ---- print / PDF ------------------------------------------------------
   A screen layout prints badly: dark mode has no meaning on paper, images
   split across page breaks, and a horizontally scrolling URL truncates. */
@media print{
  :root, :root:not([data-theme="light"]), :root[data-theme="dark"]{
    --paper:#fff;--card:#fff;--ink:#1b1b1a;--mid:#4a4845;--faint:#6f6d6a;
    --rule:#c9c6c2;--tint:#f4f2ef;--acc:#a0245f;--acc-soft:#f6e3ed;
    --ok:#3d6a4a;--warn:#8a6318;
  }
  @page{ size:A4; margin:13mm 12mm 15mm; }
  body{font-size:10.5pt;background:#fff}
  .wrap{max-width:none;padding:0}
  .cover{display:block;break-after:page;padding-top:38mm}
  header.hero{break-after:page;padding-top:0}
  .toc a{padding:9px 12px;font-size:11pt}
  .seatband{break-before:page;margin-top:0}
  .flow{break-inside:auto}
  .fhead{break-after:avoid}
  .meta,.trigger{break-after:avoid}
  .step{break-inside:avoid;margin-top:16px;border-color:var(--rule)}
  figure img{max-height:128mm;object-fit:contain;object-position:left top}
  .url{white-space:normal;word-break:break-all;overflow:visible}
  .note,footer{break-before:avoid}
  a{color:inherit;text-decoration:none}
}
@media screen{.cover{display:none}}
@media print{
  .cover h1{font-size:30pt;line-height:1.06;margin:0 0 14px}
  .cover .sub{font-size:13pt;color:var(--mid);max-width:62ch;margin:0 0 30px}
  .cover dl{display:grid;grid-template-columns:auto 1fr;gap:9px 20px;
    font-size:10.5pt;border-top:1px solid var(--rule);padding-top:18px;margin:0}
  .cover dt{font:600 9pt/1.5 "IBM Plex Mono",monospace;letter-spacing:.09em;
    text-transform:uppercase;color:var(--faint)}
  .cover dd{margin:0;color:var(--mid)}
}
"""

TOP = {"S2", "S3", "S6", "S7", "S8"}
steps = [f for f in steps if f["id"] in TOP]

SEAT_ORDER = ["campaign owner", "admin"]
by_seat = {k: [f for f in steps if f["seat"] == k] for k in SEAT_ORDER}

parts = [
    "<title>Five Paths Through the Dashboard</title>",
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&"
    'display=swap">',
    f"<style>{CSS}</style>",
    '<div class="wrap">',
    '<section class="cover">',
    '<div class="eyebrow">GSB \u00b7 DCO housing loan campaign</div>',
    "<h1>Five paths through the dashboard</h1>",
    '<p class="sub">Two paths for the campaign owner, three for the admin. The tasks that '
    "require navigating rather than reading a single screen, each shown step by step on the "
    "real interface.</p>",
    "<dl>"
    "<dt>Prepared</dt><dd>7 September 2026</dd>"
    "<dt>Covers</dt><dd>5 paths, 22 steps, both seats</dd>"
    "<dt>Screens</dt><dd>Captured from the running dashboard, not mocked up</dd>"
    "<dt>Companions</dt><dd>Task list workbook \u00b7 FigJam flow boards \u00b7 seat map</dd>"
    "</dl>",
    "</section>",
    '<header class="hero">',
    '<div class="eyebrow">GSB · DCO campaign · click-through tutorials</div>',
    "<h1>Five paths through the dashboard</h1>",
    '<p class="lede">The tasks that actually require navigating, rather than reading one '
    "screen: two for the campaign owner, three for the admin. Every image is the real dashboard captured from the running app, "
    "with the thing to click ringed in pink. Each step carries the URL that opens that exact "
    "screen, so you can follow along in the app instead of only reading about it.</p>",
    '<nav class="toc">',
]
for seat in SEAT_ORDER:
    for i, fl in enumerate(by_seat[seat], 1):
        parts.append(f'<a href="#{fl["id"]}"><b>{fl["id"]}</b> {fl["title"]}</a>')
parts.append("</nav></header>")

for seat in SEAT_ORDER:
    parts.append(f'<h2 class="seatband">{seat}</h2>')
    for rank, fl in enumerate(by_seat[seat], 1):
        parts += [
            f'<section class="flow" id="{fl["id"]}">',
            '<div class="fhead">',
            f'<span class="fid">{fl["id"]}</span>',
            f"<h3>{fl['title']}</h3>",
            f'<span class="rank">{seat} #{rank}</span>',
            "</div>",
            '<div class="meta">'
            + "".join(f"<span>{m}</span>" for m in fl["meta"]) + "</div>",
            f'<div class="trigger"><b>The trigger.</b> {fl["trigger"]}</div>',
        ]
        for n, st in enumerate(fl["steps"], 1):
            parts += [
                '<section class="step">',
                f'<div class="shead"><div class="num">{n}</div><h4>{st["label"]}</h4></div>',
                f'<code class="url"><b>opens:</b> {st["url"]}</code>',
                f'<figure><img src="{data_uri(st["file"])}" '
                f'alt="Step {n} of {fl["id"]}: {st["label"]}">',
                f'<figcaption>{st["caption"]}</figcaption></figure>',
                "</section>",
            ]
        parts.append("</section>")

parts += [
    '<div class="note"><b>These screenshots are generated, not cropped by hand.</b> '
    "<code>capture_tour.py</code> drives the live app, rings the target element inside the "
    "page itself, and screenshots it. Re-run it after any UI change and every picture here "
    "is current again. That is also why each step shows a URL rather than a description: "
    "neither can quietly drift away from the app.</div>",
    "<footer>DCO campaign · six flows · generated from the running dashboard<br>"
    "Companion to the six-path workbook. All nine flows, including the two not shown "
    "here, are on the FigJam board."
    "</footer>",
    "</div>",
]

with open(OUT, "w") as f:
    f.write("\n".join(parts))
n = sum(len(fl["steps"]) for fl in steps)
print(f"wrote {OUT} ({os.path.getsize(OUT)//1024} KB, {len(steps)} flows, {n} steps)")
