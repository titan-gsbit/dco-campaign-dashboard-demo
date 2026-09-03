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

st.info("Three denominators changed in **v1.1** to match the best-practice brief §7. "
        "Numbers quoted from an earlier version are not comparable.",
        icon=":material/history:")

rows = [{
    "kpi": d.name,
    "formula": d.formula,
    "source": d.source,
    "gate": "matured cohorts" if d.gated else "—",
    "exclusions": d.exclusions or "—",
    "spec": d.brief or "—",
    "changed": "v1.1" if key in kpi.CHANGED_IN_V11 else "",
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
