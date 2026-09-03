# -*- coding: utf-8 -*-
"""Mock user-level event data for the DCO campaign dashboard.
Seeded and reproducible. Output: mock_data/*.csv
Identity chain per best-practice PDF: prospect_id -> lead_id -> application_id -> loan_account_id.
"""
import numpy as np, pandas as pd, os
rng = np.random.default_rng(42)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_data")
os.makedirs(OUT, exist_ok=True)

CAMPAIGN_START = pd.Timestamp("2026-09-01")
WEEKS = 10
SEGS = {
    "FHB": ("First-Home Urban Starters", "housing", 0.34),
    "FAM": ("Family Upgraders",          "housing", 0.18),
    "SAE": ("Smart Asset Entrepreneurs", "housing", 0.08),
    "OPT": ("The Optimizer",             "refinance", 0.26),
    "MRL": ("The Monthly Relief",        "refinance", 0.14),
}
CHANNELS = {"facebook": 0.45, "google": 0.30, "line": 0.15, "display": 0.10}
CREATIVES = {  # creative -> (segment targeted, label)
    "CR-A-ratecut":    "FHB", "CR-B-calculator": "FHB",
    "CR-C-familyhome": "FAM", "CR-D-bizasset":   "SAE",
    "CR-E-refi-save":  "OPT", "CR-F-payless":    "MRL",
    "CR-G-firsthome":  "FHB", "CR-H-refi-fast":  "OPT",
}
BRANCHES = [("BR-014","Ratchadaphisek"),("BR-022","Bang Khae"),("BR-052","Chiang Mai"),
            ("BR-031","Hat Yai"),("BR-044","Khon Kaen"),("BR-061","Rangsit")]
FORM_FIELDS = ["name","phone_number","id_card_no","income_occupation","property_value","consent_tickbox"]
DECLINE = ["dsr_too_high","bureau_history","income_doc","collateral_value","employment_tenure","other"]
LOST = ["cannot_contact","not_interested","not_qualified","duplicate_lead","cancelled"]

# per-segment funnel multipliers (quality differs by segment — this is what the scatter should show)
SEG_QUALITY = {"FHB":1.0,"FAM":1.25,"SAE":0.8,"OPT":1.15,"MRL":0.7}

seg_keys = list(SEGS); seg_p = np.array([SEGS[k][2] for k in seg_keys])
ch_keys = list(CHANNELS); ch_p = np.array(list(CHANNELS.values()))
cr_keys = list(CREATIVES)

# ---------- 1. media_daily (anonymous — impressions have no user) ----------
rows=[]
for d in pd.date_range(CAMPAIGN_START, periods=WEEKS*7):
    week = (d - CAMPAIGN_START).days // 7
    burst = 1.6 if week in (1,2,6,7) else 1.0          # two flights
    for cr in cr_keys:
        seg = CREATIVES[cr]
        ch = rng.choice(ch_keys, p=ch_p)
        imp = int(rng.gamma(6, 2200) * burst * SEGS[seg][2] * 3)
        ctr = np.clip(rng.normal(0.021, 0.005), 0.004, 0.06)
        clicks = rng.binomial(imp, ctr)
        cpm = rng.normal(96, 14)
        rows.append([d.date(), "DCO2026", f"AS-{seg}", cr, seg, ch, imp, clicks, round(imp/1000*cpm,2)])
media = pd.DataFrame(rows, columns=["date","campaign_id","ad_set_id","creative_id","segment_code","channel","impressions","clicks","spend_thb"])

# ---------- 2. prospects (people) ----------
n_sessions = int(media["clicks"].sum() * 0.72)          # click -> landing page view rate
n_prospects = int(n_sessions * 0.85)                    # some people visit twice
ages = {"FHB":(25,35),"FAM":(35,50),"SAE":(35,50),"OPT":(30,50),"MRL":(30,50)}
occ = ["employee","civil_servant","business_owner","professional","freelance"]
pseg = rng.choice(seg_keys, n_prospects, p=seg_p)
prospects = pd.DataFrame({
    "prospect_id": [f"P{100000+i}" for i in range(n_prospects)],
    "segment_code": pseg,
    "segment": [SEGS[s][0] for s in pseg],
    "product": [SEGS[s][1] for s in pseg],
    "age": [rng.integers(*ages[s]) for s in pseg],
    "occupation": rng.choice(occ, n_prospects),
    "monthly_income_thb": np.round(rng.lognormal(10.9, 0.5, n_prospects), -2),
    "province": rng.choice(["Bangkok","Nonthaburi","Pathum Thani","Chiang Mai","Songkhla","Khon Kaen"],
                           n_prospects, p=[.42,.14,.12,.12,.10,.10]),
    "customer_id": [f"CIF{700000+i}" if rng.random()<0.31 else "" for i in range(n_prospects)],  # 31% existing customers
})

