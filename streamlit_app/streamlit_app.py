import streamlit as st

import auth
import common

st.set_page_config(page_title="DCO Campaign", page_icon=":material/monitoring:", layout="wide")

if "drill" not in st.session_state:
    st.session_state.drill = {}

# ---- authentication gate (T2) ----------------------------------------------
# Nobody reaches a KPI page before signing in. The seat now comes from the user
# record rather than a picker, so every write is attributable to a named person.
#
# A deep link always starts a fresh browser session, so it always lands here.
# Without remembering where the visitor was headed, every documented step URL
# (/customers?stage=Booked&...) would dump them on Overview with no filters,
# which would quietly break the flow tutorials and the workbook's Link column.
if not auth.is_authenticated():
    # No st.navigation here on purpose: see auth.render_signin. Registering pages
    # before sign-in makes Streamlit resolve (and lose) the requested path.
    if "_intended" not in st.session_state:
        st.session_state._intended = common.destination_from_url(
            getattr(st.context, "url", None))
    auth.render_signin()
    st.stop()

# Put the query string back before anything reads it: showing the login page
# rewrites the URL, so the filters that came in with the link are gone by now.
_dest = st.session_state.pop("_intended", None)
if _dest and _dest.get("params"):
    for k, v in _dest["params"].items():
        st.query_params[k] = v

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
GROUPS = [(g, [(mod, stem + ".py", title, icon) for mod, stem, title, icon in items])
          for g, items in common.PAGES]

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

# Land on the page the link asked for, if this seat may read it.
if _dest and _dest.get("stem"):
    hit = common.resolve_page(_dest["stem"])
    if hit and (hit[0] == "account" or auth.can_read(hit[0])):
        st.session_state._last_role = role
        st.switch_page(hit[1])
    elif hit:
        st.warning(f"Your seat cannot open **{_dest['stem']}**. Showing your home "
                   f"page instead.", icon=":material/lock:")

if st.session_state.get("_last_role") not in (None, role):
    st.session_state._last_role = role
    st.switch_page(HOME[role])
st.session_state._last_role = role

page.run()
common.render_freshness()
