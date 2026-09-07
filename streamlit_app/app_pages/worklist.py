import pandas as pd
import streamlit as st

import common
import kpi
from common import baht

common.guard_admin(module="worklist")
cv = common.customer_view()
now = common.as_of()

st.title("Worklist")
st.caption("Keying screen: work the queue top-down, log outcomes as branch reports come in.")

hours_open = (now - cv.submitted_ts).dt.total_seconds() / 3600
open_new = cv[cv.stage == "New / assigned"]
overdue = open_new[hours_open.reindex(open_new.index) > 24]
await_docs = cv[(cv.stage == "Contacted") & (cv.days_in_stage > 3)]
pipe_stuck = cv[cv.stage.isin(["Docs submitted", "Application"]) & (cv.days_in_stage > 7)]

# Queue size and queue health are different questions. Showing six numbers at the
# same weight let a 21% SLA sit as quietly as a row count, so they are split and
# the health figures are scored against their targets.
m = st.container(horizontal=True)
m.metric("Overdue first contact", len(overdue),
         help="Past the 24-hour SLA. Work these first.")
m.metric("New, no contact yet", len(open_new))
m.metric("Contacted, no docs > 3d", len(await_docs))
m.metric("In process > 7d", len(pipe_stuck))
m.metric("Open total", int((~cv.stage.isin(["Disbursed", "Rejected", "Duplicate",
                                            "Not qualified", "Cannot contact"])).sum()))

sla, hrs = kpi.sla_compliance(cv), kpi.lead_to_contact_hrs(cv)
h = st.container(horizontal=True)
h.metric("SLA compliance", f"{sla:.0%}", delta=f"{sla - 0.8:+.0%} vs 80% target",
         delta_color="normal",          # higher is better

         help=kpi.sla_compliance.definition.exclusions)
h.metric("Median hrs to first contact", f"{hrs:.0f}h",
         delta=f"{hrs - 24:+.0f}h vs 24h SLA",
         delta_color="inverse",         # more hours is worse

         help="Brief §3: first attempt within 24 hours.")
h.metric("Screening coverage", f"{kpi.screening_coverage(cv):.0%}",
         help="Share of the lead book anyone has actually assessed. A high "
              "qualified rate on low coverage is not good news.")
if sla < 0.8 or hrs > 24:
    st.warning(f"Follow-up is behind: {sla:.0%} of assigned leads met the 24-hour "
               f"SLA, median {hrs:.0f}h. Every level-3 KPI downstream is produced "
               f"by working this queue.", icon=":material/schedule:")

# ---- S6: key an outcome without touching the mouse --------------------------
# The load-bearing interaction. If this is slower than whatever branches use
# today, the data supply stops and eight KPIs downstream go stale. How outcomes
# actually arrive is still an open question for the GSB workshop.
with st.container(border=True):
    st.subheader("Key an outcome")
    st.caption("Paste a lead id or phone from the branch report, then Tab → status → "
               "Tab → reason → Enter. Twenty-two records should take under ten minutes.")
    jump = st.text_input("Lead id or phone", key="wl_jump", placeholder="L200041  or  0812345678",
                         label_visibility="collapsed")
    if jump:
        j = jump.strip().lower()
        hit = cv[cv.lead_id.str.lower().eq(j)
                 | cv.get("phone_number", pd.Series("", index=cv.index)).astype(str).str.endswith(j)]
        if not len(hit):
            st.warning(f"No open lead matches `{jump}`. Check the id, or search the customer list.",
                       icon=":material/search_off:")
        else:
            r = hit.iloc[0]
            st.markdown(f"**{r['name']}** · `{r.lead_id}` · {r.branch_name} · "
                        f":violet-badge[{r.stage}] · {int(r.days_in_stage)}d waiting")
            with st.form("quickkey", clear_on_submit=True):
                f = st.container(horizontal=True)
                new_status = f.selectbox("Status", common.LEAD_STATUSES,
                                         index=common.LEAD_STATUSES.index("Contacted"))
                reason = f.selectbox("Reason (required if terminal)", [""] + common.REASON_CODES)
                note = f.text_input("Note (never a KPI)")
                if st.form_submit_button("Save and next", type="primary"):
                    if new_status in common.TERMINAL_STATUSES and not reason:
                        st.error("A reason code is required on a terminal status.")
                    else:
                        common.write_status(r.lead_id, new_status, reason, note,
                                            actor=common.actor(), actor_role=common.role())
                        st.session_state.wl_jump = ""
                        st.toast(f"{r.lead_id} → {new_status}. Event appended, nothing overwritten.")
                        st.rerun()

bucket = st.segmented_control(
    "Queue", ["Overdue first contact", "New / assigned", "Contacted, no docs", "Stuck in process"],
    default="Overdue first contact", label_visibility="collapsed")
branch = st.selectbox("Branch", ["All branches"] + sorted(cv.branch_name.unique()))

q = {"Overdue first contact": overdue, "New / assigned": open_new,
     "Contacted, no docs": await_docs, "Stuck in process": pipe_stuck}[bucket].copy()
if branch != "All branches":
    q = q[q.branch_name == branch]
q = q.sort_values("days_in_stage", ascending=False)

if len(q) == 0:
    st.success(f"**{bucket}** is clear — nothing waiting in this bucket."
               + (f" Try another bucket, or widen the branch filter."
                  if branch != "All branches" else ""),
               icon=":material/task_alt:")
    st.stop()

show = q[["lead_id", "name", "branch_name", "stage", "days_in_stage",
          "contact_attempts", "requested_amt_thb", "owner"]].head(200).reset_index(drop=True)
# a lead with no application has no requested amount; NaN renders blank, the
# string "None" renders as the word None.
show["requested_amt_thb"] = pd.to_numeric(show.requested_amt_thb, errors="coerce")
show["attempt"] = ":material/phone_missed: no answer"
show["open"] = ":material/person: open"

def _log():
    lead = show.iloc[st.session_state.wl_att.row]["lead_id"]
    common.log_attempt(lead, "no_answer", common.actor(), common.role())
    st.toast(f"Attempt logged on {lead}")

def _open():
    st.session_state.selected_lead = show.iloc[st.session_state.wl_open.row]["lead_id"]
    st.session_state.list_order = show.lead_id.tolist()
    st.switch_page("app_pages/customer_detail.py")

can_write = common.can_write("worklist")
col_cfg = {
    "lead_id": "Lead", "name": "Name", "branch_name": "Branch", "stage": "Stage",
    "days_in_stage": "Days waiting", "contact_attempts": "Attempts",
    "requested_amt_thb": st.column_config.NumberColumn("Requested ฿", format="localized"),
    "days_in_stage": st.column_config.NumberColumn("Days waiting", format="%d d"),
    "owner": "Owner",
    "open": st.column_config.ButtonColumn("", type="tertiary", on_click=_open, key="wl_open"),
}
if can_write:
    col_cfg["attempt"] = st.column_config.ButtonColumn(
        "Quick log", type="tertiary", on_click=_log, key="wl_att",
        help="Logs one unanswered phone attempt. Reached someone? Open the lead and set the status.")
else:
    show = show.drop(columns=["attempt"])
# height follows the rows: a fixed height padded short buckets with blank
# rows, which reads as broken data rather than an empty queue.
st.dataframe(show, hide_index=True, width="stretch",
             height=min(480, 44 + 35 * len(show)), column_config=col_cfg)
st.caption("Sorted by longest waiting first. 'Quick log' = one keystroke per unanswered call; "
           "anything more than that goes through the lead's detail page.")
