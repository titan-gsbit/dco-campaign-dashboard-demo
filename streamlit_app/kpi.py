"""The KPI dictionary, executable.

The best-practice brief section 7 asks that every KPI carry a definition,
numerator, denominator, exclusions, source, refresh, owner and version. Keeping
that in a document guarantees drift: the seat-map review found three KPIs whose
code silently disagreed with the written formula. So the dictionary lives here,
in the only place that can be wrong in exactly one way.

Every KPI is a function with metadata attached. Pages call the function; nothing
computes a rate inline. REGISTRY renders the dictionary page from the same
source, so the documentation cannot drift from the arithmetic.

Fixed against the brief in v1.1 (seat map F1-F3):
  approval rate     / submitted applications, not / decided
  application rate  / qualified leads,        not / all leads
  contact rate      / assigned leads,         not / all leads
"""
from dataclasses import dataclass, field

import pandas as pd

VERSION = "v1.1"

# denominators that changed in v1.1 - any number quoted before this needs the caveat
CHANGED_IN_V11 = {"approval_rate", "application_rate", "contact_rate"}


@dataclass
class Def:
    name: str
    num: str
    den: str = ""
    source: str = ""
    gated: bool = False          # only meaningful on matured cohorts
    exclusions: str = ""
    brief: str = ""              # section of the best-practice brief that specifies it
    fn: object = field(default=None, repr=False)

    @property
    def formula(self):
        return f"{self.num} / {self.den}" if self.den else self.num


REGISTRY: dict[str, Def] = {}


def kpi(name, num, den="", source="", gated=False, exclusions="", brief=""):
    def wrap(fn):
        REGISTRY[fn.__name__] = Def(name, num, den, source, gated, exclusions, brief, fn)
        fn.definition = REGISTRY[fn.__name__]
        return fn
    return wrap


def _rate(n, d):
    """Rates are derived, never stored, so any filtered view re-aggregates."""
    return float(n) / float(d) if d else 0.0


# ---------- population helpers: the denominators that caused the faults ----------
def completed_leads(cv):
    """Every submitted droplead form. Duplicates stay in - removing them
    silently collapses funnel counts (brief section 2)."""
    return cv


def assigned_leads(cv):
    return cv[cv.assigned_ts.notna()]


def qualified_leads(cv):
    return cv[cv.qualified_flag & ~cv.duplicate_flag]


def submitted_applications(cv):
    """All applications that reached LOS, pending decisions included."""
    return cv[cv.app_ts.notna()]


def decided_applications(cv):
    return cv[cv.app_status.isin(["Approved", "Rejected"])]


# ---------------- level 1 - media ----------------
@kpi("Impressions", "SUM(impressions)", source="media_daily", brief="deck L1")
def impressions(media): return int(media.impressions.sum())


@kpi("Reach", "SUM(reach)", source="media_daily", brief="deck L1")
def reach(media): return int(media.reach.sum()) if "reach" in media else 0


@kpi("Frequency", "impressions", "reach", source="media_daily", brief="deck L1")
def frequency(media): return _rate(media.impressions.sum(), reach(media))


@kpi("CTR", "clicks", "impressions", source="media_daily", brief="brief 7")
def ctr(media): return _rate(media.clicks.sum(), media.impressions.sum())


@kpi("CPC", "spend_thb", "clicks", source="media_daily", brief="deck L1")
def cpc(media): return _rate(media.spend_thb.sum(), media.clicks.sum())


@kpi("CPM", "spend_thb x 1000", "impressions", source="media_daily", brief="deck L1")
def cpm(media): return _rate(media.spend_thb.sum() * 1000, media.impressions.sum())


# ---------------- level 2 - engagement ----------------
@kpi("Landing page rate", "landing page views", "clicks", source="web_session + media", brief="brief 7")
def landing_page_rate(sessions, media): return _rate(len(sessions), media.clicks.sum())


@kpi("Form start rate", "form starts", "landing page views", source="web_session", brief="brief 7")
def form_start_rate(sessions): return _rate(sessions.form_start.sum(), len(sessions))


@kpi("Form completion rate", "completed leads", "form starts", source="web_session", brief="brief 7")
def form_completion_rate(sessions): return _rate(sessions.form_complete.sum(), sessions.form_start.sum())


# ---------------- level 3 - lead quality ----------------
@kpi("Leads", "COUNT(completed droplead forms)", source="lead", brief="deck L3")
def leads(cv): return len(cv)


@kpi("Cost per lead", "spend_thb", "completed leads", source="media + lead", brief="deck L3")
def cost_per_lead(cv, media): return _rate(media.spend_thb.sum(), len(cv))


@kpi("Qualified lead rate", "qualified leads", "completed leads",
     source="lead", exclusions="duplicates excluded from the numerator",
     brief="brief 7 - ratio settled, screening rule still open (U1)")
def qualified_rate(cv): return _rate(len(qualified_leads(cv)), len(cv))


