"""Shared data layer for the DCO campaign dashboard (mock-data v1).

Reads the user-level mock CSVs from dashboard-mockup/mock_data and derives
everything else in pandas. ponytail: swap load() internals for BigQuery/Cloud SQL
later; every page only sees the returned frames.
"""
from pathlib import Path
import hashlib

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parents[1] / "dashboard-mockup" / "mock_data"

# Two seats (seat-map v3). The brief section 12 lists eight roles, but that is the
# governance model of a finished CRM; we are at phase 1-2. A third seat, `branch`,
# arrives later as the write module scoped by branch_id.
ROLES = ["admin", "campaign_owner"]
WRITE_ROLES = {"admin"}                     # the only human write path
UNMASKED_ROLES = {"admin"}                  # who sees raw contact fields
ADMIN_ONLY_PAGES = {"worklist", "data_health", "campaign_setup"}

FIRST = ["Somchai", "Suda", "Anong", "Prasit", "Kanya", "Wichai", "Malee", "Thanawat",
         "Pornthip", "Krit", "Siriporn", "Chaiwat", "Nok", "Somsak", "Duangjai", "Arthit"]

# Brief §2 recommended flow. The build previously collapsed this and dropped the
# three statuses that carry the admin's day-to-day distinctions.
LEAD_STATUSES = ["New", "Assigned", "Contact Attempted", "Contacted", "Interested",
                 "Document Pending", "Application Submitted", "Approved", "Booked", "Disbursed",
                 "Cannot Contact", "Not Interested", "Not Qualified", "Duplicate Lead",
                 "Application Rejected", "Cancelled"]
TERMINAL_STATUSES = {"Cannot Contact", "Not Interested", "Not Qualified", "Duplicate Lead",
                     "Application Rejected", "Cancelled"}
REASON_CODES = ["cannot_contact", "not_interested", "not_qualified", "duplicate_lead",
                "cancelled", "keying_correction"]

STAGE_ORDER = ["Duplicate", "Not qualified", "Cannot contact", "New / assigned", "Contacted",
               "Docs submitted", "Application", "Rejected", "Approved", "Booked", "Disbursed"]
GOOD_STAGES = ["Contacted", "Docs submitted", "Application", "Approved", "Booked", "Disbursed"]


def _boolify(df, cols):
    for c in cols:
        df[c] = df[c].astype(str).eq("True")
    return df


def display_name(lead_id: str) -> str:
    h = int(hashlib.md5(lead_id.encode()).hexdigest(), 16)
    return f"{FIRST[h % len(FIRST)]} {chr(65 + (h // 7) % 26)}. (mock)"


@st.cache_data(ttl=600)
def load():
    media = pd.read_csv(DATA_DIR / "media_daily.csv", parse_dates=["date"])
    prospects = pd.read_csv(DATA_DIR / "prospects.csv")
    sessions = pd.read_csv(DATA_DIR / "web_sessions.csv", parse_dates=["ts"])
    _boolify(sessions, ["form_start", "form_complete"])
    leads = pd.read_csv(DATA_DIR / "leads.csv",
                        parse_dates=["submitted_ts", "assigned_ts", "contacted_ts", "docs_submitted_ts"])
    _boolify(leads, ["qualified_flag", "duplicate_flag"])
    apps = pd.read_csv(DATA_DIR / "applications.csv", parse_dates=["submitted_ts", "decision_ts"])
    loans = pd.read_csv(DATA_DIR / "loans.csv", parse_dates=["booked_ts", "disbursed_ts"])
    media["reach"] = media.get("reach", media.impressions)
    events = pd.read_csv(DATA_DIR / "lead_events.csv")
    # format="mixed": generator writes ns-precision strings, write_status writes seconds
    events["changed_at"] = pd.to_datetime(events["changed_at"], format="mixed")
    return media, prospects, sessions, leads, apps, loans, events


@st.cache_data(ttl=600)
def campaign():
    """The registry row. Every query filters on campaign_id so a second campaign
    costs a WHERE clause, not a refactor (seat map S9)."""
    return pd.read_csv(DATA_DIR / "campaign.csv").iloc[0]


@st.cache_data(ttl=600)
def crosssell():
    return pd.read_csv(DATA_DIR / "crosssell_monthly.csv", parse_dates=["month"])


@st.cache_data(ttl=600)
def control_group():
    return pd.read_csv(DATA_DIR / "control_group.csv")


@st.cache_data(ttl=600)
def as_of():
    _, _, _, _, _, _, events = load()
    return events["changed_at"].max().normalize()


