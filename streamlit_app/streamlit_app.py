import streamlit as st

import auth
import common

st.set_page_config(page_title="DCO Campaign", page_icon=":material/monitoring:", layout="wide")

if "drill" not in st.session_state:
    st.session_state.drill = {}

# ---- authentication gate (T2) ----------------------------------------------
# Nobody reaches a KPI page before signing in. The seat now comes from the user
# record rather than a picker, so every write is attributable to a named person.
if not auth.is_authenticated():
    st.navigation([st.Page("app_pages/login.py", title="Sign in",
                           icon=":material/login:")], position="hidden").run()
    st.stop()

common.pull_drill_from_url()
if "maturity_gate" not in st.session_state:
    st.session_state.maturity_gate = st.query_params.get("gate", "on") != "off"

user = auth.current_user()
role = user["role"]

with st.sidebar:
    st.markdown("**DCO Housing Loan Campaign**")
    st.caption("GSB · mock data demo")
    st.divider()
    st.markdown(f"**{user['name']}**")
    st.caption(f":material/badge: {auth.ROLE_LABEL[role]}")
    st.caption(auth.ROLE_HELP[role])
    if st.button("Sign out", icon=":material/logout:", width="stretch"):
        auth.sign_out()
        st.rerun()
    st.divider()
    st.toggle("Maturity gate", key="maturity_gate",
              help="Exclude lead cohorts younger than 4 weeks from headline rates. "
                   "Applies from Application rate down, and nowhere above it.")
    st.caption(f"Mock data · as of {common.as_of():%d %b %Y}")

# The nav is built FROM the permission table, so it can never disagree with the
# page guards about who sees what.
P = "app_pages/"
GROUPS = [
    ("", [("overview", "exec.py", "Overview", ":material/speed:")]),
    ("Campaign tracking", [
        ("engagement", "engagement.py", "Engagement", ":material/ads_click:"),
        ("lead_quality", "lead_quality.py", "Lead quality", ":material/verified:"),
        ("loan_funnel", "loan_funnel.py", "Loan funnel", ":material/filter_alt:"),
        ("business", "business.py", "Business KPI", ":material/payments:"),
    ]),
    ("Customers", [
        ("worklist", "worklist.py", "Worklist", ":material/checklist:"),
        ("customers", "customers.py", "Customer list", ":material/group:"),
        ("customer_detail", "customer_detail.py", "Customer detail", ":material/person:"),
    ]),
    ("Operate", [
        ("campaign_setup", "campaign_setup.py", "Campaign setup", ":material/tune:"),
        ("leads_import", "leads_import.py", "Target leads", ":material/upload_file:"),
        ("data_health", "data_health.py", "Data health", ":material/monitor_heart:"),
    ]),
    ("Reference", [
        ("dictionary", "dictionary.py", "KPI dictionary", ":material/function:"),
        ("account", "login.py", "Account", ":material/account_circle:"),
    ]),
]

pages = {}
for group, items in GROUPS:
    allowed = [st.Page(P + f, title=t, icon=i, default=(mod == "overview"))
               for mod, f, t, i in items
               if mod == "account" or auth.can_read(mod)]
    if allowed:
        pages[group] = allowed

page = st.navigation(pages, position="top")

# Two homes: marketing enters via a queue, the campaign owner via a number.
HOME = {"marketing": P + "worklist.py", "viewer": P + "exec.py"}
if st.session_state.get("_last_role") not in (None, role):
    st.session_state._last_role = role
    st.switch_page(HOME[role])
st.session_state._last_role = role

page.run()
common.render_freshness()
