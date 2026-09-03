# ponytail: one smoke test — every page renders for both seats, the gate holds,
# and the three corrected denominators stay corrected.
from streamlit.testing.v1 import AppTest

READ_PAGES = ["app_pages/exec.py", "app_pages/engagement.py", "app_pages/lead_quality.py",
              "app_pages/loan_funnel.py", "app_pages/business.py", "app_pages/customers.py",
              "app_pages/customer_detail.py", "app_pages/dictionary.py"]
ADMIN_PAGES = ["app_pages/worklist.py", "app_pages/data_health.py", "app_pages/campaign_setup.py"]


def run(page, role, extra=None):
    at = AppTest.from_file(page, default_timeout=90)
    at.session_state["role"] = role
    at.session_state["drill"] = {}
    at.session_state["maturity_gate"] = True
    for k, v in (extra or {}).items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, f"{page} [{role}]: {at.exception[0].value if at.exception else ''}"
    return at


LEAD = {"selected_lead": "L200041", "list_order": ["L200041"]}

for p in READ_PAGES + ADMIN_PAGES:
    run(p, "admin", LEAD)
    print("ok admin  ", p)

for p in READ_PAGES:
    run(p, "campaign_owner", LEAD)
    print("ok owner  ", p)

# the gate: admin-only pages must stop the owner
for p in ADMIN_PAGES:
    at = run(p, "campaign_owner")
    assert at.error, f"{p} should be admin-only"
print("ok gate    owner blocked from", ADMIN_PAGES)

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
