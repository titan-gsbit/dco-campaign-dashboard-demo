"""KPI dictionary - rendered from kpi.REGISTRY, so it cannot drift from the code.

The best-practice brief section 7 requires every KPI to carry a definition,
numerator, denominator, exclusions, source and version. This page is that
requirement satisfied by construction rather than by discipline.
"""
import pandas as pd
import streamlit as st

import common
import kpi

camp = common.campaign()

st.title("KPI dictionary")
st.caption(f"Definition version `{kpi.VERSION}` · attribution `{camp.attribution_rule}` "
           f"/ {camp.attribution_window_days} days · every rate derived, never stored")

st.info("**v1.2** settles what *qualified* means, from GSB's own droplead status "
        "list. That also moves application rate, which divides by qualified leads. "
        "**v1.1** corrected three denominators against the brief §7. Numbers quoted "
        "under an earlier version are not comparable to these.",
        icon=":material/history:")

with st.expander("What 'qualified' means, and why unreached leads are excluded"):
    st.markdown(
        "The deck asks for leads that passed preliminary screening — "
        "*ผ่านการคัดกรองเบื้องต้น*. GSB's `สถานะ` field already records that, and it "
        "separates three judgements a single flag collapses: **eligibility**, "
        "**intent**, and **reachability**.\n\n"
        "A lead nobody reached has not been screened, so it sits in neither the "
        "numerator nor the denominator. Counting it as unqualified makes a "
        "follow-up backlog look like a targeting problem, and those go to "
        "different people. Reach is measured separately, by contact rate.")
    st.dataframe(pd.DataFrame(
        [{"สถานะ": s, "Counts as": b} for b, ss in
         [("Qualified", sorted(kpi.QUALIFIED_STATUSES)),
          ("Not qualified", sorted(kpi.DISQUALIFIED_STATUSES)),
          ("Not screened — excluded from both", sorted(kpi.UNSCREENED_STATUSES))]
         for s in ss if not s.isascii()]),
        hide_index=True, width="stretch")

rows = [{
    "kpi": d.name,
    "formula": d.formula,
    "source": d.source,
    "gate": "matured cohorts" if d.gated else "—",
    "exclusions": d.exclusions or "—",
    "spec": d.brief or "—",
    "changed": ("v1.2" if key in kpi.CHANGED_IN_V12 else
                "v1.1" if key in kpi.CHANGED_IN_V11 else ""),
} for key, d in kpi.REGISTRY.items()]

df = pd.DataFrame(rows)
q = st.text_input("Filter", placeholder="approval, cost, speed, holdout …")
if q:
    df = df[df.apply(lambda r: q.lower() in " ".join(map(str, r.values)).lower(), axis=1)]

st.dataframe(df, hide_index=True, height=620, column_config={
    "kpi": st.column_config.TextColumn("KPI", width="medium"),
    "formula": st.column_config.TextColumn("Numerator / denominator", width="medium"),
    "source": "Source",
    "gate": "Maturity gate",
    "exclusions": st.column_config.TextColumn("Exclusions", width="medium"),
    "spec": "Specified by",
    "changed": st.column_config.TextColumn("Changed", width="small"),
})

st.caption(f"{len(kpi.REGISTRY)} KPIs defined in `kpi.py`. "
           "Pages call these functions; no page computes a rate inline.")