@kpi("Contact rate", "contacted leads", "assigned leads",
     source="lead_event", exclusions="unassigned leads are not follow-up failures",
     brief="brief 7 - was / all leads before v1.1 (F1)")
def contact_rate(cv):
    a = assigned_leads(cv)
    return _rate(a.contacted_ts.notna().sum(), len(a))


@kpi("Document submission rate", "docs submitted", "completed leads", source="lead", brief="deck L3")
def doc_submission_rate(cv): return _rate(cv.docs_submitted_ts.notna().sum(), len(cv))


# ---------------- level 4 - loan funnel (maturity-gated) ----------------
@kpi("Application rate", "applications", "qualified leads", source="application", gated=True,
     brief="brief 7 - was / all leads before v1.1 (F2)")
def application_rate(cv):
    q = qualified_leads(cv)
    return _rate(q.app_ts.notna().sum(), len(q))


@kpi("Approval rate", "approved applications", "submitted applications", source="application", gated=True,
     exclusions="pending decisions stay in the denominator",
     brief="brief 7 - was / decided applications before v1.1 (F3)")
def approval_rate(cv):
    s = submitted_applications(cv)
    return _rate((s.app_status == "Approved").sum(), len(s))


@kpi("Approval rate (decided only)", "approved", "approved + rejected", source="application", gated=True,
     exclusions="excludes pending - shown alongside approval_rate to make the pending drag visible")
def approval_rate_decided(cv):
    d = decided_applications(cv)
    return _rate((d.app_status == "Approved").sum(), len(d))


@kpi("Booking rate", "booked loans", "approved applications", source="loan_account", gated=True, brief="brief 7")
def booking_rate(cv):
    ap = cv[cv.app_status == "Approved"]
    return _rate(ap.booked_ts.notna().sum(), len(ap))


@kpi("Disbursement rate", "disbursed loans", "booked loans", source="loan_account", gated=True, brief="brief 7")
def disbursement_rate(cv):
    b = cv[cv.booked_ts.notna()]
    return _rate(b.disbursed_ts.notna().sum(), len(b))


@kpi("Approval amount", "SUM(approved_amt_thb)", source="application", gated=True, brief="deck L4")
def approval_amount(cv): return float(cv.approved_amt_thb.sum())


@kpi("Average ticket size", "SUM(disbursed_amt_thb)", "disbursed loans", source="loan_account", gated=True,
     exclusions="disbursed base, not approved - the base the brief leaves open (U2)", brief="brief 7 strategic")
def avg_ticket(cv):
    d = cv[cv.disbursed_ts.notna()]
    return _rate(d.disbursed_amt_thb.sum(), len(d))


@kpi("Approved to requested", "SUM(approved_amt_thb)", "SUM(requested_amt_thb)", source="application",
     gated=True, brief="brief 7 quality")
def approved_to_requested(cv):
    ap = cv[cv.app_status == "Approved"]
    return _rate(ap.approved_amt_thb.sum(), ap.requested_amt_thb.sum())


# ---------------- level 5 - business ----------------
@kpi("Total disbursed", "SUM(disbursed_amt_thb)", source="loan_account", gated=True, brief="deck L5")
def total_disbursed(cv): return float(cv.disbursed_amt_thb.sum())


@kpi("Disbursed from loans >= THB 3M", "SUM(disbursed_amt_thb) WHERE loan >= 3M",
     source="loan_account", gated=True,
     exclusions="3M is a per-loan ticket threshold, not a campaign target",
     brief="brief 7 north star")
def disbursed_ge3m(cv):
    return float(cv.loc[cv.disbursed_amt_thb >= 3e6, "disbursed_amt_thb"].sum())


@kpi("Interest income", "SUM(disbursed x rate x elapsed years)", source="loan_account", gated=True,
     exclusions="realised to date; projection uses versioned assumptions", brief="deck L5")
def interest_income(cv):
    d = cv[cv.disbursed_ts.notna()]
    if not len(d):
        return 0.0
    yrs = (cv.disbursed_ts.max() - d.disbursed_ts).dt.days.clip(lower=0) / 365.0
    return float((d.disbursed_amt_thb * d.interest_rate_pct / 100 * yrs).sum())


@kpi("Cross-sell revenue", "SUM(crosssell_revenue_thb)", source="crosssell_monthly", gated=True,
     brief="deck L5 - mocked feed, production needs product holdings")
def crosssell_revenue(crosssell): return float(crosssell.crosssell_revenue_thb.sum())


@kpi("Revenue", "interest income + cross-sell revenue", source="loan_account + crosssell", gated=True,
     brief="deck L5")
def revenue(cv, crosssell): return interest_income(cv) + crosssell_revenue(crosssell)


@kpi("ROAS", "interest income + cross-sell", "ad spend", source="all", gated=True,
     exclusions="gross, not incremental, until a holdout exists (M5)", brief="deck L5")
