# -*- coding: utf-8 -*-
"""Mock the feeds the seat map flagged as missing (M1-M5).

Runs AFTER generate_mock_data.py and reads its output, so the numbers stay
consistent with the main mock. Seeded with the same 42.

Produces:
  campaign.csv        the registry the best-practice brief section 4 requires
                      (target, budget, attribution rule, control-group pct) - M1
  crosssell_monthly.csv  revenue from other products bought by campaign customers - M4
  control_group.csv   the holdout, so "incremental" means something - M5
and adds a `reach` column to media_daily.csv - M2.
"""
import os

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_data")

media = pd.read_csv(os.path.join(OUT, "media_daily.csv"), parse_dates=["date"])
leads = pd.read_csv(os.path.join(OUT, "leads.csv"), parse_dates=["submitted_ts"])
loans = pd.read_csv(os.path.join(OUT, "loans.csv"), parse_dates=["booked_ts", "disbursed_ts"])
apps = pd.read_csv(os.path.join(OUT, "applications.csv"), parse_dates=["submitted_ts"])

CAMPAIGN_START = pd.Timestamp("2026-09-01")
CAMPAIGN_END = pd.Timestamp("2026-11-30")

# ---- M1 · campaign registry -------------------------------------------------
# Brief section 4: business / schedule / finance / audience / execution /
# governance / measurement. One row per campaign; the app filters on campaign_id
# everywhere so a second row costs nothing.
pd.DataFrame([{
    "campaign_id": "DCO2026",
    "name": "DCO Housing Loan 2026",
    "product": "housing+refinance",
    "objective": "Acquire mid-market housing loans of THB 3M or more",
    "status": "Running",
    "start_date": CAMPAIGN_START.date(),
    "end_date": CAMPAIGN_END.date(),
    # the number O1 needs and did not have
    "target_disbursed_ge3m_thb": 450_000_000,
    "target_leads": 3_000,
    "budget_thb": float(media.spend_thb.sum().round(-3)) * 1.35,
    "planned_cpl_thb": 950,
    "cost_owner": "GSB Marketing",
    "utm_tag": "DCO2026",
    # measurement block - every attributed number assumes this, so it is stored
    "attribution_rule": "last_click",
    "attribution_window_days": 30,
    "control_group_pct": 8.0,
    "kpi_def_version": "v1.1",
    "owner_user_id": "owner.gsb",
}]).to_csv(os.path.join(OUT, "campaign.csv"), index=False)

# ---- M2 · reach, so frequency is computable ---------------------------------
# Reach < impressions, and the ratio tightens as a creative saturates its
# audience: later days in a campaign show higher frequency for the same spend.
day_idx = (media.date - CAMPAIGN_START).dt.days.clip(lower=0)
saturation = 1.0 + 0.55 * (day_idx / max(day_idx.max(), 1))          # 1.0 -> 1.55
freq = np.clip(rng.normal(1.7, 0.22, len(media)) * saturation, 1.05, 4.2)
media["reach"] = (media.impressions / freq).round().astype(int)
media.to_csv(os.path.join(OUT, "media_daily.csv"), index=False)

# ---- M4 · cross-sell revenue ------------------------------------------------
# Brief: Revenue = income from ALL new products bought by campaign customers.
# Only booked customers can cross-sell, so this is anchored on the loan book.
booked = loans.copy()  # loans already carries segment_code
booked["month"] = booked.booked_ts.dt.to_period("M").dt.start_time
rows = []
for (month, seg), g in booked.dropna(subset=["month"]).groupby(["month", "segment_code"]):
    n = len(g)
    # ~38% of new borrowers take a second product; deposit/insurance/card mix
    takers = rng.binomial(n, 0.38)
    rows.append({
        "month": month.date(), "segment_code": seg,
        "customers_with_2nd_product": int(takers),
        "crosssell_revenue_thb": float(np.round(takers * rng.normal(4200, 900), -1)),
    })
pd.DataFrame(rows).to_csv(os.path.join(OUT, "crosssell_monthly.csv"), index=False)

