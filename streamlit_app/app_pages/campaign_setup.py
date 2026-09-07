"""Campaign setup: create and edit (checklist T3, senior's task 1).

The registry everything else hangs off. Two fields here unblock things
elsewhere: the target is the denominator of the owner's pace bullet, and the
UTM tag is what every ad must stamp for attribution to survive a lost click id.

Laid out as the senior's six blocks plus the brief §4 measurement fields,
because those categories are what the workshop will argue about.
"""
import pandas as pd
import streamlit as st

import common

common.guard_admin(module="campaign_setup")

camps = common.campaigns()
st.title("Campaign setup")

# ---- pick, or start a new one ----------------------------------------------
ids = list(camps.campaign_id)
NEW = "+ New campaign"
top = st.container(horizontal=True)
choice = top.selectbox("Campaign", ids + [NEW],
                       index=ids.index(st.session_state.get("campaign_id", ids[0]))
                       if st.session_state.get("campaign_id", ids[0]) in ids else 0)
creating = choice == NEW
if not creating:
    st.session_state.campaign_id = choice
    row = camps[camps.campaign_id == choice].iloc[0].to_dict()
else:
    row = {"campaign_id": "", "name": "", "product": "housing", "objective": "",
           "status": "Draft", "start_date": str(pd.Timestamp.today().date()),
           "end_date": str((pd.Timestamp.today() + pd.Timedelta(days=90)).date()),
           "target_disbursed_ge3m_thb": 0, "target_leads": 0, "budget_thb": 0,
           "planned_cpl_thb": 0, "cost_owner": "", "utm_tag": "",
           "attribution_rule": "last_click", "attribution_window_days": 30,
           "control_group_pct": 8.0, "kpi_def_version": "v1.1", "owner_user_id": ""}

st.caption("Six blocks from the senior's task 1, plus the measurement fields the "
           "best-practice brief §4 requires. Saving records every changed field "
           "in the change log.")

LIFECYCLE = ["Draft", "Pending Approval", "Scheduled", "Running", "Paused",
             "Completed", "Archived"]

with st.form("campaign"):
    T = st.tabs(["1 Objective", "2 Product & target customer", "3 Campaign target",
                 "4 Period & finance", "5 Roles", "6 Measurement"])
    v = {}
    with T[0]:
        a = st.container(horizontal=True)
        v["campaign_id"] = a.text_input("Campaign id", row["campaign_id"],
                                        disabled=not creating,
                                        help="Immutable. Everything joins on it.")
        v["name"] = a.text_input("Campaign name", row["name"])
        v["objective"] = st.text_area("Objective", row["objective"], height=80)
        v["status"] = st.selectbox("Status", LIFECYCLE,
                                   index=LIFECYCLE.index(row["status"])
                                   if row["status"] in LIFECYCLE else 0)
    with T[1]:
        b = st.container(horizontal=True)
        v["product"] = b.text_input("Product", row["product"])
        v["utm_tag"] = b.text_input("Canonical UTM tag", row["utm_tag"],
                                    help="Every ad must stamp this. It is the fallback "
                                         "attribution join when the click id is lost.")
        st.caption("Target customer detail comes from the imported lead list. "
                   "Import it on the **Target leads** page; its age, income and "
                   "occupation shape is what the Overview grid compares against.")
    with T[2]:
        v["target_disbursed_ge3m_thb"] = st.number_input(
            "Target — disbursed ฿ from loans ≥ ฿3M",
            value=int(row["target_disbursed_ge3m_thb"]), step=10_000_000,
            help="The denominator of the pace bullet. Without it, 'are we on plan' "
                 "cannot be answered at all.")
        v["target_leads"] = st.number_input("Target leads", value=int(row["target_leads"]),
                                            step=100)
        st.caption("฿3M is a per-loan ticket threshold, not the campaign target. The "
                   "north-star is *incremental* disbursed value from loans that size.")
    with T[3]:
        c = st.container(horizontal=True)
        v["start_date"] = str(c.date_input("Start", pd.Timestamp(row["start_date"])))
        v["end_date"] = str(c.date_input("End", pd.Timestamp(row["end_date"])))
        d = st.container(horizontal=True)
        v["budget_thb"] = d.number_input("Budget ฿", value=int(row["budget_thb"]),
                                         step=100_000)
        v["planned_cpl_thb"] = d.number_input("Planned CPL ฿",
                                              value=int(row["planned_cpl_thb"]), step=50)
    with T[4]:
        e = st.container(horizontal=True)
        v["cost_owner"] = e.text_input("Cost owner", row["cost_owner"])
        v["owner_user_id"] = e.text_input("Campaign owner (username)", row["owner_user_id"],
                                          help="Scopes that user to this campaign. "
                                               "Create the user on the Account page.")
        st.warning("Brief §12 requires **maker-checker** on campaigns: one person acts, "
                   "a second approves. One Marketing seat cannot satisfy that. Either a "
                   "second seat arrives, or the waiver is written down.",
                   icon=":material/gpp_maybe:")
    with T[5]:
        f = st.container(horizontal=True)
        RULES = ["last_click", "first_click", "lead_source_campaign", "multi_touch"]
        v["attribution_rule"] = f.selectbox(
            "Attribution rule", RULES,
            index=RULES.index(row["attribution_rule"])
            if row["attribution_rule"] in RULES else 0,
            help="Brief §10: fix this before launch and keep the rule version. Every "
                 "attributed number already assumes an answer.")
        v["attribution_window_days"] = f.number_input(
            "Attribution window (days)", value=int(row["attribution_window_days"]), step=1)
        v["control_group_pct"] = st.slider(
            "Control group %", 0.0, 20.0, float(row["control_group_pct"]), 0.5,
            help="The holdout. Once the campaign runs at scale it cannot be carved "
                 "retroactively, so this decision has an expiry date.")
        v["kpi_def_version"] = row["kpi_def_version"]

    v["_reason"] = st.text_input("Reason for this change",
                                 placeholder="Budget raised after week-4 review")
    saved = st.form_submit_button("Create campaign" if creating else "Save changes",
                                  type="primary")

if saved:
    if not v["campaign_id"].strip():
        st.error("Campaign id is required.")
    elif creating and v["campaign_id"] in ids:
        st.error(f"Campaign {v['campaign_id']} already exists.")
    elif not v["_reason"].strip() and not creating:
        st.error("A reason is required. It is what makes the change log useful "
                 "later, when somebody asks why a number moved.")
    else:
        n = common.save_campaign(v, common.actor())
        st.session_state.campaign_id = v["campaign_id"]
        st.success(f"{'Created' if creating else 'Saved'} — {n} change(s) logged.")
        st.rerun()

# ---- change log -------------------------------------------------------------
with st.container(border=True):
    st.subheader("Change log")
    st.caption("Senior's task 10. Every material change is a structured event, not a "
               "comment, so it can be pinned to a chart at the right position.")
    log = common.change_log(None if creating else choice)
    if not len(log):
        st.info("No changes recorded yet.", icon=":material/history:")
    else:
        st.dataframe(log.sort_values("effective", ascending=False),
                     hide_index=True, width="stretch")