@st.cache_data(ttl=600)
def customer_view() -> pd.DataFrame:
    """One row per lead with everything the list/detail screens need."""
    media, prospects, sessions, leads, apps, loans, events = load()
    now = as_of()

    a = apps.sort_values("submitted_ts").groupby("lead_id").last().reset_index()
    ln = loans.merge(a[["application_id", "lead_id"]], on="application_id", how="left")
    ln = ln.sort_values("booked_ts").groupby("lead_id").last().reset_index()

    cv = leads.merge(
        a[["lead_id", "application_id", "requested_amt_thb", "approved_amt_thb",
           "app_status", "decision_ts", "decline_reason", "submitted_ts"]]
        .rename(columns={"submitted_ts": "app_ts"}),
        on="lead_id", how="left",
    ).merge(
        ln[["lead_id", "loan_account_id", "booked_ts", "booked_amt_thb",
            "disbursed_ts", "disbursed_amt_thb", "interest_rate_pct"]],
        on="lead_id", how="left",
    ).merge(
        prospects[["prospect_id", "age", "occupation", "monthly_income_thb", "province",
                   "is_new_to_bank", "cif_linked_at"]],
        on="prospect_id", how="left",
    )

    def stage(r):
        if r.duplicate_flag: return "Duplicate"
        if not r.qualified_flag: return "Not qualified"
        if pd.notna(r.disbursed_ts): return "Disbursed"
        if pd.notna(r.booked_ts): return "Booked"
        if r.app_status == "Approved": return "Approved"
        if r.app_status == "Rejected": return "Rejected"
        if pd.notna(r.app_ts): return "Application"
        if pd.notna(r.docs_submitted_ts): return "Docs submitted"
        if pd.notna(r.contacted_ts): return "Contacted"
        if r.lead_status == "Cannot Contact": return "Cannot contact"
        return "New / assigned"

    cv["stage"] = cv.apply(stage, axis=1)
    since = cv[["disbursed_ts", "booked_ts", "decision_ts", "app_ts",
                "docs_submitted_ts", "contacted_ts", "assigned_ts", "submitted_ts"]].bfill(axis=1)
    cv["stage_since"] = since.iloc[:, 0]
    cv["days_in_stage"] = (now - cv["stage_since"]).dt.days.clip(lower=0)

    owner = (events[events.event_type == "assignment"]
             .sort_values("changed_at").groupby("lead_id")["new_value"].last())
    cv["owner"] = cv["lead_id"].map(owner).fillna("-")
    cv["is_new_to_bank"] = cv["is_new_to_bank"].astype(str).eq("True")
    unmatched = cv.prospect_id.isna() | (cv.prospect_id == "")
    cv["customer_type"] = pd.Series(
        pd.NA, index=cv.index, dtype="object").mask(~unmatched & cv.is_new_to_bank, "new_to_bank"
        ).mask(~unmatched & ~cv.is_new_to_bank, "existing").fillna("unknown")
    cv["name"] = cv["lead_id"].map(display_name)
    cv["lead_week"] = cv["submitted_ts"].dt.to_period("W-SUN").dt.start_time
    return cv


# ---------------- drill / filter model ----------------
# every clickable chart element is just a WHERE clause on customer_view
FILTERS = {
    "creative_id":  ("Creative",    lambda cv, v: cv.creative_id == v),
    "channel":      ("Channel",     lambda cv, v: cv.channel == v),
    "segment":      ("Segment",     lambda cv, v: cv.segment == v),
    "branch_name":  ("Branch",      lambda cv, v: cv.branch_name == v),
    "stage":        ("Stage",       lambda cv, v: cv.stage == v),
    "reached":      ("Reached",     lambda cv, v: cv.stage.isin(GOOD_STAGES[GOOD_STAGES.index(v):]) if v in GOOD_STAGES else cv.stage == v),
    "lost_reason":  ("Lost reason", lambda cv, v: cv.lost_reason == v),
    "decline_reason": ("Declined for", lambda cv, v: cv.decline_reason == v),
    "lead_week":    ("Lead week",   lambda cv, v: cv.lead_week == pd.Timestamp(v)),
    "aging":        ("Aging",       lambda cv, v: cv.days_in_stage.between(*v)),
    "unmatched":    ("Data issue",  lambda cv, v: cv.prospect_id.isna() | (cv.prospect_id == "")),
    "customer_type": ("Customer",   lambda cv, v: cv.customer_type == v),
    "product":      ("Product",     lambda cv, v: cv["product"] == v),
}


