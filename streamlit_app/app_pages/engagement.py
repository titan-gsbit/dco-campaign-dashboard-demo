import altair as alt
import pandas as pd
import streamlit as st

import common

media, prospects, sessions, leads, *_ = common.load()
cv = common.customer_view()

st.title("Engagement")
st.caption("Does the creative pull people in, and where do they fall out before becoming a lead?")

c1, c2 = st.columns([2, 1])
with c1, st.container(border=True):
    st.subheader("Landing page views, daily")
    st.line_chart(sessions.groupby(sessions.ts.dt.date).size().rename("views"),
                  color="#6f6d6a", height=240)
with c2, st.container(border=True):
    st.subheader("Landing page → lead")
    fun = pd.DataFrame({
        "step": ["LP views", "Form starts", "Leads"],
        "n": [len(sessions), int(sessions.form_start.sum()), int(sessions.form_complete.sum())]})
    st.altair_chart(alt.Chart(fun).mark_bar(color="#b8296e").encode(
        y=alt.Y("step", sort=None, title=None), x=alt.X("n", title=None),
        tooltip=["step", "n"]).properties(height=240))

c3, c4, c5 = st.columns(3)
with c3, st.container(border=True):
    st.subheader("Scroll depth reached")
    depth = (sessions.max_scroll_pct.value_counts(normalize=True).sort_index(ascending=False)
             .cumsum().sort_index().rename("share").reset_index())
    st.altair_chart(alt.Chart(depth).mark_line(point=True, color="#1b1b1a").encode(
        x=alt.X("max_scroll_pct:O", title="scrolled to (%)"),
        y=alt.Y("share", axis=alt.Axis(format="%"), title=None)).properties(height=200))
    st.caption("No drill — anonymous sessions, no person behind them")
with c4, st.container(border=True):
    st.subheader("Time on page")
    st.altair_chart(alt.Chart(sessions[sessions.time_on_lp_sec < 600]).mark_bar(color="#c9c6c2").encode(
        x=alt.X("time_on_lp_sec", bin=alt.Bin(maxbins=25), title="seconds"),
        y=alt.Y("count()", title=None)).properties(height=200))
with c5, st.container(border=True):
    st.subheader("Form abandonment, last field")
    ab = sessions.loc[sessions.abandon_field.notna() & (sessions.abandon_field != ""),
                      "abandon_field"].value_counts().reset_index()
    st.altair_chart(alt.Chart(ab).mark_bar(color="#c9c6c2").encode(
        y=alt.Y("abandon_field", sort="-x", title=None),
        x=alt.X("count", title=None)).properties(height=200))

with st.container(border=True):
    st.subheader("Creative scorecard")
    sc = sessions.groupby("creative_id").agg(
        lp_views=("session_id", "count"),
        median_time=("time_on_lp_sec", "median"),
        form_starts=("form_start", "sum"), leads=("form_complete", "sum")).reset_index()
    sc = sc.merge(media.groupby("creative_id").spend_thb.sum().reset_index(), on="creative_id")
    sc["cpl"] = (sc.spend_thb / sc.leads.clip(lower=1)).round(0)
    sc["open"] = ":material/arrow_forward: leads"

    def _cr_click():
        common.drill(creative_id=sc.iloc[st.session_state.cr_click.row]["creative_id"])

    st.download_button(":material/download: Export scorecard (CSV)",
                       sc.drop(columns="open").to_csv(index=False),
                       file_name="creative_scorecard.csv", mime="text/csv",
                       help="Aggregate-only — safe to share with the media agency")
    st.dataframe(sc, hide_index=True, column_config={
        "creative_id": "Creative", "lp_views": "LP views",
        "median_time": st.column_config.NumberColumn("Median time (s)", format="%.0f"),
        "form_starts": "Form starts", "leads": "Leads",
        "spend_thb": st.column_config.NumberColumn("Spend ฿", format="localized"),
        "cpl": st.column_config.NumberColumn("CPL ฿"),
        "open": st.column_config.ButtonColumn("", type="tertiary", on_click=_cr_click, key="cr_click"),
    })
