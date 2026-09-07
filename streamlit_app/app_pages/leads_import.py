"""Target leads: import and summary (checklist T4, senior's task 2).

"Import finalized lead to DB and display summary by Age, Income, Occupation."

This is also the "targeted" half of the Overview cross-tab: without a target
list there is nothing to compare the achieved population against, so the drift
that makes the grid worth looking at cannot be seen.
"""
import pandas as pd
import streamlit as st

import common

common.guard_admin(module="leads_import")

REQUIRED = ["age_band", "income_band", "occupation", "region"]

st.title("Target leads")
st.caption("The finalized lead list, imported before the campaign runs. "
           "Its shape is what the Overview cross-tab compares against.")

target = common.target_leads()

# ---- current list -----------------------------------------------------------
with st.container(border=True):
    st.subheader("Current list")
    if not len(target):
        st.info("No target list imported yet.", icon=":material/inbox:")
    else:
        c = st.container(horizontal=True)
        c.metric("Leads", f"{len(target):,}")
        c.metric("Imported", str(target.imported_at.iloc[0])[:16])
        c.metric("By", target.imported_by.iloc[0])
        c.metric("Source file", target.source_file.iloc[0])
        st.caption("An import is versioned: which file, when, by whom, how many rows. "
                   "Replacing the list keeps the previous version on disk.")

# ---- summary ----------------------------------------------------------------
if len(target):
    with st.container(border=True):
        st.subheader("Summary")
        st.caption("Senior's task 2: by age, income and occupation.")
        dim = st.segmented_control(
            "Break down by", ["Age band", "Income band", "Occupation", "Region"],
            default="Age band", label_visibility="collapsed")
        col = {"Age band": "age_band", "Income band": "income_band",
               "Occupation": "occupation", "Region": "region"}[dim]
        counts = (target[col].value_counts().rename_axis(dim)
                  .reset_index(name="Leads"))
        counts["Share"] = counts.Leads / counts.Leads.sum()
        a, b = st.columns([2, 3])
        a.dataframe(counts, hide_index=True, width="stretch", column_config={
            "Leads": st.column_config.NumberColumn(format="localized"),
            "Share": st.column_config.NumberColumn(format="percent")})
        b.bar_chart(counts.set_index(dim)["Leads"], color="#b8296e", height=300)

# ---- import -----------------------------------------------------------------
with st.container(border=True):
    st.subheader("Import a new list")
    st.caption(f"Excel or CSV. Required columns: {', '.join(f'`{c}`' for c in REQUIRED)}. "
               "Rows missing any of them are rejected and counted, never silently dropped.")
    up = st.file_uploader("Lead list", type=["xlsx", "csv"], label_visibility="collapsed")
    if up is not None:
        try:
            new = pd.read_excel(up) if up.name.endswith("xlsx") else pd.read_csv(up)
        except Exception as e:                                   # noqa: BLE001
            st.error(f"Could not read the file: {e}")
            st.stop()

        missing = [c for c in REQUIRED if c not in new.columns]
        if missing:
            st.error(f"Missing required column(s): {', '.join(missing)}. "
                     f"Found: {', '.join(map(str, new.columns[:12]))}")
            st.stop()

        bad = new[REQUIRED].isna().any(axis=1)
        st.success(f"Read **{len(new):,}** rows from `{up.name}`.")
        c = st.container(horizontal=True)
        c.metric("Will import", f"{int((~bad).sum()):,}")
        c.metric("Rejected", f"{int(bad.sum()):,}",
                 help="Rows with a blank required field.")
        if bad.any():
            with st.expander(f"Show {int(bad.sum())} rejected rows"):
                st.dataframe(new[bad].head(50), hide_index=True)
        st.dataframe(new[~bad].head(8), hide_index=True, width="stretch")

        if st.button("Import this list", type="primary", icon=":material/upload:"):
            common.import_target_leads(new[~bad], up.name, common.actor())
            st.success(f"Imported {int((~bad).sum()):,} leads. "
                       "The Overview cross-tab now compares against this list.")
            st.rerun()
