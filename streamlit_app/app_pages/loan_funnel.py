import altair as alt
import pandas as pd
import streamlit as st

import common
import kpi
from common import baht

cv = common.customer_view()
now = common.as_of()

st.title("Loan funnel")
st.caption("Of the people who applied, how much money actually left the bank — and are the recent numbers real yet?")

MATURITY_WEEKS = 4  # ponytail: single knob for the gate
gate_on = st.session_state.get("maturity_gate", True)
mature_cut = now - pd.Timedelta(weeks=MATURITY_WEEKS)
mat = cv[cv.lead_week <= mature_cut] if gate_on else cv

# ---- zone 1 of 4: alerts. The steepest drop is highlighted, not left to be spotted.
STAGES = [("Qualified leads", lambda d: (d.qualified_flag & ~d.duplicate_flag).sum()),
          ("Application", lambda d: d.app_ts.notna().sum()),
          ("Approved", lambda d: (d.app_status == "Approved").sum()),
          ("Booked", lambda d: d.booked_ts.notna().sum()),
          ("Disbursed", lambda d: d.disbursed_ts.notna().sum())]
_n = [(name, int(fn(mat))) for name, fn in STAGES]
_steps = [{"from": _n[i][0], "to": _n[i + 1][0],
           "conv": _n[i + 1][1] / _n[i][1] if _n[i][1] else 0.0,
           "lost": _n[i][1] - _n[i + 1][1]} for i in range(len(_n) - 1)]
worst = min(_steps, key=lambda x: x["conv"]) if _steps else None
if worst:
    st.error(f"**Steepest drop: {worst['from']} → {worst['to']} at {worst['conv']:.0%}.** "
             f"{worst['lost']:,} leads stop here. Level 4 of the KPI framework, so the fix "
             f"belongs to GSB credit, not to media or to branch follow-up.",
             icon=":material/priority_high:")
if not gate_on:
    st.warning("Maturity gate OFF — immature cohorts drag every rate below down.",
               icon=":material/hourglass_empty:")

# ---- zone 2 of 4: the stage row, with time-in-stage. "Stage-by-stage conversion
# with time-in-stage answers more questions than any other single CRM visual."
with st.container(border=True):
    st.subheader("Stage to stage")
    med = {"Application": kpi.lead_to_application_days(mat),
           "Approved": kpi.application_to_approval_days(mat)}
    cols = st.columns(len(_n))
    for i, (name, n) in enumerate(_n):
        with cols[i]:
            st.metric(name, f"{n:,}",
                      help=(f"median {med[name]:.0f} days to reach this stage" if name in med else None))
            if i:
                conv = _steps[i - 1]["conv"]
                is_worst = worst and name == worst["to"]
                # a conversion rate is not a change, so it must not render with a delta arrow
                st.markdown(f"{':red' if is_worst else ':gray'}[**{conv:.0%}** of previous]"
                            + (f"  \n:red[−{_steps[i-1]['lost']:,} lost]" if is_worst else ""))
            else:
                st.caption("funnel base")
    st.caption("Maturity gate applies from Application rightward, and nowhere left of it — "
               "so never read a gated number against an ungated one.")