# ---------- 3. web_sessions (user-level GA) ----------
sess_prospect = rng.integers(0, n_prospects, n_sessions)
scr = rng.random(n_sessions)
sessions = pd.DataFrame({
    "session_id": [f"S{i:07d}" for i in range(n_sessions)],
    "prospect_id": prospects["prospect_id"].values[sess_prospect],
    "ts": [CAMPAIGN_START + pd.Timedelta(days=float(rng.integers(0,WEEKS*7)), hours=float(rng.integers(7,23)), minutes=float(rng.integers(0,60))) for _ in range(n_sessions)],
    "creative_id": rng.choice(cr_keys, n_sessions),
    "channel": rng.choice(ch_keys, n_sessions, p=ch_p),
    "utm_campaign": np.where(rng.random(n_sessions)<0.95, "DCO2026", ""),   # 5% missing UTM
    "time_on_lp_sec": np.round(rng.lognormal(4.1, 0.9, n_sessions),1),
    "max_scroll_pct": np.select([scr<.28,scr<.55,scr<.78,scr<.92],[10,25,50,75],100),
})
sessions["form_start"] = (sessions["max_scroll_pct"]>=75) & (rng.random(n_sessions)<0.24)
sessions["form_complete"] = sessions["form_start"] & (rng.random(n_sessions)<0.58)
starts = sessions["form_start"] & ~sessions["form_complete"]
sessions["abandon_field"] = ""
sessions.loc[starts,"abandon_field"] = rng.choice(FORM_FIELDS, int(starts.sum()), p=[.06,.22,.18,.28,.16,.10])

# ---------- 4. leads (one per completing session; ~4% duplicates) ----------
lead_src = sessions[sessions["form_complete"]].reset_index(drop=True)
n_leads = len(lead_src)
lp = prospects.set_index("prospect_id").loc[lead_src["prospect_id"]].reset_index()
qual = np.array([rng.random() < np.clip(0.58*SEG_QUALITY[s],0,.95) for s in lp["segment_code"]])
dup = rng.random(n_leads) < 0.04
br = rng.integers(0, len(BRANCHES), n_leads)
assigned_lag = rng.gamma(1.5, 1.4, n_leads)             # hours
contact_ok = qual & ~dup & (rng.random(n_leads) < 0.78)
contact_lag = rng.gamma(2.0, 14, n_leads)               # hours, median ~ 24
docs = contact_ok & (rng.random(n_leads) < 0.42)
docs_lag = rng.gamma(2.0, 60, n_leads)                  # hours after contact
leads = pd.DataFrame({
    "lead_id": [f"L{200000+i}" for i in range(n_leads)],
    "prospect_id": lead_src["prospect_id"],
    "session_id": lead_src["session_id"],
    "customer_id": lp["customer_id"],
    "segment_code": lp["segment_code"], "segment": lp["segment"], "product": lp["product"],
    "creative_id": lead_src["creative_id"], "channel": lead_src["channel"],
    "utm_campaign": lead_src["utm_campaign"],
    "submitted_ts": lead_src["ts"],
    "branch_id": [BRANCHES[i][0] for i in br], "branch_name": [BRANCHES[i][1] for i in br],
    "assigned_ts": lead_src["ts"] + pd.to_timedelta(assigned_lag, "h"),
    "qualified_flag": qual, "duplicate_flag": dup,
    "contact_attempts": np.where(contact_ok, rng.integers(1,4,n_leads), rng.integers(1,6,n_leads)),
    "contacted_ts": np.where(contact_ok, lead_src["ts"] + pd.to_timedelta(assigned_lag+contact_lag,"h"), pd.NaT),
    "docs_submitted_ts": np.where(docs, lead_src["ts"] + pd.to_timedelta(assigned_lag+contact_lag+docs_lag,"h"), pd.NaT),
})
leads["contacted_ts"]=pd.to_datetime(leads["contacted_ts"]); leads["docs_submitted_ts"]=pd.to_datetime(leads["docs_submitted_ts"])
status = np.where(dup,"Duplicate Lead",
         np.where(~qual,"Not Qualified",
         np.where(~contact_ok,"Cannot Contact",
         np.where(docs,"Document Pending","Contacted"))))
