import pandas as pd
import streamlit as st

import common
from common import FILTERS, baht

cv_all = common.customer_view()

st.title("Customer list")

# ---- breadcrumb of stacked filters
drill = st.session_state.get("drill", {})
if drill:
    row = st.container(horizontal=True)
    row.markdown(":material/filter_alt: **Drilled:**")
    for k, v in list(drill.items()):
        label = FILTERS[k][0] if k in FILTERS else k
        shown = v if not isinstance(v, tuple) else f"{v[0]}-{v[1]}d"
        if isinstance(v, pd.Timestamp):
            shown = f"{v:%d %b}"
        if row.button(f"{label}: {shown} ✕", key=f"chip_{k}"):
            del st.session_state.drill[k]
            st.rerun()
    if row.button("clear all", type="tertiary"):
        st.session_state.drill = {}
        st.rerun()
else:
    st.caption("No filters — showing every lead. Click a chart on any campaign page to drill in.")

# ---- add-filter widgets
with st.expander(":material/tune: Add filters"):
    f1, f2, f3, f4, f5 = st.columns(5)
    for col, key, opts in [
        (f5, "customer_type", ["new_to_bank", "existing", "unknown"]),
        (f1, "stage", common.STAGE_ORDER),
        (f2, "segment", sorted(cv_all.segment.unique())),
        (f3, "branch_name", sorted(cv_all.branch_name.unique())),
        (f4, "creative_id", sorted(cv_all.creative_id.unique())),
    ]:
        v = col.selectbox(FILTERS[key][0], ["(any)"] + list(opts), key=f"add_{key}")
        if v != "(any)" and drill.get(key) != v:
            st.session_state.drill[key] = v
            st.rerun()

cv = common.apply_drill(cv_all)
q = st.text_input("Search", placeholder="name or lead id", label_visibility="collapsed")
if q:
    cv = cv[cv.name.str.contains(q, case=False) | cv.lead_id.str.contains(q, case=False)]

m = st.container(horizontal=True)
m.metric("Customers", f"{len(cv):,} / {len(cv_all):,}")
m.metric("Requested", baht(cv.requested_amt_thb.sum(), m=True))
m.metric("Disbursed", baht(cv.disbursed_amt_thb.sum(), m=True))
m.metric("Median days in stage", f"{cv.days_in_stage.median():.0f}" if len(cv) else "-")

if len(cv) == 0:
    st.info(":material/search_off: No customers match this filter combination.")
    if st.button("Clear all filters", type="primary"):
        st.session_state.drill = {}
        st.rerun()
    st.stop()

show = cv.sort_values("days_in_stage", ascending=False)[
    ["lead_id", "name", "segment", "creative_id", "stage", "days_in_stage",
     "owner", "requested_amt_thb", "branch_name"]].head(300).reset_index(drop=True)
show["open"] = ":material/person: open"

def _open():
    st.session_state.selected_lead = show.iloc[st.session_state.cust_click.row]["lead_id"]
    st.session_state.list_order = show.lead_id.tolist()
    st.switch_page("app_pages/customer_detail.py")

st.dataframe(show, hide_index=True, height=520, column_config={
    "lead_id": "Lead", "name": "Name", "segment": "Segment", "creative_id": "Creative",
    "stage": "Stage", "days_in_stage": "Days in stage", "owner": "Owner",
    "requested_amt_thb": st.column_config.NumberColumn("Requested ฿", format="localized"),
    "branch_name": "Branch",
    "open": st.column_config.ButtonColumn("", type="tertiary", on_click=_open, key="cust_click"),
})
if len(cv) > 300:
    st.caption(f"Showing 300 of {len(cv):,} — narrow the filters")