c1, c2 = st.columns(2)
with c1, st.container(border=True):
    st.subheader("Cohort maturity")
    rows = []
    for wk, g in cv.groupby("lead_week"):
        max_age = int(((now - wk).days) // 7)
        for age in range(min(max_age, 9) + 1):
            cutoff = wk + pd.Timedelta(weeks=age + 1)
            rows.append({"lead_week": wk, "age": age, "leads": len(g),
                         "apps": int((g.app_ts <= cutoff).sum())})
    tri = pd.DataFrame(rows)
    tri["rate"] = tri.apps / tri.leads
    sel = alt.selection_point(name="sel", fields=["lead_week"], on="click")
    ch = (alt.Chart(tri).mark_rect().encode(
        x=alt.X("age:O", title="weeks since lead"),
        y=alt.Y("yearmonthdate(lead_week):O", title="lead week"),
        color=alt.Color("rate", scale=alt.Scale(scheme="pinkyellowgreen", reverse=True), legend=None),
        opacity=alt.condition(sel, alt.value(1), alt.value(0.6)),
        tooltip=[alt.Tooltip("lead_week:T"), "age", alt.Tooltip("rate", format=".0%")],
    ).add_params(sel).properties(height=300))
    ev = st.altair_chart(ch, on_select="rerun", key="tri")
    clicked = common.altair_click(ev, field="lead_week")
    if clicked:
        common.drill(lead_week=pd.Timestamp(clicked, unit="ms") if isinstance(clicked, (int, float)) else clicked)
    st.caption("Cumulative lead→application rate. Read down a column to compare cohorts fairly.")
    common.drill_hint("Click a cell to open that week's cohort")

with c2, st.container(border=True):
    st.subheader("Where the money leaks")
    wf = pd.DataFrame({
        "stage": ["Application", "Approved", "Booked", "Disbursed"],
        "amt": [cv.requested_amt_thb.sum() / 1e6, cv.approved_amt_thb.sum() / 1e6,
                cv.booked_amt_thb.sum() / 1e6, cv.disbursed_amt_thb.sum() / 1e6]})
    sel3 = alt.selection_point(name="sel", fields=["stage"], on="click")
    ch3 = (alt.Chart(wf).mark_bar(color="#b8296e").encode(
        x=alt.X("stage", sort=None, title=None), y=alt.Y("amt", title="฿ million"),
        opacity=alt.condition(sel3, alt.value(1), alt.value(0.5)),
        tooltip=["stage", alt.Tooltip("amt", format=",.0f", title="฿M")]).add_params(sel3).properties(height=300))
    ev3 = st.altair_chart(ch3, on_select="rerun", key="wf")
    common.drill_hint("Click a stage to open those customers")
    clicked = common.altair_click(ev3, field="stage")
    if clicked:
        common.drill(reached=clicked)

c3, c4, c5 = st.columns(3)
with c3, st.container(border=True):
    st.subheader("Approval rate" + (" (matured cohorts)" if gate_on else " (ALL cohorts)"))
    # F3 fixed in kpi v1.1: denominator is SUBMITTED applications per brief §7.
    # Both readings are shown because the corrected number is ~15pts lower and
    # has already been presented to GSB the old way.
    st.metric("Approved / submitted applications", f"{kpi.approval_rate(mat):.0%}",
              help=kpi.approval_rate.definition.brief)
    pend = int((mat.app_status == "Submitted").sum())
    st.caption(f"Decided-only reading: {kpi.approval_rate_decided(mat):.0%} "
               f"— {pend} applications still pending drag the corrected rate down.")
    # F2 fixed: denominator is QUALIFIED leads per brief §7.
    st.metric("Application rate from qualified leads", f"{kpi.application_rate(mat):.0%}",
              help=kpi.application_rate.definition.brief)
    if not gate_on:
        st.warning("Maturity gate OFF — recent cohorts drag these rates down artificially.")
with c4, st.container(border=True):
    st.subheader("Decline reasons")
    dr = cv.loc[cv.decline_reason.notna() & (cv.decline_reason != ""), "decline_reason"].value_counts().reset_index()
    sel4 = alt.selection_point(name="sel", fields=["decline_reason"], on="click")
    ch4 = (alt.Chart(dr).mark_bar(color="#c9c6c2").encode(
        y=alt.Y("decline_reason", sort="-x", title=None), x=alt.X("count", title=None),
        opacity=alt.condition(sel4, alt.value(1), alt.value(0.5))).add_params(sel4).properties(height=230))
    ev4 = st.altair_chart(ch4, on_select="rerun", key="decl")
    common.drill_hint("Click a reason to open those applications")
    clicked = common.altair_click(ev4, field="decline_reason")
    if clicked:
        common.drill(decline_reason=clicked)
with c5, st.container(border=True):
    st.subheader("Loan size by segment")
    st.altair_chart(alt.Chart(cv[cv.approved_amt_thb > 0]).mark_boxplot(color="#6f6d6a").encode(
        x=alt.X("segment_code", title=None), y=alt.Y("approved_amt_thb", title="approved ฿"),
    ).properties(height=230))

with st.container(border=True):
    st.subheader("Live pipeline")
    pipe = cv[cv.stage.isin(["Application", "Approved", "Booked", "Docs submitted"])]
    agg = pipe.groupby("stage").agg(n=("lead_id", "count"), amt=("requested_amt_thb", "sum"),
                                    med_days=("days_in_stage", "median")).reset_index()
    cols = st.columns(len(agg) or 1)
    for col, (_, r) in zip(cols, agg.iterrows()):
        with col:
            st.metric(r.stage, f"{int(r.n)}", f"{baht(r.amt, m=True)} · {r.med_days:.0f} d median",
                      delta_color="off")
            st.button("open", key=f"pipe_{r.stage}", width="stretch",
                      on_click=common.drill, kwargs={"stage": r.stage})

# ---- zone 4 of 4: source mix. Which sources survive to money, not just to leads.
with st.container(border=True):
    st.subheader("Source mix")
    st.caption("Every source looks fine at the top of the funnel. This is the same "
               "sources measured at the bottom — approval rate and cost per disbursement "
               "by channel (brief §7: approval rate by source).")
    media_df, *_ = common.load()
    rows = []
    for ch, g in mat.groupby("channel"):
        m = media_df[media_df.channel == ch]
        rows.append({
            "channel": ch, "leads": len(g),
            "qualified": kpi.qualified_rate(g),
            "app_rate": kpi.application_rate(g),
            "approval": kpi.approval_rate(g),
            "appr_requested": kpi.approved_to_requested(g),
            "cost_disb": kpi.cost_per_disbursement(g, m),
            "disbursed": g.disbursed_amt_thb.sum(),
            "open": ":material/arrow_forward: open"})
    src = pd.DataFrame(rows).sort_values("disbursed", ascending=False).reset_index(drop=True)

    def _src_click():
        common.drill(channel=src.iloc[st.session_state.src_click.row]["channel"])

    st.dataframe(src, hide_index=True, width="stretch", column_config={
        "channel": "Channel", "leads": "Leads",
        "qualified": st.column_config.NumberColumn("Qualified", format="percent"),
        "app_rate": st.column_config.NumberColumn("Application", format="percent"),
        "approval": st.column_config.NumberColumn("Approval", format="percent"),
        "appr_requested": st.column_config.NumberColumn("Approved / requested", format="percent"),
        "cost_disb": st.column_config.NumberColumn("Cost / disbursement ฿", format="%.0f"),
        "disbursed": st.column_config.NumberColumn("Disbursed ฿", format="localized"),
        "open": st.column_config.ButtonColumn("", type="tertiary", on_click=_src_click, key="src_click"),
    })