# ---- M5 · control group -----------------------------------------------------
# A holdout of comparable people who were NOT served the campaign. Their
# baseline application/approval/disbursement behaviour is what "incremental"
# subtracts. Sized at control_group_pct of the lead population.
n_ctrl = int(len(leads) * 0.08)
seg_mix = leads.segment_code.value_counts(normalize=True)
ctrl_seg = rng.choice(seg_mix.index.to_numpy(), n_ctrl, p=seg_mix.to_numpy())
# organic baseline rates - materially lower than campaign-exposed, which is the point
applied = rng.random(n_ctrl) < 0.061
approved = applied & (rng.random(n_ctrl) < 0.52)
disbursed = approved & (rng.random(n_ctrl) < 0.63)
amt = np.where(disbursed, np.round(rng.lognormal(14.85, 0.42, n_ctrl), -3), 0.0)
pd.DataFrame({
    "control_id": [f"CTL{i:05d}" for i in range(n_ctrl)],
    "segment_code": ctrl_seg,
    "observed_week": rng.choice(sorted(leads.submitted_ts.dt.to_period("W-SUN")
                                       .dt.start_time.dt.date.unique()), n_ctrl),
    "applied": applied, "approved": approved, "disbursed": disbursed,
    "disbursed_amt_thb": amt,
}).to_csv(os.path.join(OUT, "control_group.csv"), index=False)

print(f"campaign.csv          1 row  target ฿450.0M")
print(f"media_daily.csv       +reach   frequency {freq.min():.2f}-{freq.max():.2f}")
print(f"crosssell_monthly.csv {len(rows)} rows")
print(f"control_group.csv     {n_ctrl} rows  disbursed {disbursed.sum()}  ฿{amt.sum()/1e6:.1f}M")

# ---- F1 support · a routing backlog -----------------------------------------
# The mock assigned every lead the instant it arrived, which made the corrected
# contact-rate denominator (assigned, not all) indistinguishable from the old
# one. Real routing lags: the brief's own SLA is "accept within 2 hours", so a
# tail of fresh arrivals is always still unassigned, plus a few that fell
# through. Without this the F1 fix is invisible in the demo.
leads_full = pd.read_csv(os.path.join(OUT, "leads.csv"), parse_dates=["submitted_ts", "assigned_ts"])
latest = leads_full.submitted_ts.max()
fresh = leads_full.submitted_ts > (latest - pd.Timedelta(days=3))     # not yet routed
dropped = rng.random(len(leads_full)) < 0.025                          # fell through routing
unassigned = fresh | dropped
leads_full.loc[unassigned, "assigned_ts"] = pd.NaT
leads_full.to_csv(os.path.join(OUT, "leads.csv"), index=False)
print(f"leads.csv             {int(unassigned.sum())} of {len(leads_full)} unassigned "
      f"({fresh.sum()} awaiting routing, {int((dropped & ~fresh).sum())} fell through)")

# ---- T1 · speak GSB's language ---------------------------------------------
# Swaps the invented English dimensions for GSB's own code lists, and adds the
# two bands the Overview cross-tab needs. Column NAMES are unchanged so the
# pages and kpi.py keep working; only the values change, plus three new columns.
#
# Deliberately NOT localised yet: lead_status and app_status. common.py derives
# the funnel stage from those exact strings, so swapping them is a wider change
# than tonight's three asks need. The Thai status list is in gsb_vocab as
# LEAD_STATUSES_TH and APP_STATUSES, ready for that pass.
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gsb_vocab as V  # noqa: E402

pros = pd.read_csv(os.path.join(OUT, "prospects.csv"))
lead2 = pd.read_csv(os.path.join(OUT, "leads.csv"))
apps2 = pd.read_csv(os.path.join(OUT, "applications.csv"))

# Real GSB branch hierarchy. The mock had six invented branches; GSB gave 68
# real ones under 26 districts and 5 regions, so leads now route somewhere real.
rng2 = np.random.default_rng(42)
n_br = min(len(V.BRANCHES), 24)                      # keep the queue readable
branch_pool = pd.DataFrame({
    "branch_name": V.BRANCHES[:n_br],
    "region": rng2.choice(V.REGIONS, n_br),
    "district": rng2.choice(V.DISTRICTS, n_br),
})
branch_pool["branch_id"] = [f"BR-{i:03d}" for i in range(1, n_br + 1)]
pick = rng2.integers(0, n_br, len(lead2))
for col in ["branch_id", "branch_name", "region", "district"]:
    lead2[col] = branch_pool[col].to_numpy()[pick]

