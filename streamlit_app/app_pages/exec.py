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
media, prospects, *_ = common.load()
cs, ctrl, camp = common.crosssell(), common.control_group(), common.campaign()
target_list = common.target_leads()  # not `target`: that is the baht target
now = common.as_of()

st.title("Overview")

# ---- T5a: campaign profile ---------------------------------------------------
# Deliberately NOT st.metric. A metric is for a number you read at a glance;
# using it for a product name and a date range makes the page shout identity
# louder than performance, and pushes the one number that matters below the fold.
PRODUCT_LABEL = {"housing+refinance": "Housing loan · Refinance",
                 "housing": "Housing loan", "refinance": "Refinance"}
with st.container(border=True):
    h1, h2 = st.columns([4, 1])
    h1.markdown(f"#### {camp['name']} &nbsp;:violet-badge[{camp.status}]")
    if common.can_write("campaign_setup"):
        try:
            h2.page_link("app_pages/campaign_setup.py", label="Edit campaign",
                         icon=":material/tune:")
        except Exception:                       # noqa: BLE001
            h2.caption(":material/tune: Campaign setup")
    st.caption(camp.objective)
    facts = [
        ("Product", PRODUCT_LABEL.get(str(camp["product"]), str(camp["product"]))),
        ("Period", f"{camp.start_date} → {camp.end_date}"),
        ("Target", f"฿{camp.target_disbursed_ge3m_thb/1e6:,.0f}M disbursed ≥ ฿3M"),
        ("Budget", f"฿{camp.budget_thb/1e6:,.1f}M"),
        ("Owner", str(camp.owner_user_id)),
        ("Attribution", f"{camp.attribution_rule.replace('_', ' ')}, "
                        f"{camp.attribution_window_days}-day window"),
    ]
    cols = st.columns(3)
    for i, (k, v) in enumerate(facts):
        cols[i % 3].markdown(
            f"<div style='line-height:1.35;margin-bottom:.55rem'>"
            f"<span style='font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;"
            f"opacity:.55'>{k}</span><br><span style='font-size:.95rem'>{v}</span></div>",
            unsafe_allow_html=True)

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
        st.caption(
            f":red[**Pink bar** = disbursed ฿{actual/1e6:,.0f}M] &nbsp;&nbsp;"
            f":orange[**Amber line** = expected by today ฿{expected/1e6:,.0f}M] &nbsp;&nbsp;"
            f"**Black line** = target ฿{target/1e6:,.0f}M")
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

