"""Data health - admin only (use case A6).

The owner never opens this page; they see its verdict in the footer chip. The
admin is the only person who can act on a stale feed, which is why the page is
behind the write gate rather than merely being uninteresting to the owner.
"""
import pandas as pd
import streamlit as st

import common

common.guard_admin("Data health")

media, prospects, sessions, leads, apps, loans, events = common.load()
cv = common.customer_view()
now = common.as_of()

st.title("Data health")
st.caption("Freshness, match rates and duplicates — the numbers that defend the other numbers.")

# ---- freshness per source ----------------------------------------------------
human = events[events.changed_by.ne("system")]
sources = [
    ("media_platform", "Media platform (IPG)", media.date.max(), 1),
    ("ga_landing", "GA / landing page", sessions.ts.max(), 1),
    ("droplead", "Droplead form", leads.submitted_ts.max(), 1),
    ("los", "LOS extract", apps.decision_ts.max(), 1),
    ("branch_tracking", "Branch keying (manual)", human.changed_at.max() if len(human) else pd.NaT, 1),
]
rows = []
for key, label, ts, cadence_days in sources:
    age = (now - ts).days if pd.notna(ts) else None
    rows.append({"source": label, "last_load": ts, "age_days": age,
                 "ok": age is not None and age <= cadence_days + 1})
fresh = pd.DataFrame(rows)

stale = fresh[~fresh.ok]
if len(stale):
    st.error(f"{len(stale)} source(s) stale: {', '.join(stale.source)}. "
             "Branch keying goes stale exactly when the worklist has not been worked.",
             icon=":material/warning:")
else:
    st.success("All five sources fresh.", icon=":material/check_circle:")

c = st.container(horizontal=True)
for _, r in fresh.iterrows():
    c.metric(r.source, f"{r.age_days}d ago" if r.age_days is not None else "—",
             delta="fresh" if r.ok else "STALE",
             delta_color="normal" if r.ok else "inverse")

col1, col2 = st.columns(2)

# ---- match rates -------------------------------------------------------------
with col1, st.container(border=True):
    st.subheader("Identity match rates")
    st.caption("Unmatched leads are counted and shown, never dropped. A rising "
               "unmatched count means the funnel is understated.")
    unmatched = int((cv.prospect_id.isna() | (cv.prospect_id == "")).sum())
    app_matched = int(apps.lead_id.isin(leads.lead_id).sum())
    m = st.container(horizontal=True)
    m.metric("Lead → CIF / prospect", f"{1 - unmatched/max(len(cv),1):.1%}")
    m.metric("Application → lead", f"{app_matched/max(len(apps),1):.1%}")
    m.metric("Duplicate rate", f"{cv.duplicate_flag.mean():.1%}")
    no_utm = int((sessions.utm_campaign.isna() | (sessions.utm_campaign == "")).sum())
    m.metric("Missing UTM", f"{no_utm/max(len(sessions),1):.1%}",
             help="Fallback attribution join when the click id is lost.")
    if unmatched:
        if st.button(f"Open the {unmatched} unmatched leads", icon=":material/link_off:"):
            common.drill(unmatched=True)

# ---- load counts -------------------------------------------------------------
with col2, st.container(border=True):
    st.subheader("Load volumes")
    vols = pd.DataFrame({
        "table": ["media_daily", "web_session", "lead", "lead_event", "application", "loan_account"],
        "rows": [len(media), len(sessions), len(leads), len(events), len(apps), len(loans)],
    })
    st.dataframe(vols, hide_index=True, column_config={
        "table": "Table", "rows": st.column_config.NumberColumn("Rows", format="localized")})
    st.caption("Mock reads CSVs. Production reads `agg_data_quality`, which records "
               "rows_loaded and rows_failed per run.")

# ---- what the owner sees -----------------------------------------------------
with st.container(border=True):
    st.subheader("What the campaign owner sees")
    st.caption("Acknowledging a known issue downgrades their chip from red to amber, "
               "so they know it is seen rather than missed.")
    st.text_input("Known-issue note (shown on the owner's freshness footer)",
                  placeholder="LOS extract delayed by month-end batch, ETA 18:00",
                  key="dq_note")
    st.button("Acknowledge", icon=":material/visibility:",
              help="Mock: writes nothing. Production writes to agg_data_quality.")
