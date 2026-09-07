# ponytail: one smoke test — every page renders for both seats, the gate holds,
# and the three corrected denominators stay corrected.
from streamlit.testing.v1 import AppTest

READ_PAGES = ["app_pages/exec.py", "app_pages/engagement.py", "app_pages/lead_quality.py",
              "app_pages/loan_funnel.py", "app_pages/business.py", "app_pages/customers.py",
              "app_pages/customer_detail.py", "app_pages/dictionary.py"]
ADMIN_PAGES = ["app_pages/worklist.py", "app_pages/data_health.py",
               "app_pages/campaign_setup.py", "app_pages/leads_import.py"]

USERS = {"marketing": {"username": "marketing.gsb", "name": "Marketing (GSB)",
                       "role": "marketing"},
         "viewer": {"username": "owner.gsb", "name": "Campaign owner (GSB)",
                    "role": "viewer"}}


def run(page, role, extra=None):
    at = AppTest.from_file(page, default_timeout=90)
    at.session_state["auth_user"] = USERS[role]
    at.session_state["drill"] = {}
    at.session_state["maturity_gate"] = True
    for k, v in (extra or {}).items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, f"{page} [{role}]: {at.exception[0].value if at.exception else ''}"
    return at


LEAD = {"selected_lead": "L200041", "list_order": ["L200041"]}

for p in READ_PAGES + ADMIN_PAGES:
    run(p, "marketing", LEAD)
    print("ok marketing", p)

for p in READ_PAGES:
    run(p, "viewer", LEAD)
    print("ok viewer   ", p)

# the gate: write pages must stop the read-only seat
for p in ADMIN_PAGES:
    at = run(p, "viewer")
    assert at.error, f"{p} should be marketing-only"
print("ok gate      viewer blocked from", len(ADMIN_PAGES), "write pages")

# auth itself
import auth  # noqa: E402
h = auth.hash_password("correct horse")
assert auth.verify_password("correct horse", h), "password verify broken"
assert not auth.verify_password("wrong", h), "password verify accepts anything"
assert "$" in h and "correct horse" not in h, "password stored in the clear"
assert auth.PERMISSIONS["worklist"]["read"] == {"marketing"}, "worklist not gated"
assert not any("viewer" in v["write"] for v in auth.PERMISSIONS.values()), \
    "viewer has a write permission somewhere"
print(f"ok auth      {len(auth.PERMISSIONS)} modules, viewer writes nothing")

# ---- the three corrected denominators (seat map F1-F3) ----
import common, kpi  # noqa: E402

cv = common.customer_view.__wrapped__()

n_submitted = int(cv.app_ts.notna().sum())
n_decided = int(cv.app_status.isin(["Approved", "Rejected"]).sum())
assert n_submitted > n_decided, "fixture has no pending applications — fault F3 untestable"
assert kpi.approval_rate(cv) < kpi.approval_rate_decided(cv), \
    "F3: approval rate must divide by SUBMITTED applications (brief §7)"

assert len(kpi.qualified_leads(cv)) < len(cv), "fixture has no unqualified leads"
assert kpi.application_rate(cv) > (cv.app_ts.notna().sum() / len(cv)), \
    "F2: application rate must divide by QUALIFIED leads (brief §7)"

assert len(kpi.assigned_leads(cv)) < len(cv), "fixture has no unassigned leads"
assert kpi.contact_rate(cv) > (cv.contacted_ts.notna().sum() / len(cv)), \
    "F1: contact rate must divide by ASSIGNED leads (brief §7)"
print(f"ok formulas approval {kpi.approval_rate(cv):.1%} (decided {kpi.approval_rate_decided(cv):.1%}) · "
      f"application {kpi.application_rate(cv):.1%} · contact {kpi.contact_rate(cv):.1%}")

# every registered KPI carries the metadata the brief §7 requires
for key, d in kpi.REGISTRY.items():
    assert d.name and d.num and d.source or not d.source, key
print(f"ok registry {len(kpi.REGISTRY)} KPIs defined")

# ---- deep links survive the login they trigger ----
d = common.destination_from_url(
    "http://localhost:8507/customers?stage=Booked&branch_name=%E0%B8%AA%E0%B8%B2%E0%B8%82%E0%B8%B2")
assert d["stem"] == "customers", d
assert d["params"]["stage"] == "Booked", d
assert d["params"]["branch_name"].startswith("สาขา"), "url-encoded Thai must decode"
assert common.destination_from_url("http://localhost:8507/") is None, \
    "a bare root URL is not a destination"
assert common.destination_from_url(None) is None

mod, path = common.resolve_page("customers")
assert (mod, path) == ("customers", "app_pages/customers.py"), (mod, path)
assert common.resolve_page("not_a_page") is None
# every registered page must exist on disk, or a link resolves to a 404
import os  # noqa: E402
for _g, items in common.PAGES:
    for _mod, stem, _t, _i in items:
        assert os.path.exists(f"app_pages/{stem}.py"), f"missing page file {stem}.py"
# and the nav registry must agree with the permission table
regs = {m for _g, items in common.PAGES for m, _s, _t, _i in items} - {"account"}
assert regs == set(auth.PERMISSIONS), (regs ^ set(auth.PERMISSIONS))
print(f"ok routing   {len(regs)} pages, registry and permissions agree")

# ---- the qualified-lead rule (C1, settled v1.2) ----
# The three buckets must be disjoint, or a status silently counts twice.
assert not (kpi.QUALIFIED_STATUSES & kpi.DISQUALIFIED_STATUSES)
assert not (kpi.QUALIFIED_STATUSES & kpi.UNSCREENED_STATUSES)
assert not (kpi.DISQUALIFIED_STATUSES & kpi.UNSCREENED_STATUSES)

# Every status GSB actually uses must be classified, or leads vanish from both
# the numerator and the denominator without anyone noticing.
import sys as _s, os as _o  # noqa: E402
_s.path.insert(0, _o.path.join(_o.path.dirname(_o.getcwd()), "dashboard-mockup"))
import gsb_vocab as _v  # noqa: E402
_all = kpi.QUALIFIED_STATUSES | kpi.DISQUALIFIED_STATUSES | kpi.UNSCREENED_STATUSES
_unclassified = set(_v.LEAD_STATUSES_TH) - _all
assert not _unclassified, f"GSB statuses with no bucket: {_unclassified}"

# And every status present in the data must be classified too.
_in_data = set(cv.lead_status.dropna().unique()) - {"Duplicate Lead"}
assert not (_in_data - _all), f"mock statuses with no bucket: {_in_data - _all}"

# Unreachable leads are NOT qualified. That conflation is the whole point of the
# rule: it made a follow-up backlog look like a targeting problem.
_cc = cv[cv.lead_status == "Cannot Contact"]
assert len(_cc) and not len(kpi.qualified_leads(_cc)), \
    "leads nobody reached must not count as qualified"
assert not len(kpi.screened_leads(_cc)), \
    "leads nobody reached must not sit in the denominator either"

assert kpi.screening_coverage(cv) < 1.0, "coverage of 100% means nothing is pending"
print(f"ok qualified {kpi.qualified_rate(cv):.1%} of screened, "
      f"coverage {kpi.screening_coverage(cv):.0%}, all {len(_v.LEAD_STATUSES_TH)} "
      f"GSB statuses classified")
