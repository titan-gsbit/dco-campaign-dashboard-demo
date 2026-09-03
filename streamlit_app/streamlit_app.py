import streamlit as st

import common

st.set_page_config(page_title="DCO Campaign", page_icon=":material/monitoring:", layout="wide")

if "drill" not in st.session_state:
    st.session_state.drill = {}
if "role" not in st.session_state:
    # ?seat=admin makes a seat linkable — handy for demos, and it is the only way
    # to drive the seat picker from a test or a screenshot script.
    seat = st.query_params.get("seat", "campaign_owner")
    st.session_state.role = seat if seat in ("admin", "campaign_owner") else "campaign_owner"

SEAT_HELP = {
    "admin": "Reads everything unmasked, and holds the only human write path.",
    "campaign_owner": "Reads every KPI page. Writes nothing, ever. Contact fields masked.",
}

with st.sidebar:
    st.markdown("**DCO Housing Loan Campaign**")
    st.caption("GSB · mock data demo")
    st.divider()
    # ponytail: a demo control, not a product feature. Real seats come from SSO;
    # the picker is labelled as a presenter tool so reviewers stop evaluating it.
    st.selectbox("Seat (demo only)", common.ROLES, key="role",
                 format_func=lambda r: {"admin": "Admin", "campaign_owner": "Campaign owner"}[r])
    st.caption(f":material/present_to_all: {SEAT_HELP[st.session_state.role]}")
    st.divider()
    st.toggle("Maturity gate", key="maturity_gate", value=True,
              help="Exclude lead cohorts younger than 4 weeks from headline rates. "
                   "Applies from Application rate down, and nowhere above it.")
    st.caption(f"Mock data · as of {common.as_of():%d %b %Y}")

is_admin = common.can_write()

read_pages = {
    "": [st.Page("app_pages/exec.py", title="Overview", icon=":material/speed:", default=True)],
    "Diagnose": [
        st.Page("app_pages/engagement.py", title="Engagement", icon=":material/ads_click:"),
        st.Page("app_pages/lead_quality.py", title="Lead quality", icon=":material/verified:"),
        st.Page("app_pages/loan_funnel.py", title="Loan funnel", icon=":material/filter_alt:"),
        st.Page("app_pages/business.py", title="Business KPI", icon=":material/payments:"),
    ],
    "Customers": [
        st.Page("app_pages/customers.py", title="Customer list", icon=":material/group:"),
        st.Page("app_pages/customer_detail.py", title="Customer detail", icon=":material/person:"),
    ],
    "Reference": [st.Page("app_pages/dictionary.py", title="KPI dictionary", icon=":material/function:")],
}
if is_admin:
    # Write surfaces are ABSENT for the owner, not disabled (seat map C3).
    read_pages["Customers"].insert(0, st.Page("app_pages/worklist.py", title="Worklist",
                                              icon=":material/checklist:"))
    read_pages["Operate"] = [
        st.Page("app_pages/data_health.py", title="Data health", icon=":material/monitor_heart:"),
        st.Page("app_pages/campaign_setup.py", title="Campaign setup", icon=":material/tune:"),
    ]

page = st.navigation(read_pages, position="top")

# Two homes: the admin enters via a queue, the owner enters via a number.
HOME = {"admin": "app_pages/worklist.py", "campaign_owner": "app_pages/exec.py"}
role = st.session_state.role
if st.session_state.get("_last_role") not in (None, role):
    st.session_state._last_role = role
    st.switch_page(HOME[role])
st.session_state._last_role = role

page.run()
common.render_freshness()