def roas(cv, crosssell, media): return _rate(revenue(cv, crosssell), media.spend_thb.sum())


@kpi("New-to-bank customers", "DISTINCT prospects booked WHERE is_new_to_bank", source="prospect",
     gated=True, exclusions="restates as CIFs bind late (U4)", brief="strategic")
def new_to_bank(cv):
    b = cv[cv.booked_ts.notna() & cv.is_new_to_bank]
    return int(b.prospect_id.nunique())


# ---------------- economics (brief 7, absent from the deck) ----------------
def _cost_per(cv, media, mask):
    return _rate(media.spend_thb.sum(), mask.sum())


@kpi("Cost per application", "spend_thb", "applications", source="media + application", gated=True, brief="brief 7")
def cost_per_application(cv, media): return _cost_per(cv, media, cv.app_ts.notna())


@kpi("Cost per approval", "spend_thb", "approved applications", source="media + application", gated=True, brief="brief 7")
def cost_per_approval(cv, media): return _cost_per(cv, media, cv.app_status == "Approved")


@kpi("Cost per booking", "spend_thb", "booked loans", source="media + loan_account", gated=True, brief="brief 7")
def cost_per_booking(cv, media): return _cost_per(cv, media, cv.booked_ts.notna())


@kpi("Cost per disbursement", "spend_thb", "disbursed loans", source="media + loan_account", gated=True, brief="brief 7")
def cost_per_disbursement(cv, media): return _cost_per(cv, media, cv.disbursed_ts.notna())


@kpi("Cost per disbursed baht", "spend_thb", "SUM(disbursed_amt_thb)", source="media + loan_account",
     gated=True, brief="economics")
def cost_per_disbursed_baht(cv, media): return _rate(media.spend_thb.sum(), cv.disbursed_amt_thb.sum())


# ---------------- speed (brief 7) ----------------
def _median_days(a, b):
    d = (a - b).dt.total_seconds() / 86400
    d = d[d.notna() & (d >= 0)]
    return float(d.median()) if len(d) else 0.0


@kpi("Lead to contact (hours)", "median(contacted_ts - submitted_ts)", source="lead_event",
     exclusions="24h SLA", brief="brief 3")
def lead_to_contact_hrs(cv): return _median_days(cv.contacted_ts, cv.submitted_ts) * 24


@kpi("Lead to application (days)", "median(app_ts - submitted_ts)", source="lead + application",
     gated=True, brief="brief 7 speed")
def lead_to_application_days(cv): return _median_days(cv.app_ts, cv.submitted_ts)


@kpi("Application to approval (days)", "median(decision_ts - app_ts)", source="application",
     gated=True, brief="brief 7 speed")
def application_to_approval_days(cv):
    d = decided_applications(cv)
    return _median_days(d.decision_ts, d.app_ts)


# ---------------- SLA (brief 3) ----------------
@kpi("SLA compliance rate", "leads meeting first-contact SLA", "assigned leads", source="lead_event",
     exclusions="first contact within 24h of submission", brief="brief 3")
def sla_compliance(cv, hours=24):
    a = assigned_leads(cv)
    if not len(a):
        return 0.0
    hrs = (a.contacted_ts - a.submitted_ts).dt.total_seconds() / 3600
    return _rate((hrs <= hours).sum(), len(a))


# ---------------- north star vs plan + incrementality ----------------
@kpi("Pace against plan", "disbursed >= 3M to date", "campaign target", source="campaign registry",
     gated=True, exclusions="straight-line expectation over the campaign window", brief="brief 4 business")
def pace(cv, campaign, as_of_ts):
    """Returns (actual, target, expected_by_now, pct_of_target)."""
    target = float(campaign.target_disbursed_ge3m_thb)
    start = pd.Timestamp(campaign.start_date)
    end = pd.Timestamp(campaign.end_date)
    span = max((end - start).days, 1)
    elapsed = min(max((pd.Timestamp(as_of_ts) - start).days, 0), span)
    actual = disbursed_ge3m(cv)
    return actual, target, target * elapsed / span, _rate(actual, target)


@kpi("Incremental disbursed >= THB 3M", "campaign disbursed >= 3M", "minus scaled control baseline",
     source="loan_account + control_group", gated=True,
     exclusions="control scaled to the campaign lead population", brief="brief 7 north star, brief 10")
def incremental_disbursed_ge3m(cv, control):
    """The brief is blunt: without this, ROAS credits customers who would have
    applied anyway. Control is scaled up from the holdout to campaign size."""
    if not len(control) or not len(cv):
        return disbursed_ge3m(cv), 0.0
    ctrl_ge3 = control.loc[control.disbursed_amt_thb >= 3e6, "disbursed_amt_thb"].sum()
    baseline = ctrl_ge3 * (len(cv) / len(control))
    return disbursed_ge3m(cv) - baseline, baseline
