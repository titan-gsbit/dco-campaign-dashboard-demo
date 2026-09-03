import pandas as pd
import streamlit as st

import common
from common import baht

cv = common.customer_view()
_, prospects, _, _, _, _, events = common.load()

lead_id = st.session_state.get("selected_lead")
if not lead_id:
    st.info("Pick a customer from the list first.")
    if st.button(":material/arrow_back: Customer list"):
        st.switch_page("app_pages/customers.py")
    st.stop()
r = cv[cv.lead_id == lead_id].iloc[0]

# ---- nav row
order = st.session_state.get("list_order", [lead_id])
i = order.index(lead_id) if lead_id in order else 0
nav = st.container(horizontal=True)
if nav.button(":material/arrow_back: back to list"):
    st.switch_page("app_pages/customers.py")
if nav.button(":material/chevron_left: prev", disabled=i == 0):
    st.session_state.selected_lead = order[i - 1]; st.rerun()
if nav.button("next :material/chevron_right:", disabled=i >= len(order) - 1):
    st.session_state.selected_lead = order[i + 1]; st.rerun()
nav.caption(f"{i+1} of {len(order)} in current list")

st.title(r["name"])

h = st.container(horizontal=True)
h.metric("Lead", r.lead_id)
h.metric("Segment", r.segment_code, help=r.segment)
h.metric("Product", r["product"])
h.metric("Phone", common.mask_phone(getattr(r, "phone_number", "")),
         help="Masked for the owner seat; unmasked for admin (brief §12).")
ctype = {"existing": "existing (CIF)", "new_to_bank": "new to bank", "unknown": "unmatched"}[r.customer_type]
cif_help = (f"CIF linked {r.cif_linked_at}" if isinstance(r.cif_linked_at, str) and r.cif_linked_at
            else "no CIF yet — created when GSB onboarding opens the account")
h.metric("Customer", ctype, help=cif_help)
h.metric("Income", baht(r.monthly_income_thb) if pd.notna(r.monthly_income_thb) else "-")

with st.container(border=True):
    st.markdown(
        f"**Source:** :violet-badge[{r.utm_campaign or 'no UTM'}] → "
        f":violet-badge[{r.creative_id}] → :violet-badge[{r.channel}] "
        f"· submitted {r.submitted_ts:%d %b %Y}")
    st.button(":material/group: all customers from this creative",
              on_click=lambda: (st.session_state.drill.update({"creative_id": r.creative_id}),
                                st.switch_page("app_pages/customers.py")))

# ---- journey stepper
steps = ["New / assigned", "Contacted", "Docs submitted", "Application", "Approved", "Booked", "Disbursed"]
reached = steps.index(r.stage) if r.stage in steps else -1
badges = " ".join(
    (f":red-badge[✕ {r.stage}]" if reached < 0 and s == steps[0] else
     f":green-badge[{s}]" if j < reached else
     f":violet-badge[**{s} · {r.days_in_stage} d**]" if j == reached else
     f":gray-badge[{s}]")
    for j, s in enumerate(steps))
with st.container(border=True):
    st.markdown(badges)
    if r.stage not in steps:
        st.markdown(f":red-badge[{r.stage}] — reason: `{r.lost_reason or 'n/a'}`")

c1, c2 = st.columns([3, 2])
with c1, st.container(border=True):
    st.subheader("Activity timeline")
    ev = events[events.lead_id == lead_id].sort_values("changed_at", ascending=False)
    for _, e in ev.head(30).iterrows():
        who = e.changed_by if e.changed_by != "system" else ":material/smart_toy: system"
        what = {"status_change": f"{e.old_value or 'created'} → **{e.new_value}**",
                "assignment": f"assigned to **{e.new_value}**",
                "contact_attempt": f"contact attempt: {e.new_value} ({e.channel})"}.get(e.event_type, e.event_type)
        st.markdown(f"`{e.changed_at:%d %b %H:%M}` · {what} — {who}"
                    + (f" · _{e.note}_" if isinstance(e.note, str) and e.note else ""))
with c2:
    with st.container(border=True):
        st.subheader("Money")
        st.metric("Requested", baht(r.requested_amt_thb))
        st.metric("Approved", baht(r.approved_amt_thb))
        st.metric("Disbursed", baht(r.disbursed_amt_thb))
        if isinstance(r.application_id, str):
            st.caption(f"app {r.application_id}" + (f" · loan {r.loan_account_id}" if isinstance(r.loan_account_id, str) else ""))
    with st.container(border=True):
        if common.can_write():
            st.subheader("Update this lead")
            with st.form("wb"):
                new_status = st.selectbox("Status", common.LEAD_STATUSES)
                reason = st.selectbox("Reason code (required on terminal statuses)",
                                      [""] + common.REASON_CODES)
                note = st.text_input("Note (never parsed into a KPI)")
                if st.form_submit_button("Save", type="primary"):
                    if new_status in common.TERMINAL_STATUSES and not reason:
                        st.error("A reason code is required on a terminal status.")
                    else:
                        common.write_status(lead_id, new_status, reason, note,
                                            actor=f"demo-{common.role()}", actor_role=common.role())
                        st.toast("Saved — event appended, nothing overwritten")
                        st.rerun()
        else:
            # Seat map S5: a disabled dropdown reads as broken. Show the value,
            # name who can change it, and hand over something copyable.
            st.subheader("Status")
            st.markdown(f":material/lock: **{r.lead_status}**")
            st.caption("Status is set by the campaign admin.")
            st.code(f"{r.lead_id} · {r.stage} · {r.branch_name} · {int(r.days_in_stage)}d in stage",
                    language=None)
            st.caption("Copy the reference above into your message to the admin.")
