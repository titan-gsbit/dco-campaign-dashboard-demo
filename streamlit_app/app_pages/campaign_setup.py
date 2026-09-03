"""Campaign setup - admin only (use cases A4, A5, A7).

The registry everything else hangs off. Two fields here unblock things
elsewhere: the target is the denominator of the owner's pace bullet, and the
UTM tag is what every ad must stamp for attribution to survive a lost click id.

Laid out as the brief's section 4 categories rather than a flat form, because
the categories are what the workshop will argue about.
"""
import pandas as pd
import streamlit as st

import common

common.guard_admin("Campaign setup")

camp = common.campaign()
cv = common.customer_view()

st.title("Campaign setup")
st.caption("The registry the best-practice brief §4 requires. Mock: reads `campaign.csv`, "
           "saves nothing. Production writes the registry and versions every change.")

st.markdown(f"### {camp['name']}  ·  :violet-badge[{camp.status}]")

TABS = st.tabs(["Business", "Schedule & finance", "Audience", "Measurement", "Change log", "Access"])

with TABS[0]:
    st.text_input("Objective", camp.objective)
    c = st.container(horizontal=True)
    c.text_input("Campaign id", camp.campaign_id, disabled=True)
    c.text_input("Product", camp["product"])
    st.number_input("KPI target — disbursed ฿ from loans ≥ ฿3M", value=int(camp.target_disbursed_ge3m_thb),
                    step=10_000_000,
                    help="This is the denominator of the owner's pace bullet. Without it, "
                         "use case O1 cannot be answered at all.")
    st.number_input("Target leads", value=int(camp.target_leads), step=100)
    st.caption("The north-star is *incremental* disbursed value from loans of ฿3M or more. "
               "฿3M is a per-loan ticket threshold, not the campaign target.")

with TABS[1]:
    c = st.container(horizontal=True)
    c.date_input("Start", pd.Timestamp(camp.start_date))
    c.date_input("End", pd.Timestamp(camp.end_date))
    c.selectbox("Status", ["Draft", "Pending Approval", "Scheduled", "Running",
                           "Paused", "Completed", "Archived"],
                index=3, help="Brief §4 campaign lifecycle.")
    c2 = st.container(horizontal=True)
    c2.number_input("Budget ฿", value=int(camp.budget_thb), step=100_000)
    c2.number_input("Planned CPL ฿", value=int(camp.planned_cpl_thb), step=50)
    c2.text_input("Cost owner", camp.cost_owner)

with TABS[2]:
    st.text_input("Canonical UTM tag", camp.utm_tag,
                  help="Every ad must stamp this. It is the fallback attribution join "
                       "when the click id is lost, and it drives the missing-UTM trust KPI.")
    st.multiselect("Target segments", sorted(cv.segment.unique()),
                   default=sorted(cv.segment.unique()))
    st.slider("Control group %", 0.0, 20.0, float(camp.control_group_pct), 0.5,
              help="The holdout. Carving one retroactively is not possible once the "
                   "campaign is live at scale — this decision has an expiry date.")

with TABS[3]:
    c = st.container(horizontal=True)
    c.selectbox("Attribution rule", ["last_click", "first_click", "lead_source_campaign", "multi_touch"],
                index=0, help="Brief §10: fix this before launch and retain the rule version. "
                              "Every attributed number already assumes an answer.")
    c.number_input("Attribution window (days)", value=int(camp.attribution_window_days), step=1)
    c.text_input("KPI definition version", camp.kpi_def_version, disabled=True,
                 help="Bumped in kpi.py. v1.1 corrected three denominators against brief §7.")
    st.info("Numbers produced under an earlier definition version are not comparable to "
            "these. That is why the version travels with every export.", icon=":material/info:")

with TABS[4]:
    st.caption("Every material change is a structured event, not a comment — so it can be "
               "pinned to a chart at the right x position (brief §5).")
    st.dataframe(pd.DataFrame([
        {"effective": "2026-10-14 10:00", "user": "admin.gsbit", "change": "creative",
         "from": "CR-A-ratecut", "to": "CR-B-calculator",
         "reason": "CTR 30% below target for Bangkok Income 100K+"},
        {"effective": "2026-10-28 09:30", "user": "admin.gsbit", "change": "budget",
         "from": "฿180k/wk", "to": "฿240k/wk", "reason": "OPT segment CPL best in class"},
        {"effective": "2026-11-04 14:00", "user": "admin.gsbit", "change": "kpi_definition",
         "from": "v1.0", "to": "v1.1", "reason": "approval/application/contact denominators per brief §7"},
    ]), hide_index=True, width="stretch")
    with st.form("changelog"):
        c = st.container(horizontal=True)
        c.selectbox("Change type", ["budget", "creative", "audience", "landing_page",
                                    "targeting", "kpi_definition", "status"])
        c.text_input("From")
        c.text_input("To")
        st.text_input("Reason and expected impact",
                      placeholder="CTR 30% below target for the Bangkok Income 100K+ audience")
        if st.form_submit_button("Record change", type="primary"):
            st.toast("Mock: recorded. Production appends an event and annotates every chart.")

with TABS[5]:
    st.caption("Assigning an owner to a campaign is what makes future scoping a WHERE clause "
               "rather than a refactor.")
    st.dataframe(pd.DataFrame([
        {"user": "admin.gsbit", "seat": "admin", "scope": "all campaigns", "writes": "yes"},
        {"user": camp.owner_user_id, "seat": "campaign_owner", "scope": camp.campaign_id, "writes": "no"},
    ]), hide_index=True, width="stretch")
    st.warning("The brief §12 requires **maker-checker** on campaigns and audience exports — "
               "one person acts, a second approves. A single admin seat cannot satisfy that. "
               "Either the second seat arrives early, or the waiver is written down.",
               icon=":material/gpp_maybe:")
