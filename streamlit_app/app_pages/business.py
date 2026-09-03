import pandas as pd
import streamlit as st

import common
from common import baht

media, *_ = common.load()
cv = common.customer_view()
now = common.as_of()

st.title("Business KPI")
st.caption("Did this campaign make money, and which segment made it?")

spend = media.spend_thb.sum()
days_out = (now - cv.disbursed_ts).dt.days.clip(lower=0)
cv = cv.assign(interest=cv.disbursed_amt_thb.fillna(0) * cv.interest_rate_pct.fillna(0) / 100 / 365 * days_out.fillna(0))

c = st.container(horizontal=True)
c.metric("Ad spend", baht(spend, m=True))
c.metric("Disbursed", baht(cv.disbursed_amt_thb.sum(), m=True))
c.metric("Disbursed ≥ ฿3M", baht(cv.loc[cv.disbursed_amt_thb >= 3e6, "disbursed_amt_thb"].sum(), m=True))
c.metric("Interest accrued", baht(cv.interest.sum(), m=True))
c.metric("New-to-bank customers", f"{int(cv.loc[cv.booked_ts.notna() & cv.is_new_to_bank, 'prospect_id'].nunique()):,}",
         help="People with no GSB CIF before the campaign whose loan created one (CIF attached at booking)")
c.metric("Cross-sell revenue", "n/a", help="Not in mock data; needs product-holding feed")

with st.container(border=True):
    st.subheader("Unit economics by segment")
    seg_spend = media.groupby("segment_code").spend_thb.sum()
    u = cv.groupby(["segment", "segment_code"]).agg(
        leads=("lead_id", "count"), apps=("app_ts", "count"),
        disbursed_cnt=("disbursed_ts", "count"), disbursed=("disbursed_amt_thb", "sum"),
        interest=("interest", "sum")).reset_index()
    u["spend"] = u.segment_code.map(seg_spend)
    u["cost_per_loan"] = (u.spend / u.disbursed_cnt.clip(lower=1)).round(0)
    u["roas"] = (u.interest / u.spend).round(2)
    u = u.sort_values("roas", ascending=False).drop(columns="segment_code")
    u["open"] = ":material/arrow_forward: open"

    def _u_click():
        common.drill(segment=u.iloc[st.session_state.u_click.row]["segment"])

    st.dataframe(u, hide_index=True, column_config={
        "segment": "Segment", "leads": "Leads", "apps": "Apps", "disbursed_cnt": "Loans",
        "disbursed": st.column_config.NumberColumn("Disbursed ฿", format="localized"),
        "interest": st.column_config.NumberColumn("Interest ฿", format="localized"),
        "spend": st.column_config.NumberColumn("Spend ฿", format="localized"),
        "cost_per_loan": st.column_config.NumberColumn("Cost/loan ฿"),
        "roas": st.column_config.NumberColumn("ROAS", format="%.2fx"),
        "open": st.column_config.ButtonColumn("", type="tertiary", on_click=_u_click, key="u_click"),
    })

c1, c2 = st.columns(2)
with c1, st.container(border=True):
    st.subheader("Disbursed per week by product")
    d = cv.dropna(subset=["disbursed_ts"])
    wk = d.groupby([d.disbursed_ts.dt.to_period("W").dt.start_time, "product"]).disbursed_amt_thb.sum().reset_index()
    st.bar_chart(wk, x="disbursed_ts", y="disbursed_amt_thb", color="product", height=240)
with c2, st.container(border=True):
    st.subheader("Data joins — trust check")
    unmatched = int((cv.prospect_id.isna() | (cv.prospect_id == "")).sum())
    m1, m2, m3 = st.columns(3)
    m1.metric("Lead → prospect match", f"{1 - unmatched/len(cv):.1%}")
    m2.metric("Unmatched leads", f"{unmatched}")
    m3.metric("Duplicates", f"{int(cv.duplicate_flag.sum())}")
    b1, b2 = st.columns(2)
    b1.button(":material/search: open unmatched leads", on_click=common.drill, kwargs={"unmatched": True}, width="stretch")
    b2.button(":material/person_add: open new-to-bank customers", on_click=common.drill,
              kwargs={"customer_type": "new_to_bank"}, width="stretch")
    st.caption("If match rate drops, every figure on this page is suspect.")
