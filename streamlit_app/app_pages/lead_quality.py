import altair as alt
import pandas as pd
import streamlit as st

import common
import kpi

media, *_ = common.load()
cv = common.customer_view()

st.title("Lead quality")
st.caption("Are the cheap leads also the good leads?")

c1, c2 = st.columns(2)
with c1, st.container(border=True):
    st.subheader("Cost per lead vs qualified rate")
    q = cv.groupby("creative_id").agg(leads=("lead_id", "count"),
                                      qual=("qualified_flag", "mean")).reset_index()
    q = q.merge(media.groupby("creative_id").spend_thb.sum().reset_index(), on="creative_id")
    q["cpl"] = q.spend_thb / q.leads
    sel = alt.selection_point(name="sel", fields=["creative_id"], on="click")
    ch = (alt.Chart(q).mark_circle().encode(
        x=alt.X("cpl", title="cost per lead ฿"),
        y=alt.Y("qual", axis=alt.Axis(format="%"), title="qualified rate"),
        size=alt.Size("leads", legend=None),
        color=alt.value("#b8296e"),
        opacity=alt.condition(sel, alt.value(0.9), alt.value(0.35)),
        tooltip=["creative_id", "leads", alt.Tooltip("cpl", format=",.0f"),
                 alt.Tooltip("qual", format=".0%")]).add_params(sel).properties(height=280))
    ev = st.altair_chart(ch, on_select="rerun", key="lq_scatter")
    clicked = common.altair_click(ev, field="creative_id")
    common.drill_hint("Click a bubble to open that creative's leads")
    if clicked:
        common.drill(creative_id=clicked)
with c2, st.container(border=True):
    st.subheader("Leads per week by segment")
    wk = cv.groupby(["lead_week", "segment"]).size().rename("leads").reset_index()
    st.altair_chart(alt.Chart(wk).mark_bar().encode(
        x=alt.X("lead_week:T", title=None), y=alt.Y("leads", title=None),
        color=alt.Color("segment", legend=alt.Legend(orient="bottom", columns=2, title=None)),
        tooltip=["lead_week", "segment", "leads"]).properties(height=280))

c3, c4, c5 = st.columns(3)
with c3, st.container(border=True):
    st.subheader("Lost reasons")
    lr = cv.loc[cv.lost_reason.notna() & (cv.lost_reason != ""), "lost_reason"].value_counts().reset_index()
    sel2 = alt.selection_point(name="sel", fields=["lost_reason"], on="click")
    ch2 = (alt.Chart(lr).mark_bar(color="#c9c6c2").encode(
        y=alt.Y("lost_reason", sort="-x", title=None), x=alt.X("count", title=None),
        opacity=alt.condition(sel2, alt.value(1), alt.value(0.5))).add_params(sel2).properties(height=220))
    ev2 = st.altair_chart(ch2, on_select="rerun", key="lq_lost")
    clicked = common.altair_click(ev2, field="lost_reason")
    common.drill_hint("Click a reason to open those leads")
    if clicked:
        common.drill(lost_reason=clicked)
with c4, st.container(border=True):
    st.subheader("Hours to first contact")
    ttc = ((cv.contacted_ts - cv.submitted_ts).dt.total_seconds() / 3600).dropna()
    st.altair_chart(alt.Chart(ttc.rename("hours").reset_index()).mark_bar(color="#c9c6c2").encode(
        x=alt.X("hours", bin=alt.Bin(maxbins=30), title="hours"),
        y=alt.Y("count()", title=None)).properties(height=220))
    st.caption(f"Median {ttc.median():.0f} h · SLA 24 h per best-practice doc")
with c5, st.container(border=True):
    st.subheader("Aging — contacted, no docs")
    ag = cv[(cv.stage == "Contacted")]
    buckets = [("0-2 d", 0, 2), ("3-5 d", 3, 5), ("6-10 d", 6, 10), ("11-20 d", 11, 20), ("21+ d", 21, 9999)]
    for lab, lo, hi in buckets:
        n = int(ag.days_in_stage.between(lo, hi).sum())
        st.button(f"{lab} — {n} leads", key=f"age_{lo}", width="stretch",
                  on_click=common.drill, kwargs={"stage": "Contacted", "aging": (lo, hi)})

with st.container(border=True):
    st.subheader("Branches")
    br = cv.groupby("branch_name").agg(
        leads=("lead_id", "count"),
        # F1 fixed: contacted / ASSIGNED, not / all leads (brief §7). Unassigned
        # leads are a routing gap, not a calling failure.
        contact_rate=("lead_id", lambda s: kpi.contact_rate(cv.loc[s.index])),
        docs=("docs_submitted_ts", lambda s: s.notna().sum()),
        med_hrs=("submitted_ts", "count")).reset_index()
    hrs = ((cv.contacted_ts - cv.submitted_ts).dt.total_seconds() / 3600)
    br["med_hrs"] = br.branch_name.map(cv.assign(h=hrs).groupby("branch_name").h.median())
    br["open"] = ":material/arrow_forward: open"

    def _br_click():
        common.drill(branch_name=br.iloc[st.session_state.br_click.row]["branch_name"])

    st.dataframe(br, hide_index=True, column_config={
        "branch_name": "Branch", "leads": "Leads",
        "contact_rate": st.column_config.NumberColumn("Contact rate", format="percent"),
        "docs": "Docs submitted",
        "med_hrs": st.column_config.NumberColumn("Median hrs to contact", format="%.0f"),
        "open": st.column_config.ButtonColumn("", type="tertiary", on_click=_br_click, key="br_click"),
    })