# ---- T5b: who we aimed at, against who we got --------------------------------
# Two grids, same axes, counts inside. One grid alone is descriptive; the pair
# shows targeting drift, which is the decision the table can actually support.
with st.container(border=True):
    st.subheader("Targeted vs achieved")
    DIMS = {"Age band": "age_band", "Income band": "income_band",
            "Occupation": "occupation", "Region": "region"}
    # Bands are ordinal. Sorted alphabetically they read "20 - 30, 41 - 50,
    # 61 - 65, Under 20", which makes a distribution impossible to see.
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(
        _os.path.dirname(_os.path.abspath(__file__)))), "dashboard-mockup"))
    try:
        import gsb_vocab as _V
        ORDER = {"age_band": _V.AGE_BANDS, "income_band": _V.INCOME_BANDS}
    except Exception:                                   # noqa: BLE001
        ORDER = {}
    d1, d2 = st.columns(2)
    rows_dim = d1.selectbox("Rows", list(DIMS), index=0)
    cols_dim = d2.selectbox("Columns", list(DIMS), index=1)
    rk, ck = DIMS[rows_dim], DIMS[cols_dim]

    if rk == ck:
        st.warning("Pick two different dimensions.", icon=":material/error:")
    elif not len(target_list):
        st.info("No target list imported yet, so there is nothing to compare against. "
                "Import one on the Target leads page.", icon=":material/inbox:")
    else:
        # achieved = prospects who became leads; that is the population the
        # campaign actually reached, and where age and income live.
        got = cv.merge(prospects[["prospect_id", "age_band", "income_band",
                                  "occupation"]],
                       on="prospect_id", how="left", suffixes=("", "_p"))
        got["region"] = got.get("region", pd.Series(index=got.index, dtype=object))

        def grid(df, r, c):
            if r not in df.columns or c not in df.columns:
                return pd.DataFrame()
            d = df.dropna(subset=[r, c])
            return pd.crosstab(d[r], d[c]) if len(d) else pd.DataFrame()

        g_t, g_a = grid(target_list, rk, ck), grid(got, rk, ck)
        if g_a.empty:
            st.info(f"The achieved population has no {cols_dim.lower()} on it. "
                    f"Age and income come from the application feed; region comes "
                    f"from the branch. Try a different pair.", icon=":material/info:")
        else:
            # share the axes so the two grids are genuinely comparable
            idx = sorted(set(g_t.index) | set(g_a.index))
            col = sorted(set(g_t.columns) | set(g_a.columns))
            g_t = g_t.reindex(index=idx, columns=col, fill_value=0)
            g_a = g_a.reindex(index=idx, columns=col, fill_value=0)
            # Colour by share of each grid's own total, on one shared domain.
            # Sharing an ABSOLUTE scale looked right and read wrong: the target
            # list is larger, so its cells dominated and the achieved grid went
            # flat. The question here is whether the mix shifted, not whether
            # there are fewer people, and share answers that.
            def _ord(key, present):
                want = ORDER.get(key)
                return ([v for v in want if v in present] +
                        sorted(p for p in present if p not in want)) if want \
                    else sorted(present)

            row_sort = _ord(rk, set(idx))
            col_sort = _ord(ck, set(col))
            # Cast to native python: a numpy scalar in an Altair spec is not
            # JSON-serialisable, and Streamlit renders nothing at all rather than
            # raising, so the charts just silently vanish.
            tot_t = int(max(g_t.to_numpy().sum(), 1))
            tot_a = int(max(g_a.to_numpy().sum(), 1))
            hi = float(max((g_t.to_numpy() / tot_t).max(),
                           (g_a.to_numpy() / tot_a).max()))

            import re as _re

            def _short(v):
                """Drop the ordering prefix for display. "01. 0-5,000" is a code;
                the reader only needs the band."""
                return _re.sub(r"^\d+\.\s*", "", str(v))

            def heat(g, total, title):
                d = g.reset_index().melt(id_vars=g.index.name or "index",
                                         var_name="col", value_name="n")
                d.columns = ["row", "col", "n"]
                d["share"] = d.n / total
                d["row"] = d.row.map(_short)
                d["col"] = d.col.map(_short)
                base = alt.Chart(d).encode(
                    x=alt.X("col:O", title=None, sort=[_short(c) for c in col_sort],
                            axis=alt.Axis(labelAngle=-35, labelLimit=110,
                                          labelOverlap=False, labelFontSize=10)),
                    y=alt.Y("row:O", title=None, sort=[_short(r) for r in row_sort],
                            axis=alt.Axis(labelLimit=140, labelOverlap=False,
                                          labelFontSize=10)))
                cells = base.mark_rect().encode(
                    color=alt.Color("share:Q",
                                    scale=alt.Scale(scheme="purples", domain=[0, hi]),
                                    legend=None),
                    tooltip=[alt.Tooltip("row", title=rows_dim),
                             alt.Tooltip("col", title=cols_dim),
                             alt.Tooltip("n", title="leads", format=","),
                             alt.Tooltip("share", title="share", format=".1%")])
                labels = base.mark_text(fontSize=11).encode(
                    text=alt.Text("n:Q", format=","),
                    color=alt.condition(alt.datum.share > hi * 0.6,
                                        alt.value("white"), alt.value("#3d3b39")))
                return (cells + labels).properties(height=270, title=title)

            l, r = st.columns(2)
            l.altair_chart(heat(g_t, tot_t, f"Targeted · {len(target_list):,} leads"),
                           width="stretch")
            r.altair_chart(heat(g_a, tot_a, f"Achieved · {len(got):,} leads"),
                           width="stretch")
            st.caption("Shaded by share of each side's own total, on one scale, so the "
                       "two are comparable even though the populations differ in size. "
                       "Numbers in the cells are lead counts.")

            # the one number that says whether targeting held
            ts = (g_t.sum(axis=1) / max(g_t.to_numpy().sum(), 1))
            as_ = (g_a.sum(axis=1) / max(g_a.to_numpy().sum(), 1))
            drift = (as_ - ts).abs().sum() / 2
            worst = (as_ - ts).abs().idxmax() if len(as_) else None
            tone = "red" if drift > 0.25 else "orange" if drift > 0.1 else "green"
            st.markdown(
                f"**Row-share drift :{tone}[{drift:.0%}]** — the share of the achieved "
                f"population sitting in a different {rows_dim.lower()} than intended, "
                f"where 0% would mean the campaign reached exactly who it aimed at."
                + (f" The biggest single gap is **{worst}**." if worst is not None else ""))

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
