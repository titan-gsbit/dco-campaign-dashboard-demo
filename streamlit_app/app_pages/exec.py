"""Overview - the campaign owner's landing screen.

Use case O1 must be answerable in zero clicks, so the pace bullet is the first
thing on the page. Five headline tiles, no more: dashboards with 5-7 KPIs beat
dashboards with 20+, and the other forty KPIs live one click deeper.
"""
import altair as alt
import pandas as pd
import streamlit as st

import common
import kpi
from common import baht

cv = common.customer_view()
media, *_ = common.load()
cs, ctrl, camp = common.crosssell(), common.control_group(), common.campaign()
now = common.as_of()

st.title("Overview")
st.caption(f"{camp['name']} · {camp.status} · {camp.start_date} → {camp.end_date}")

# ---- O1: pace against plan. The number the owner is asked about. -------------
actual, target, expected, pct = kpi.pace(cv, camp, now)
ahead = actual >= expected
with st.container(border=True):
    l, r = st.columns([3, 1])
    with l:
        st.subheader("Disbursed from loans ≥ ฿3M, against plan")
        band = pd.DataFrame({"x0": [0, target * .6, target * .85], "x1": [target * .6, target * .85, target],
                             "band": ["behind", "close", "on plan"]})
        base_h = 88
        bands = alt.Chart(band).mark_rect(opacity=.5).encode(
            x=alt.X("x0", title=None, axis=alt.Axis(format="~s", tickCount=5)), x2="x1",
            color=alt.Color("band", scale=alt.Scale(
                domain=["behind", "close", "on plan"],
                range=["#f1efec", "#e8e5e1", "#dcd9d5"]), legend=None))
        bar = alt.Chart(pd.DataFrame({"v": [actual]})).mark_bar(
            color="#b8296e", height=22).encode(x="v")
        tgt = alt.Chart(pd.DataFrame({"v": [target]})).mark_tick(
            color="#1b1b1a", thickness=3, size=52).encode(x="v")
        exp = alt.Chart(pd.DataFrame({"v": [expected]})).mark_tick(
            color="#a97b22", thickness=3, size=52).encode(x="v")
        st.altair_chart((bands + bar + exp + tgt).properties(height=base_h),
                        use_container_width=True)
        st.caption(f"▬ :red[disbursed ฿{actual/1e6:,.0f}M]  ·  "
                   f"▏:orange[expected by today ฿{expected/1e6:,.0f}M]  ·  "
                   f"▏target ฿{target/1e6:,.0f}M")
    with r:
        st.metric("of target", f"{pct:.0%}",
                  delta=f"{(actual-expected)/1e6:+,.1f}M vs plan",
                  delta_color="normal" if ahead else "inverse")
        gap_days = (pd.Timestamp(camp.end_date) - now).days
        st.metric("days left", f"{max(gap_days,0)}")
if not ahead:
    st.warning(f"Behind plan by ฿{(expected-actual)/1e6:,.1f}M. "
               f"Run the leak diagnosis on **Loan funnel** before reallocating budget.",
               icon=":material/trending_down:")

# ---- headline tiles, with week-over-week -------------------------------------
wk = now - pd.Timedelta(days=7)
prev = cv[~((cv.disbursed_ts > wk) | (cv.booked_ts > wk))]
d3_7 = cv.loc[(cv.disbursed_ts > wk) & (cv.disbursed_amt_thb >= 3e6), "disbursed_amt_thb"].sum()
leads_7 = int((cv.submitted_ts > wk).sum())
inc, baseline = kpi.incremental_disbursed_ge3m(cv, ctrl)
rev, spend = kpi.revenue(cv, cs), media.spend_thb.sum()

c = st.container(horizontal=True)
c.metric("Disbursed ≥ ฿3M", baht(actual, m=True), delta=f"+{d3_7/1e6:,.1f}M this week",
         help=kpi.disbursed_ge3m.definition.exclusions)
c.metric("Incremental ≥ ฿3M", baht(inc, m=True),
         delta=f"−{baseline/1e6:,.1f}M control baseline", delta_color="off",
         help="Net of the holdout. The brief: without this, ROAS credits customers "
              "who would have applied anyway.")
c.metric("Leads", f"{len(cv):,}", delta=f"+{leads_7:,} this week",
         help=f"Target {int(camp.target_leads):,}")
c.metric("Revenue", baht(rev, m=True),
         help="Interest realised + cross-sell. Cross-sell is a mocked feed.")