leads["lead_status"]=status
leads["lost_reason"]=np.where(np.isin(status,["Duplicate Lead","Not Qualified","Cannot Contact"]),
                              np.char.lower(np.char.replace(status.astype(str)," ","_")),"")

# ---------- 5. applications ----------
app_src = leads[leads["docs_submitted_ts"].notna()].reset_index(drop=True)
apply_flag = rng.random(len(app_src)) < 0.80
apps_src = app_src[apply_flag].reset_index(drop=True)
n_apps = len(apps_src)
req = np.round(np.clip(rng.lognormal(14.85, 0.45, n_apps), 8e5, 1.3e7), -4)   # ~2.8M median
app_lag = rng.gamma(2.0, 30, n_apps)      # hours after docs
dec_lag = rng.gamma(3.0, 3.2, n_apps)     # days to decision
approved = rng.random(n_apps) < np.clip([0.62*SEG_QUALITY[s] for s in apps_src["segment_code"]],0,.9)
appr_amt = np.round(req * np.clip(rng.normal(0.92,0.08,n_apps),0.6,1.0), -4)
applications = pd.DataFrame({
    "application_id":[f"A{300000+i}" for i in range(n_apps)],
    "lead_id": apps_src["lead_id"], "prospect_id": apps_src["prospect_id"],
    "product": apps_src["product"], "segment_code": apps_src["segment_code"],
    "submitted_ts": apps_src["docs_submitted_ts"] + pd.to_timedelta(app_lag,"h"),
    "requested_amt_thb": req,
    "decision_ts": apps_src["docs_submitted_ts"] + pd.to_timedelta(app_lag,"h") + pd.to_timedelta(dec_lag,"D"),
    "app_status": np.where(approved,"Approved","Rejected"),
    "approved_amt_thb": np.where(approved, appr_amt, 0.0),
    "decline_reason": np.where(approved,"",rng.choice(DECLINE,n_apps,p=[.30,.24,.17,.12,.09,.08])),
})

# ---------- 6. loans ----------
appr = applications[applications["app_status"]=="Approved"].reset_index(drop=True)
booked = rng.random(len(appr)) < 0.78
loans_src = appr[booked].reset_index(drop=True)
book_lag = rng.gamma(2.5, 4, len(loans_src))    # days
disb = rng.random(len(loans_src)) < 0.85
disb_lag = rng.gamma(2.0, 5, len(loans_src))    # days after booking
loans = pd.DataFrame({
    "loan_account_id":[f"LN{400000+i}" for i in range(len(loans_src))],
    "application_id": loans_src["application_id"], "prospect_id": loans_src["prospect_id"],
    "product": loans_src["product"], "segment_code": loans_src["segment_code"],
    "booked_ts": loans_src["decision_ts"] + pd.to_timedelta(book_lag,"D"),
    "booked_amt_thb": loans_src["approved_amt_thb"],
    "disbursed_ts": np.where(disb, loans_src["decision_ts"] + pd.to_timedelta(book_lag+disb_lag,"D"), pd.NaT),
    "disbursed_amt_thb": np.where(disb, np.round(loans_src["approved_amt_thb"]*np.clip(rng.normal(.96,.05,len(loans_src)),.5,1.0),-4), 0.0),
    "interest_rate_pct": np.round(rng.normal(3.4,0.35,len(loans_src)),2),
})
loans["disbursed_ts"]=pd.to_datetime(loans["disbursed_ts"])

