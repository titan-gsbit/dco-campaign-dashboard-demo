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
