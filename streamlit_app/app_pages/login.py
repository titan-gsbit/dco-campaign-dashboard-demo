"""Login (checklist T2, senior's task 12).

Shown instead of the app when nobody is signed in. Marketing also manages users
from here, which is use case A7: onboarding a campaign owner should not require
a developer.
"""
import pandas as pd
import streamlit as st

import auth

st.markdown("### DCO Housing Loan Campaign")
st.caption("GSB · campaign tracking and CRM")

if not auth.is_authenticated():
    auth.render_signin()
    st.stop()

# ---------------- signed in ----------------
user = auth.current_user()
st.success(f"Signed in as **{user['name']}** · {auth.ROLE_LABEL[user['role']]}",
           icon=":material/check_circle:")
st.caption(auth.ROLE_HELP[user["role"]])

c1, c2 = st.columns([1, 3])
if c1.button("Sign out", icon=":material/logout:"):
    auth.sign_out()
    st.rerun()

with st.container(border=True):
    st.subheader("What this seat can reach")
    st.caption("From the permission table in `auth.py`. Every page asks it; no "
               "page decides for itself.")
    rows = [{"Module": m,
             "Read": "yes" if user["role"] in v["read"] else "—",
             "Write": "yes" if user["role"] in v["write"] else "—"}
            for m, v in auth.PERMISSIONS.items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, height=330, width="stretch")

if auth.can_write("campaign_setup"):
    with st.container(border=True):
        st.subheader("Add a user")
        st.caption("Use case A7. Onboarding a campaign owner should not need a "
                   "developer.")
        with st.form("adduser", clear_on_submit=True):
            a, b = st.columns(2)
            nu = a.text_input("Username", placeholder="owner.somchai")
            nn = b.text_input("Full name", placeholder="Somchai (GSB)")
            c, d = st.columns(2)
            npw = c.text_input("Password", type="password",
                               help="At least 8 characters.")
            nr = d.selectbox("Seat", list(auth.ROLE_LABEL),
                             format_func=lambda r: auth.ROLE_LABEL[r])
            if st.form_submit_button("Add user", type="primary"):
                ok, msg = auth.add_user(nu.strip(), nn.strip(), npw, nr)
                (st.success if ok else st.error)(msg)