# censor events beyond the observation window (maturity is real, not simulated away)
CUTOFF = CAMPAIGN_START + pd.Timedelta(days=WEEKS*7)
for df,cols in [(leads,["contacted_ts","docs_submitted_ts"]),(applications,["submitted_ts","decision_ts"]),(loans,["booked_ts","disbursed_ts"])]:
    for c in cols:
        late = df[c] > CUTOFF
        df.loc[late, c] = pd.NaT
applications.loc[applications["decision_ts"].isna(),["app_status","approved_amt_thb","decline_reason"]] = ["Submitted",0.0,""]
loans.loc[loans["booked_ts"].isna(),["booked_amt_thb"]] = 0.0
loans.loc[loans["disbursed_ts"].isna(),["disbursed_amt_thb"]] = 0.0
loans = loans[loans["booked_ts"].notna() | (loans["disbursed_amt_thb"]>0)]

# late CIF binding: a new-to-bank customer has no CIF until GSB onboarding creates one
# at booking. Existing customers were linked pre-campaign.
prospects["cif_linked_at"] = np.where(prospects.customer_id.ne(""), str(CAMPAIGN_START.date()), "")
prospects["is_new_to_bank"] = prospects.customer_id.eq("")
booked = loans[loans.booked_ts.notna()][["prospect_id", "booked_ts"]].dropna()
first_book = booked.groupby("prospect_id").booked_ts.min()
newly = prospects.prospect_id.isin(first_book.index) & prospects.customer_id.eq("")
prospects.loc[newly, "customer_id"] = ["CIF9" + pid[1:] for pid in prospects.loc[newly, "prospect_id"]]
prospects.loc[newly, "cif_linked_at"] = prospects.loc[newly, "prospect_id"].map(
    first_book.dt.date.astype(str))

# ~7% of leads lose their prospect link (unmatched — feeds data-quality)
unmatched = rng.random(len(leads)) < 0.07
leads.loc[unmatched, "prospect_id"] = ""

for name,df in [("media_daily",media),("prospects",prospects),("web_sessions",sessions),
                ("leads",leads),("applications",applications),("loans",loans)]:
    df.to_csv(os.path.join(OUT,f"{name}.csv"), index=False)
    print(f"{name:14s} {len(df):>8,} rows  {len(df.columns)} cols")


# ---------- 7. lead_event (append-only history, derived from the same lifecycle) ----------
STAFF = {bid: [f"U-{bid[3:]}-{k:02d}" for k in range(1, rng.integers(3,6))] for bid,_ in BRANCHES}
ev_rows=[]
def ev(lead_id, etype, old, new, reason, who, role, ts, channel="", note=""):
    ev_rows.append([lead_id, etype, old, new, reason, who, role, ts, channel, note])