# Age and income bands: the axes of the Overview cross-tab. Neither existed in
# the mock, and neither exists on droplead in the real feed either, so they are
# attached to the prospect, which is where lorapp carries them.
pros["age_band"] = rng2.choice(V.AGE_BANDS, len(pros))
pros["income_band"] = rng2.choice(V.INCOME_BANDS, len(pros))
pros["occupation"] = rng2.choice(V.OCCUPATIONS, len(pros))
pros["sub_occupation"] = rng2.choice(V.SUB_OCCUPATIONS, len(pros))

# MARKET_CODE_SETUP_DESC_TH is the closest thing GSB has to a campaign label.
apps2["market_project"] = rng2.choice(V.MARKET_PROJECTS, len(apps2))
apps2["product_th"] = V.LOAN_PRODUCTS[0]

pros.to_csv(os.path.join(OUT, "prospects.csv"), index=False)
lead2.to_csv(os.path.join(OUT, "leads.csv"), index=False)
apps2.to_csv(os.path.join(OUT, "applications.csv"), index=False)
branch_pool.to_csv(os.path.join(OUT, "branch_dim.csv"), index=False)

# ---- GA feeds, shaped exactly like the real export -------------------------
# Aggregate daily by landing page. No UTM, no session id, no channel: that is
# what GSB's GA extract actually contains (finding F2, data request DR2).
days = pd.date_range(CAMPAIGN_START, CAMPAIGN_END, freq="D")
page = V.LANDING_PAGES[0]
ga = pd.DataFrame({
    "Date": days,
    "Landing page": page,
    "Time on Page": np.round(rng2.normal(165, 38, len(days)), 0).clip(20, 400).astype(int),
    "Total users": rng2.poisson(48, len(days)) + 5,
})
ga.to_csv(os.path.join(OUT, "ga_landing.csv"), index=False)

rows = []
for _, r in ga.iterrows():
    reach = 1.0
    for th in sorted(V.SCROLL_THRESHOLDS, key=float):
        reach *= rng2.uniform(0.62, 0.88)            # each depth loses people
        rows.append({"Date": r["Date"], "Landing page": page,
                     "scroll_depth_threshold": th,
                     "Total users": int(r["Total users"] * reach)})
pd.DataFrame(rows).to_csv(os.path.join(OUT, "ga_scroll.csv"), index=False)

print(f"branch_dim.csv        {n_br} real GSB branches")
print(f"prospects.csv         +age_band +income_band +occupation +sub_occupation")
print(f"ga_landing.csv        {len(ga)} days · ga_scroll.csv {len(rows)} rows "
      f"(aggregate only, no UTM — DR2)")

# ---- T4 · a target lead list, the "targeted" half of the Overview cross-tab --
# Senior's task 2: the finalized lead list imported before the campaign runs.
# Deliberately drawn with a DIFFERENT age/income mix from the prospects who
# actually converted, because a targeted-vs-achieved grid that matches perfectly
# teaches nothing. The drift is the point.
tgt_n = 4200
age_w = np.array([0.04, 0.24, 0.30, 0.22, 0.13, 0.05, 0.02])
inc_w = np.array([0.03, 0.08, 0.20, 0.26, 0.21, 0.13, 0.09])
target = pd.DataFrame({
    "target_lead_id": [f"TL{i:06d}" for i in range(tgt_n)],
    "age_band": rng2.choice(V.AGE_BANDS, tgt_n, p=age_w / age_w.sum()),
    "income_band": rng2.choice(V.INCOME_BANDS, tgt_n, p=inc_w / inc_w.sum()),
    "occupation": rng2.choice(V.OCCUPATIONS, tgt_n),
    "region": rng2.choice(V.REGIONS, tgt_n),
    "product": V.LOAN_PRODUCTS[0],
    "campaign_id": "DCO2026",
    "imported_at": "2026-08-28 09:00:00",
    "imported_by": "marketing.gsb",
    "source_file": "GSB_final_lead_list_2026-08-28.xlsx",
})
target.to_csv(os.path.join(OUT, "target_leads.csv"), index=False)
print(f"target_leads.csv      {tgt_n} rows (the targeted grid)")