c.metric("ROAS", f"{kpi.roas(cv, cs, media):,.2f}x",
         help="Break-even at 1.00x. Gross, not incremental.")

col1, col2 = st.columns(2)

# ---- funnel (click a stage to drill) ----------------------------------------
with col1, st.container(border=True):
    st.subheader("Spend → disbursed")
    stages = pd.DataFrame({
        "stage": ["Leads", "Contacted", "Docs submitted", "Application", "Approved", "Booked", "Disbursed"],
        "n": [len(cv), int(cv.contacted_ts.notna().sum()), int(cv.docs_submitted_ts.notna().sum()),
              int(cv.app_ts.notna().sum()), int((cv.app_status == "Approved").sum()),
              int(cv.booked_ts.notna().sum()), int(cv.disbursed_ts.notna().sum())]})
    stages["conv"] = (stages.n / stages.n.shift(1)).fillna(1.0)
    stages["label"] = stages.apply(
        lambda r: f"{r.n:,}" if r.stage == "Leads" else f"{r.n:,}  ({r.conv:.0%})", axis=1)
    sel = alt.selection_point(name="sel", fields=["stage"], on="click")
    bars = alt.Chart(stages).mark_bar(color="#b8296e").encode(
        y=alt.Y("stage", sort=None, title=None), x=alt.X("n", title=None),
        opacity=alt.condition(sel, alt.value(1), alt.value(0.4)),
        tooltip=["stage", "n", alt.Tooltip("conv", format=".1%", title="from previous")])
    txt = alt.Chart(stages).mark_text(align="left", dx=5, color="#5f5d5a", fontSize=11).encode(
        y=alt.Y("stage", sort=None), x="n", text="label")
    ev = st.altair_chart((bars + txt).add_params(sel).properties(height=280),
                         on_select="rerun", key="exec_funnel")
    clicked = common.altair_click(ev, field="stage")
    if clicked:
        common.drill(reached=("Contacted" if clicked == "Leads" else clicked))
    common.drill_hint()

# ---- spend vs revenue --------------------------------------------------------
with col2, st.container(border=True):
    st.subheader("Spend vs interest accrued, cumulative")
    ms = media.groupby(media.date.dt.to_period("W").dt.start_time).spend_thb.sum().cumsum().rename("Ad spend")
    dl = cv.dropna(subset=["disbursed_ts"]).copy()
    dl["week"] = dl.disbursed_ts.dt.to_period("W").dt.start_time
    daily_int = dl.groupby("week").apply(
        lambda g: (g.disbursed_amt_thb * g.interest_rate_pct / 100 / 52).sum(),
        include_groups=False).cumsum().cumsum().rename("Interest accrued")
    st.line_chart(pd.concat([ms, daily_int], axis=1).ffill().fillna(0),
                  color=["#6f6d6a", "#b8296e"], height=280)

# ---- segment table with drill ------------------------------------------------
with st.container(border=True):
    st.subheader("Economics by segment")
    st.caption("Cost per lead through cost per disbursement — the brief's economics group.")
    rows = []
    for seg, g in cv.groupby("segment"):
        code = g.segment_code.iloc[0]
        m = media[media.segment_code == code]
        rows.append({
            "segment": seg, "leads": len(g),
            "cpl": kpi.cost_per_lead(g, m),
            "qual": kpi.qualified_rate(g),
            "cpa": kpi.cost_per_application(g, m),
            "cost_disb": kpi.cost_per_disbursement(g, m),
            "disbursed": g.disbursed_amt_thb.sum(),
            "leads_7d": int((g.submitted_ts > wk).sum()),
            "open": ":material/arrow_forward: open"})
    seg = pd.DataFrame(rows)

    def _seg_click():
        common.drill(segment=seg.iloc[st.session_state.seg_click.row]["segment"])

    st.dataframe(seg, hide_index=True, column_config={
        "segment": "Segment", "leads": "Leads",
        "cpl": st.column_config.NumberColumn("CPL ฿", format="%.0f"),
        "qual": st.column_config.NumberColumn("Qualified", format="percent"),
        "cpa": st.column_config.NumberColumn("Cost / application ฿", format="%.0f"),
        "cost_disb": st.column_config.NumberColumn("Cost / disbursement ฿", format="%.0f"),
        "disbursed": st.column_config.NumberColumn("Disbursed ฿", format="localized"),
        "leads_7d": st.column_config.NumberColumn("Leads 7d"),
        "open": st.column_config.ButtonColumn("", type="tertiary", on_click=_seg_click, key="seg_click"),
    })