app_by_lead = applications.set_index("lead_id")
loan_by_app = loans.set_index("application_id")
for L in leads.itertuples():
    staff = STAFF[L.branch_id][int(rng.integers(0,len(STAFF[L.branch_id])))]
    mgr = f"U-{L.branch_id[3:]}-MGR"
    ev(L.lead_id,"status_change","","New","","system","system",L.submitted_ts)
    ev(L.lead_id,"assignment","",staff,"",mgr,"branch_manager",L.assigned_ts,note="round-robin")
    ev(L.lead_id,"status_change","New","Assigned","",mgr,"branch_manager",L.assigned_ts)
    if L.duplicate_flag:
        ev(L.lead_id,"status_change","Assigned","Duplicate Lead","duplicate_lead",staff,"branch_staff",
           L.assigned_ts + pd.Timedelta(hours=float(rng.gamma(1.5,4)))); continue
    if not L.qualified_flag:
        ev(L.lead_id,"status_change","Assigned","Not Qualified","not_qualified",staff,"branch_staff",
           L.assigned_ts + pd.Timedelta(hours=float(rng.gamma(1.5,6)))); continue
    n_att = int(L.contact_attempts)
    contacted = pd.notna(L.contacted_ts)
    last_att = L.assigned_ts
    attempted = False
    for k in range(n_att - (1 if contacted else 0)):
        t = last_att + pd.Timedelta(hours=float(rng.gamma(2,9)))
        if contacted and t >= L.contacted_ts: break
        last_att = t
        ev(L.lead_id,"contact_attempt","","no_answer","",staff,"branch_staff",last_att,
           channel=str(rng.choice(["phone","line","phone","email"])))
        if not attempted:
            ev(L.lead_id,"status_change","Assigned","Contact Attempted","",staff,"branch_staff",last_att)
            attempted = True
    if not contacted:
        if not attempted:
            last_att = last_att + pd.Timedelta(hours=float(rng.gamma(2,9)))
            ev(L.lead_id,"contact_attempt","","no_answer","",staff,"branch_staff",last_att,channel="phone")
            ev(L.lead_id,"status_change","Assigned","Contact Attempted","",staff,"branch_staff",last_att)
            attempted = True
        ev(L.lead_id,"status_change","Contact Attempted","Cannot Contact","cannot_contact",staff,"branch_staff",
           last_att + pd.Timedelta(hours=float(rng.gamma(2,10)))); continue
    prev = "Contact Attempted" if attempted else "Assigned"
    ev(L.lead_id,"contact_attempt","","reached","",staff,"branch_staff",L.contacted_ts,channel="phone")
    ev(L.lead_id,"status_change",prev,"Contacted","",staff,"branch_staff",L.contacted_ts)
    if pd.isna(L.docs_submitted_ts): continue
    ev(L.lead_id,"status_change","Contacted","Document Pending","",staff,"branch_staff",L.docs_submitted_ts)
    if L.lead_id not in app_by_lead.index: continue
    A = app_by_lead.loc[L.lead_id]
    if pd.isna(A["submitted_ts"]): continue
    ev(L.lead_id,"status_change","Document Pending","Application Submitted","","system","system",A["submitted_ts"])
    if A["app_status"]=="Rejected":
        ev(L.lead_id,"status_change","Application Submitted","Application Rejected",A["decline_reason"],
           "system","system",A["decision_ts"]); continue
    if A["app_status"]!="Approved" or pd.isna(A["decision_ts"]): continue
    ev(L.lead_id,"status_change","Application Submitted","Approved","","system","system",A["decision_ts"])
    aid = A["application_id"]
    if aid in loan_by_app.index:
        LN = loan_by_app.loc[aid]
        if pd.notna(LN["booked_ts"]):
            ev(L.lead_id,"status_change","Approved","Booked","","system","system",LN["booked_ts"])
            if pd.notna(LN["disbursed_ts"]):
                ev(L.lead_id,"status_change","Booked","Disbursed","","system","system",LN["disbursed_ts"])

lead_events = pd.DataFrame(ev_rows, columns=["lead_id","event_type","old_value","new_value",
    "reason_code","changed_by","changed_role","changed_at","channel","note"])
lead_events = lead_events.sort_values(["lead_id","changed_at"]).reset_index(drop=True)
lead_events.insert(0,"event_id",[f"E{500000+i}" for i in range(len(lead_events))])
lead_events = lead_events[lead_events["changed_at"] <= CUTOFF]
lead_events.to_csv(os.path.join(OUT,"lead_events.csv"), index=False)
print(f"{'lead_events':14s} {len(lead_events):>8,} rows  {len(lead_events.columns)} cols")

# funnel sanity check
print("\n--- funnel ---")
print(f"impressions      {media['impressions'].sum():>12,}")
print(f"clicks           {media['clicks'].sum():>12,}   CTR {media['clicks'].sum()/media['impressions'].sum():.2%}")
print(f"lp sessions      {len(sessions):>12,}")
print(f"form starts      {int(sessions['form_start'].sum()):>12,}")
print(f"leads            {len(leads):>12,}")
print(f"qualified        {int(leads['qualified_flag'].sum()):>12,}")
print(f"docs submitted   {int(leads['docs_submitted_ts'].notna().sum()):>12,}")
print(f"applications     {len(applications):>12,}")
print(f"approved         {int((applications['app_status']=='Approved').sum()):>12,}")
print(f"booked           {int(loans['booked_ts'].notna().sum()):>12,}")
print(f"disbursed        {int((loans['disbursed_amt_thb']>0).sum()):>12,}")
print(f"disbursed >=3M   {int(((loans['disbursed_amt_thb']>=3e6)).sum()):>12,}")
print(f"spend THB        {media['spend_thb'].sum():>12,.0f}")
assert (applications["approved_amt_thb"]>=0).all() and len(leads)>0