def drill(**kv):
    """Stack filters and jump to the customer list."""
    st.session_state.drill = {**st.session_state.get("drill", {}), **kv}
    st.switch_page("app_pages/customers.py")


def apply_drill(cv):
    for k, v in st.session_state.get("drill", {}).items():
        if k in FILTERS:
            cv = cv[FILTERS[k][1](cv, v)]
    return cv


def altair_click(event, param="sel", field=None):
    """Return the clicked value from an altair selection event, or None."""
    try:
        pts = event["selection"][param]
        if pts:
            return pts[0][field] if field else pts[0]
    except (KeyError, IndexError, TypeError):
        pass
    return None


def role():
    return st.session_state.get("role", "campaign_owner")


def can_write():
    return role() in WRITE_ROLES


def mask_phone(v):
    """Brief section 12: mask the sensitive attribute, do not block the page. The
    owner needs lead-level detail (use case O6); they do not need the number."""
    if role() in UNMASKED_ROLES:
        return v
    s = str(v or "")
    return f"XXX-XXX-{s[-4:]}" if len(s) >= 4 else "XXX-XXX-XXXX"


def guard_admin(page="This page"):
    if not can_write():
        st.error(f":material/lock: {page} is admin-only. "
                 "Your seat reads every KPI page, but does not write.")
        st.stop()


def drill_hint(txt="Click to open those customers"):
    st.caption(f":material/touch_app: {txt}")


def baht(x, m=False):
    if pd.isna(x) or x == 0: return "-"
    return f"฿{x/1e6:,.1f}M" if m else f"฿{x:,.0f}"


def log_attempt(lead_id, outcome, actor, actor_role, channel="phone"):
    """Two-click attempt logging for the coordinator keying in branch reports."""
    now = pd.Timestamp.now().floor("s")
    ev = pd.read_csv(DATA_DIR / "lead_events.csv")
    leads = pd.read_csv(DATA_DIR / "leads.csv")
    ev.loc[len(ev)] = [f"E{900000 + len(ev)}", lead_id, "contact_attempt", "", outcome,
                       "", actor, actor_role, str(now), channel, ""]
    m = leads.lead_id == lead_id
    leads.loc[m, "contact_attempts"] = leads.loc[m, "contact_attempts"].fillna(0) + 1
    ev.to_csv(DATA_DIR / "lead_events.csv", index=False)
    leads.to_csv(DATA_DIR / "leads.csv", index=False)
    st.cache_data.clear()


def write_status(lead_id, new_status, reason, note, actor, actor_role):
    """Append a lead_event and update the lead's current status. ponytail: CSV as the
    transactional store for the mock; Cloud SQL + validated transitions in production."""
    now = pd.Timestamp.now().floor("s")
    ev = pd.read_csv(DATA_DIR / "lead_events.csv")
    leads = pd.read_csv(DATA_DIR / "leads.csv")
    old = leads.loc[leads.lead_id == lead_id, "lead_status"]
    old = old.iloc[0] if len(old) else ""
    ev.loc[len(ev)] = [f"E{900000 + len(ev)}", lead_id, "status_change", old, new_status,
                       reason or "", actor, actor_role, str(now), "", note or ""]
    leads.loc[leads.lead_id == lead_id, "lead_status"] = new_status
    if reason:
        leads.loc[leads.lead_id == lead_id, "lost_reason"] = reason
    ev.to_csv(DATA_DIR / "lead_events.csv", index=False)
    leads.to_csv(DATA_DIR / "leads.csv", index=False)
    st.cache_data.clear()


def render_freshness():
    """Per-source as-of footer. ponytail: mock derives from data timestamps;
    production reads agg_data_quality."""
    media, _, sessions, leads, apps, loans, events = load()
    human = events[events.changed_by.ne("system")]
    rows = [("Media (IPG)", media.date.max()), ("GA / landing", sessions.ts.max()),
            ("Droplead", leads.submitted_ts.max()), ("LOS", apps.decision_ts.max()),
            ("Branch keying", human.changed_at.max() if len(human) else None)]
    parts = [f"{n} · {t:%d %b}" if pd.notna(t) else f"{n} · —" for n, t in rows]
    c = campaign()
    st.caption(":material/schedule: Data as of — " + "  |  ".join(parts))
    st.caption(f":material/function: KPI definitions `{c.kpi_def_version}` · "
               f"attribution `{c.attribution_rule}` / {c.attribution_window_days}d · "
               f"campaign `{c.campaign_id}`")
