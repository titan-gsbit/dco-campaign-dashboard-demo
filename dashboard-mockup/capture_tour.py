# -*- coding: utf-8 -*-
"""Screenshot the running dashboard with the target button ringed, one image per
step of a navigation flow.

The point of scripting this rather than taking screenshots by hand: a tutorial
built from stale images lies the moment a column moves. Re-run this and every
picture is current. That is also why the flows point at real URLs, the two
things stay honest together.

    streamlit run streamlit_app/streamlit_app.py --server.port 8507
    python3 dashboard-mockup/capture_tour.py

Writes PNGs into dashboard-mockup/tour/.
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = os.environ.get("DCO_BASE", "http://localhost:8507")
# The pinned playwright build may not match what is on disk. Fall back to whatever
# headless shell is cached rather than forcing a download on every machine.
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
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tour")
os.makedirs(OUT, exist_ok=True)

# Injected into the page: rings one element, dims everything else, numbers it.
HL = """
([sel, label, idx]) => {
  document.querySelectorAll('.__tourhl,.__tourbadge').forEach(e => e.remove());
  const CANDIDATES = '[data-testid="stMetric"],button,[data-testid="stAlert"],'
    + '[data-testid="stCode"],[data-testid="stExpander"],[data-testid="stVegaLiteChart"],'
    + '[data-testid="stDataFrame"],[data-testid="stTextInput"],[data-testid="stVerticalBlock"],'
    + '[data-testid="stHorizontalBlock"],div';
  const area = e => { const r = e.getBoundingClientRect(); return r.width * r.height; };
  // Smallest element containing the text, not the first. The first match is usually
  // the whole page section, which rings everything and points at nothing.
  const smallestWith = (txt, within) => {
    const want = txt.toLowerCase();
    const pool = [...(within || document).querySelectorAll(CANDIDATES)]
      .filter(x => (x.innerText || '').toLowerCase().includes(want))
      .filter(x => { const r = x.getBoundingClientRect(); return r.width > 24 && r.height > 12; });
    return pool.sort((a, b) => area(a) - area(b))[0] || null;
  };
  let el = null;
  if (sel.startsWith('table:')) {
    const card = smallestWith(sel.slice(6));
    const host = card && card.closest('[data-testid="stVerticalBlock"]') || card;
    el = host && host.querySelector('[data-testid="stDataFrame"]');
  } else if (sel.startsWith('chart:')) {
    // Ring the chart inside the card whose title matches, since the title itself
    // sits in a sibling, not in the chart.
    const card = smallestWith(sel.slice(6));
    const host = card && card.closest('[data-testid="stVerticalBlock"]') || card;
    el = host && (host.querySelector('[data-testid="stVegaLiteChart"]')
                  || host.querySelector('canvas, svg'));
  } else if (sel.startsWith('text:')) {
    el = smallestWith(sel.slice(5));
  } else {
    el = document.querySelector(sel);
  }
  if (!el) return 'NOTFOUND';
  el.scrollIntoView({block: 'center'});
  const r = el.getBoundingClientRect();
  const ring = document.createElement('div');
  ring.className = '__tourhl';
  Object.assign(ring.style, {position:'fixed', left:(r.left-8)+'px', top:(r.top-8)+'px',
    width:(r.width+16)+'px', height:(r.height+16)+'px', border:'3px solid #b8296e',
    borderRadius:'8px', boxShadow:'0 0 0 9999px rgba(27,27,26,.45)', zIndex:2147483646,
    pointerEvents:'none'});
  document.body.appendChild(ring);
  const badge = document.createElement('div');
  badge.className = '__tourbadge'; badge.textContent = idx;
  Object.assign(badge.style, {position:'fixed', left:(r.left-22)+'px', top:(r.top-22)+'px',
    width:'32px', height:'32px', borderRadius:'50%', background:'#b8296e', color:'#fff',
    font:'700 16px/32px Arial', textAlign:'center', zIndex:2147483647, pointerEvents:'none',
    boxShadow:'0 2px 8px rgba(0,0,0,.35)'});
  document.body.appendChild(badge);
  if (label) {
    const tip = document.createElement('div');
    tip.className = '__tourbadge'; tip.textContent = label;
    const below = r.top + r.height + 14;
    Object.assign(tip.style, {position:'fixed', left:Math.max(8, r.left-8)+'px',
      top:(below + 120 > window.innerHeight ? r.top - 52 : below)+'px',
      background:'#b8296e', color:'#fff', font:'600 14px/1.45 Arial', padding:'9px 13px',
      borderRadius:'6px', zIndex:2147483647, pointerEvents:'none', maxWidth:'420px',
      boxShadow:'0 3px 12px rgba(0,0,0,.28)'});
    document.body.appendChild(tip);
  }
  return 'ok';
}
"""

# TOP is the deliverable set: the owner's top tasks collapse into two paths, not
# three, because O3 and O6 are the head and tail of the same walk. S4 stays
# defined here as a real flow, it is simply not one of the five top paths.
TOP = {"S2", "S3", "S6", "S7", "S8"}

# One entry per flow. Steps carry the real URL, the element to ring, the
# instruction, and optionally `do`: interactions to perform before capturing,
# because some states (a resolved lead, an open form) cannot be deep-linked.
FLOWS = [
 {"id": "S2", "seat": "campaign owner", "title": "The disbursed number dropped. Why?",
  "trigger": "Monday morning. The delta on the Disbursed tile is red, and there are ten "
             "minutes before the meeting.",
  "meta": ["4 clicks", "about 60 seconds", "output: a message to the admin"],
  "steps": [
   ("/?seat=owner", "text:Disbursed ≥", None,
    "The Disbursed tile is behind plan. Click it.",
    "Overview is the owner's landing screen, so the bad number is already in front of them."),
   ("/loan_funnel?seat=owner", "text:Steepest drop", None,
    "Read the alert. It names the drop AND who owns the fix.",
    "Qualified leads to application, 26%, 881 leads lost. Level 4 of the KPI framework, so "
    "this belongs to GSB credit, not to media and not to branch follow-up."),
   ("/loan_funnel?seat=owner", "chart:Where the money leaks", None,
    "Click the failing stage bar to see who is stuck there.",
    "Every bar is a filter in disguise. Clicking one opens the customer list already filtered."),
   ("/customers?seat=owner&stage=Booked&branch_name=Chiang%20Mai", "text:Drilled", None,
    "The chips show exactly which slice you are looking at.",
    "Click an x to widen back out. The trail is always visible, so you cannot lose track of "
    "which filter produced the number on screen."),
   ("/customers?seat=owner&stage=Booked&branch_name=Chiang%20Mai", "text:leads |", None,
    "Copy this line. It is the whole finding in one paste.",
    "The owner cannot change a lead, so the path has to end in something they can send."),
  ]},

 {"id": "S3", "seat": "campaign owner",
  "title": "One segment costs five times more. Cut it?",
  "trigger": "First-Home Urban Starters is taking over half the budget. The question is "
             "whether that is a problem or just how the segment works.",
  "meta": ["3 clicks", "about 90 seconds", "output: a budget verdict"],
  "steps": [
   ("/lead_quality?seat=owner", "chart:Cost per lead vs qualified rate", None,
    "Find the segment that is expensive without being better.",
    "First-Home Urban Starters costs ฿350 per lead. The Monthly Relief costs ฿100. Both sit "
    "at a similar qualified rate, which is the whole problem: you are paying three and a "
    "half times more for the same quality of lead."),
   ("/business?seat=owner", "table:Unit economics by segment", None,
    "Read the ROAS column. That is where the gap actually opens up.",
    "First-Home Urban Starters returns 0.29x. Family Upgraders returns 1.71x, roughly six "
    "times better. FHB costs ฿13,404 per loan against ฿2,616, takes ฿335k of a ฿630k budget, "
    "and returns ฿66M. The Optimizer returns ฿68M on ฿170k, so the same money buys about "
    "twice the lending somewhere else."),
   ("/loan_funnel?seat=owner", "chart:Cohort maturity", None,
    "Before cutting, check the number is not just young data.",
    "Read DOWN a column to compare weeks fairly. About 30% of every segment's leads are "
    "under four weeks old, so immaturity is dragging all five down together, not FHB alone."),
   ("/loan_funnel?seat=owner", "text:Maturity gate", None,
    "Toggle the gate. Here it confirms the finding rather than rescuing it.",
    "Gating lifts FHB's application rate from 23.9% to 28.1%, and every other segment by a "
    "similar 3 to 4 points. The ranking does not change, so maturity is not the explanation."),
   ("/loan_funnel?seat=owner", "text:Stage to stage", None,
    "Now the verdict. FHB converts fine. It is the price that is wrong.",
    "All five segments convert within a few points of each other. The entire spread is in "
    "cost, not quality, which means this is a bidding and targeting problem for the agency, "
    "not a lead-quality problem for the branches."),
  ]},

 {"id": "S4", "seat": "campaign owner", "title": "Getting a number you can defend on Friday",
  "trigger": "Thursday afternoon. Building the weekly deck, and the numbers will be "
             "challenged before they are believed.",
  "meta": ["2 clicks", "about 20 seconds", "output: a stamped CSV"],
  "steps": [
   ("/business?seat=owner", "text:Data as of", None,
    "Check the freshness strip before you quote anything.",
    "Five sources, each with its own as-of date. This footer is on every page, so the check "
    "costs nothing and happens before the meeting rather than during it."),
   ("/business?seat=owner", "text:KPI definitions", None,
    "The definition version travels with the number.",
    "v1.1 corrected three denominators. A number quoted under v1.0 is not comparable to one "
    "quoted under v1.1, which is exactly why the version is on screen."),
   ("/engagement?seat=owner", "text:Export scorecard", None,
    "Export at the current filters. Counts and baht only.",
    "Rates are left derived so the recipient can re-aggregate. Contact fields are never "
    "included in an owner export."),
  ]},

 {"id": "S6", "seat": "admin", "title": "A batch of branch outcomes needs keying",
  "trigger": "A batch of follow-up outcomes comes back from the branches. How they arrive "
             "is still an open question, so this path assumes only that they arrive "
             "together and have to be keyed one by one.",
  "meta": ["keyboard only", "under 25s per record", "output: an appended event"],
  "steps": [
   ("/worklist?seat=admin", "text:SLA compliance", None,
    "The queue header tells you how far behind follow-up already is.",
    "21% SLA compliance and a median of 26 hours against a 24-hour target. These numbers "
    "only exist because outcomes get keyed, which is the job on this screen."),
   ("/worklist?seat=admin", "text:Key an outcome", None,
    "Paste the lead id or phone straight from the branch report.",
    "The field is the entry point, not a menu. No mouse needed from here on."),
   ("/worklist?seat=admin", "text:30d waiting",
    [["fill", "input[aria-label='Lead id or phone']", "L200041"], ["press", "Enter"],
     ["wait", 2500]],
    "The record resolves inline. Check the name and branch match the report.",
    "Name, lead id, branch, stage and how long it has been waiting, all before you type "
    "anything else."),
   ("/worklist?seat=admin", "text:Reason (required",
    [["fill", "input[aria-label='Lead id or phone']", "L200041"], ["press", "Enter"],
     ["wait", 2500]],
    "Tab to status, then reason. Reason is mandatory on a terminal status.",
    "Free text is never a substitute for a reason code, because free text cannot feed a KPI."),
   ("/worklist?seat=admin", "text:Save and next",
    [["fill", "input[aria-label='Lead id or phone']", "L200041"], ["press", "Enter"],
     ["wait", 2500]],
    "Enter saves and returns focus to the field for the next record.",
    "One event appended with actor, reason and timestamp. Nothing is overwritten, which is "
    "what makes keying at speed safe."),
  ]},

 {"id": "S7", "seat": "admin", "title": "That one was keyed wrong",
  "trigger": "An hour later the branch says the status was for a different customer.",
  "meta": ["3 clicks", "output: a correcting event, not an edit"],
  "steps": [
   ("/worklist?seat=admin", "text:Key an outcome", None,
    "Pull the record back up the same way you keyed it.",
    "Corrections use the same entry point as the original, so there is nothing new to learn."),
   ("/worklist?seat=admin", "text:Reason (required",
    [["fill", "input[aria-label='Lead id or phone']", "L200041"], ["press", "Enter"],
     ["wait", 2500]],
    "Choose keying_correction from the reason list.",
    "There is no edit and no delete anywhere on this screen. A correction is a new event, "
    "which is why the reason list carries a code for it."),
   ("/worklist?seat=admin", "text:Save and next",
    [["fill", "input[aria-label='Lead id or phone']", "L200041"], ["press", "Enter"],
     ["wait", 2500]],
    "Save. Both the error and its correction stay on the record.",
    "An audit that shows an overwrite is worse than no audit. Every level-3 KPI restates on "
    "the next nightly build."),
  ]},

 {"id": "S8", "seat": "admin", "title": "Are the numbers still trustworthy?",
  "trigger": "Noticed in passing, from any page. The admin is the only seat that can act "
             "on a broken feed.",
  "meta": ["2 clicks", "output: a verdict, and an acknowledgement the owner can see"],
  "steps": [
   ("/?seat=admin", "text:Data as of", None,
    "The freshness strip is on every page. A red chip is your entry point.",
    "In this mock all five sources are green, so there is nothing red to click today. On a "
    "bad day the stale source is the one you click."),
   ("/data_health?seat=admin", "text:Branch keying", None,
    "Branch keying is the manual source, and the one that goes stale.",
    "It goes stale exactly when the worklist has not been worked, so a stale feed here and a "
    "keying backlog are the same failure wearing two hats."),
   ("/data_health?seat=admin", "text:Lead → CIF", None,
    "Match rates are what decide whether a number is quotable at all.",
    "Unmatched leads are counted and shown, never dropped. A rising unmatched count is the "
    "earliest warning that the funnel is understated."),
   ("/data_health?seat=admin", "text:Acknowledge", None,
    "Acknowledge a known issue so the owner sees amber instead of red.",
    "Amber tells the owner somebody is on it. That one action serves both seats."),
  ]},
]


def main():
    only = set(sys.argv[1:])
    manifest = []
    with sync_playwright() as p:
        exe = _chromium()
        browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        for flow in FLOWS:
            if only and flow["id"] not in only:
                continue
            print(f"\n{flow['id']} — {flow['title']}")
            entries = []
            for n, (path, target, do, label, caption) in enumerate(flow["steps"], 1):
                page.goto(BASE + path, wait_until="networkidle")
                page.wait_for_timeout(2600)
                for act in (do or []):
                    try:
                        if act[0] == "fill":
                            page.fill(act[1], act[2])
                        elif act[0] == "click":
                            page.click(act[1])
                        elif act[0] == "press":
                            page.keyboard.press(act[1])
                        elif act[0] == "wait":
                            page.wait_for_timeout(act[1])
                    except Exception as e:                      # noqa: BLE001
                        print(f"    !! action {act[0]} failed: {e}", file=sys.stderr)
                res = page.evaluate(HL, [target, f"{n}. {label}", n])
                page.wait_for_timeout(250)
                sid = f"{flow['id'].lower()}-{n}"
                page.screenshot(path=os.path.join(OUT, f"{sid}.png"))
                entries.append({"id": sid, "url": path, "label": label, "caption": caption,
                                "file": f"{sid}.png", "found": res != "NOTFOUND"})
                flag = "ok " if res != "NOTFOUND" else "MISS"
                print(f"  {sid:8} {flag}  {target}")
            manifest.append({**{k: v for k, v in flow.items() if k != "steps"},
                             "steps": entries})
        browser.close()
    # A partial run must not delete the flows it did not capture: merge over the
    # existing manifest, keyed by flow id, preserving the FLOWS order.
    path = os.path.join(OUT, "manifest.json")
    prev = {}
    if os.path.exists(path):
        with open(path) as f:
            prev = {fl["id"]: fl for fl in json.load(f)}
    prev.update({fl["id"]: fl for fl in manifest})
    order = [f["id"] for f in FLOWS]
    merged = [prev[i] for i in order if i in prev]
    with open(path, "w") as f:
        json.dump(merged, f, indent=2)
    miss = [s["id"] for fl in manifest for s in fl["steps"] if not s["found"]]
    tot = sum(len(fl["steps"]) for fl in manifest)
    print(f"\n{tot - len(miss)}/{tot} steps captured -> {OUT}")
    if miss:
        print("MISSED:", ", ".join(miss))


if __name__ == "__main__":
    main()
