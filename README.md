# DCO Campaign Dashboard — demo

Design-review build of the GSB DCO housing-loan campaign dashboard.
**Synthetic data only** (generated, seed 42). No real customer records.

## Run locally
```bash
pip install -r requirements.txt
streamlit run streamlit_app/streamlit_app.py
```

## Two seats
The app has exactly two roles, and they differ on one axis: write access.

| | Admin | Campaign owner |
|---|---|---|
| Reads | everything, unmasked | every KPI page, contact fields masked |
| Writes | the only human write path | nothing |
| Lands on | Worklist (a queue) | Overview (a number) |

Default landing is the campaign owner. Append `?seat=admin` for the admin seat,
or use the seat picker in the sidebar.

## What to look at first
- `streamlit_app/kpi.py` — the KPI dictionary as executable code. 40 KPIs, each
  carrying numerator, denominator, exclusions, source, maturity gate and
  version. Pages call these functions; no page computes a rate inline. The
  in-app **KPI dictionary** page renders from the same registry, so the
  documentation cannot drift from the arithmetic.
- **Three corrected denominators (v1.1).** The build previously disagreed with
  the written spec on all three:

  | KPI | Correct | Was |
  |---|---|---|
  | Approval rate | / submitted applications | / decided only |
  | Application rate | / qualified leads | / all leads |
  | Contact rate | / assigned leads | / all leads |

  Approval rate reads 55.2% correctly vs 64.4% the old way. Both readings are
  shown on the Loan funnel page, because the old number was already presented.
- `streamlit_app/test_smoke.py` — asserts every page renders for both seats,
  the admin gate holds, and each corrected denominator stays corrected.

## Known demo limits
- Writes go to CSV on an ephemeral filesystem: keyed status changes reset when
  the container sleeps.
- Cross-sell revenue, reach, the control group and the campaign target are
  mocked feeds — production needs real sources for each.
- The change log and the data-health acknowledgement are display-only.
