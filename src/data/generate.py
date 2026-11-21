"""Generate the synthetic Arkterus Bank source files (rules in DATA_DESIGN.md).

Reads the authored synthetic customer profile and public price CSVs from the seed
volume, and writes the source-system files (ecif, crm, macro) to the raw volume,
plus generator ground truth to the seed volume. Deterministic for a given --seed.

Run as a serverless Python file task, or locally with --seed_dir/--raw_dir paths.
"""
import argparse
import json
import shutil
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

AS_OF = pd.Timestamp("2026-11-01")          # extract date
WINDOW = pd.period_range("2024-11", "2026-10", freq="M")   # 24 campaign months
BAL_MONTHS = pd.period_range("2024-05", "2026-10", freq="M")  # 6 months before the window onward

TIERS = {  # min score, min income, min 6-month average deposit
    "Silver": (650, 40_000, 1_000),
    "Gold": (700, 50_000, 2_500),
    "Platinum": (750, 125_000, 5_000),
    "Cashback": (650, 50_000, 0),
}
RANK = {"Silver": 0, "Cashback": 1, "Gold": 2, "Platinum": 3}
OFFERS = {  # offer_code: (card, description, campaign_code)
    "SIL_BT6": ("Silver", "0% balance transfer for 6 months", "CMP-SIL-BT6"),
    "GLD_GROC5": ("Gold", "5% cashback on groceries for 12 months", "CMP-GLD-GROC5"),
    "PLT_BT12": ("Platinum", "0% balance transfer for 12 months", "CMP-PLT-BT12"),
    "PLT_TE5": ("Platinum", "5% cashback on travel and entertainment", "CMP-PLT-TE5"),
    "CB_ALL3": ("Cashback", "3% cashback on all purchases for 6 months", "CMP-CB-ALL3"),
}
MARKET = {
    "Raleigh": "urban_core", "Durham": "urban_core", "Charlotte": "urban_core", "Columbia": "urban_core",
    "Wilmington": "urban_core", "Charleston": "urban_core",
    "Cary": "suburban", "Apex": "suburban", "Holly Springs": "suburban", "Chapel Hill": "suburban",
    "Greensboro": "suburban_style_metro", "Winston-Salem": "suburban_style_metro",
    "Mebane": "exurban", "Burlington": "exurban", "Salisbury": "exurban",
    "Greenville": "fast_growing_mid_size", "Florence": "highway_corridor",
    "Myrtle Beach": "coastal_resort", "Hilton Head Island": "coastal_resort", "Pawleys Island": "coastal_resort",
    "Asheville": "mountain_tourism",
}
LOW_COST = {"Columbia", "Greensboro", "Winston-Salem", "Mebane", "Burlington", "Salisbury", "Greenville", "Florence"}
METRO = {  # city -> FHFA metro area name in fhfa_hpi_metros.csv
    "Raleigh": "Raleigh-Cary", "Cary": "Raleigh-Cary", "Apex": "Raleigh-Cary", "Holly Springs": "Raleigh-Cary",
    "Durham": "Durham-Chapel Hill", "Chapel Hill": "Durham-Chapel Hill", "Mebane": "Burlington",
    "Charlotte": "Charlotte-Concord-Gastonia", "Salisbury": "Charlotte-Concord-Gastonia",
    "Greensboro": "Greensboro-High Point", "Winston-Salem": "Winston-Salem", "Burlington": "Burlington",
    "Wilmington": "Wilmington", "Charleston": "Charleston-North Charleston", "Columbia": "Columbia",
    "Greenville": "Greenville-Anderson", "Myrtle Beach": "Myrtle Beach-Conway-North Myrtle Beach",
    "Pawleys Island": "Myrtle Beach-Conway-North Myrtle Beach", "Asheville": "Asheville", "Florence": "Florence",
    "Hilton Head Island": "Hilton Head Island-Bluffton-Port Royal",
}
PLAT_BT_CITIES = ["Cary", "Raleigh", "Charlotte", "Greenville", "Durham", "Wilmington", "Charleston"]
GOLD_CITIES = ["Apex", "Holly Springs", "Greensboro", "Winston-Salem"]
SILVER_CITIES = ["Charleston", "Wilmington", "Myrtle Beach"]
CUSTOMER_COLS = ["customer_id", "date_of_birth", "city", "state", "zip_code", "country", "gender", "marital_status",
                 "employment_status", "own_rent_home", "residency_duration_yrs", "residence_year", "annual_income",
                 "monthly_household_pmt", "credit_score", "customer_since", "preferred_channel", "consent_email",
                 "consent_sms", "consent_push", "source_system", "is_residency_imputed"]


def generation(dob):
    """Generation by age at AS_OF, using the source table's bands: 18-28, 29-45, 46-58, 59-68, 69+."""
    age = ((AS_OF - pd.to_datetime(dob)).dt.days // 365).values
    return np.select([age <= 28, age <= 45, age <= 58, age <= 68], ["gen_z", "millennial", "gen_x", "boomer"], "silent")


def new_ids(rng, n):
    return [str(uuid.UUID(bytes=rng.bytes(16), version=4)) for _ in range(n)]


def added(rng, n, group, city, state, zips, age, income, score, marital, own, pmt, residence, employment=None):
    """Build n added synthetic customers. Range args are (low, high); categorical args are (values, probs)."""
    ages = rng.integers(age[0], age[1] + 1, n)
    dob = [AS_OF - pd.DateOffset(years=int(a)) - pd.Timedelta(days=int(d)) for a, d in zip(ages, rng.integers(0, 365, n))]
    res = rng.integers(residence[0], residence[1] + 1, n)
    emp_vals, emp_probs = employment or (["employed", "self_employed"], [0.8, 0.2])
    df = pd.DataFrame({
        "customer_id": new_ids(rng, n),
        "date_of_birth": pd.to_datetime(dob).date,
        "city": city,
        "state": state,
        "zip_code": rng.choice(zips, n),
        "country": "USA",
        "gender": rng.choice(["M", "F"], n, p=[0.52, 0.48]),
        "marital_status": rng.choice(marital[0], n, p=marital[1]),
        "employment_status": rng.choice(emp_vals, n, p=emp_probs),
        "own_rent_home": rng.choice(own[0], n, p=own[1]),
        "residence_year": res,
        "annual_income": rng.integers(income[0], income[1] + 1, n),
        "monthly_household_pmt": np.round(pmt(n, res) if callable(pmt) else rng.uniform(pmt[0], pmt[1], n), 2),
        "credit_score": rng.integers(score[0], score[1] + 1, n),
        "preferred_channel": rng.choice(["mobile", "online", "branch", "phone"], n, p=[0.48, 0.30, 0.18, 0.04]),
        "consent_email": rng.random(n) < 0.8, "consent_sms": rng.random(n) < 0.6, "consent_push": rng.random(n) < 0.7,
        "source_system": "ecif", "is_residency_imputed": False,
    })
    df["residency_duration_yrs"] = 2025 - df["residence_year"]
    since = rng.integers(pd.Timestamp("2008-01-01").value // 86_400_000_000_000, pd.Timestamp("2024-04-30").value // 86_400_000_000_000, n)
    df["customer_since"] = pd.to_datetime(since, unit="D").date
    df["record_origin"], df["origin_group"] = "added_synthetic", group
    return df


def load_prices(seed_dir):
    bls = pd.read_csv(seed_dir / "public" / "bls_cpi_south.csv", parse_dates=["month"])
    hpi = pd.read_csv(seed_dir / "public" / "fhfa_hpi_metros.csv", parse_dates=["month"])
    cpi = bls.pivot_table(index="month", columns="series", values="value").sort_index()
    cpi = cpi.reindex(pd.date_range(cpi.index.min(), cpi.index.max(), freq="MS")).interpolate()  # Oct 2025 not published
    # cost-of-living pressure: trailing 3-month % change of food at home and gasoline, known with a one-month lag
    chg = (cpi[["food_at_home", "gasoline"]].pct_change(3)).mean(axis=1).shift(1)
    w = chg.loc[str(WINDOW[0]): str(WINDOW[-1])]
    z = ((w - w.mean()) / w.std()).clip(-2.5, 2.5)
    macro_z = {pd.Period(m, "M"): v for m, v in z.items()}
    g = hpi.pivot_table(index="month", columns="area", values="value").sort_index()
    growth = g.loc["2025-10-01"] / g.loc["2021-01-01"] - 1
    return macro_z, growth


def main(a):
    rng = np.random.default_rng(a.seed)
    seed_dir, raw_dir, truth_dir = Path(a.seed_dir), Path(a.raw_dir), Path(a.seed_dir) / "ground_truth"
    src = pd.read_csv(seed_dir / "source" / "customer_profile.csv", dtype={"zip_code": str})
    src["record_origin"], src["origin_group"] = "source", "source"
    zips = src.groupby("city")["zip_code"].agg(lambda s: sorted(set(s))).to_dict()
    summary = {"source_customers": len(src)}

    # Adjusted: Winston-Salem married homeowners 30-50, $50k-$125k, score <= 700 -> 45% raised (DATA_DESIGN 1)
    m = ((src.city == "Winston-salem") & (src.marital_status == "married") & (src.own_rent_home == "own")
         & src.age.between(30, 50) & src.annual_income.between(50_000, 125_000) & (src.credit_score <= 700))
    pick = src[m].sample(frac=0.45, random_state=a.seed).index
    src.loc[pick, "credit_score"] = rng.integers(701, 761, len(pick))
    yr = src.loc[pick, "residence_year"].clip(2016, 2025)
    src.loc[pick, "monthly_household_pmt"] = np.round(1000 + (yr - 2016) / 9 * 400 + rng.uniform(0, 100, len(pick)), 2)
    src.loc[pick, ["record_origin", "origin_group"]] = ["adjusted", "ws_gold_uplift"]
    summary["adjusted_winston_salem"] = int(len(pick))

    # Added customers (DATA_DESIGN 1)
    mill_genx = (30, 58)
    gso_med = {2021: 1250, 2022: 1588, 2023: 1996, 2024: 2035, 2025: 2185}
    def gso_pmt(n, res):
        return np.array([gso_med[int(r)] for r in res]) * rng.uniform(0.8, 1.2, n)
    groups = []
    for city, n in (("Raleigh", 650), ("Charlotte", 1020), ("Durham", 489)):
        groups.append(added(rng, n, "platinum_bt", city, "NC", zips[city], mill_genx, (125_000, 300_000), (750, 850),
                            (["married", "single", "divorced"], [0.55, 0.35, 0.10]), (["own", "rent"], [0.6, 0.4]),
                            (1450, 3500), (2015, 2025)))
    n_fit = 300
    groups.append(added(rng, n_fit, "greensboro_homeowner_gold_fit", "Greensboro", "NC", zips["Greensboro"], (30, 50),
                        (50_000, 125_000), (700, 800), (["married"], [1.0]), (["own"], [1.0]), gso_pmt, (2021, 2025)))
    groups.append(added(rng, 1000 - n_fit, "greensboro_homeowner_mixed", "Greensboro", "NC", zips["Greensboro"], (25, 80),
                        (35_000, 160_000), (600, 820), (["married", "single", "divorced", "widowed"], [0.45, 0.3, 0.15, 0.1]),
                        (["own"], [1.0]), gso_pmt, (2021, 2025),
                        employment=(["employed", "self_employed", "retired"], [0.7, 0.15, 0.15])))
    for city, n in (("Apex", 700), ("Holly Springs", 600)):
        groups.append(added(rng, n, "gold_suburb", city, "NC", zips[city], (30, 50), (75_000, 125_000), (700, 800),
                            (["married"], [1.0]), (["own"], [1.0]), (1050, 2200), (2016, 2025)))
    hp_zip = {"27609": ("Raleigh", "NC"), "28211": ("Charlotte", "NC"), "28207": ("Charlotte", "NC"),
              "28405": ("Wilmington", "NC"), "28411": ("Wilmington", "NC"), "29401": ("Charleston", "SC"), "29407": ("Charleston", "SC")}
    hz = rng.choice(list(hp_zip), 300)
    for z in sorted(set(hz)):
        k = int((hz == z).sum())
        g = added(rng, k, "high_payer", hp_zip[z][0], hp_zip[z][1], [z], (30, 70), (250_000, 600_000), (720, 850),
                  (["married", "single", "divorced"], [0.7, 0.2, 0.1]), (["own", "rent"], [0.85, 0.15]), (7000, 15000), (2021, 2025))
        groups.append(g)
    add = pd.concat(groups, ignore_index=True)
    summary["added_customers"] = add.groupby("origin_group").size().to_dict()
    cust = pd.concat([src[CUSTOMER_COLS + ["record_origin", "origin_group"]], add[CUSTOMER_COLS + ["record_origin", "origin_group"]]], ignore_index=True)
    cust["date_of_birth"] = pd.to_datetime(cust["date_of_birth"])
    cust["customer_since"] = pd.to_datetime(cust["customer_since"])
    cust["city_clean"] = cust["city"].replace({"Winston-salem": "Winston-Salem"})
    cust["generation"] = generation(cust["date_of_birth"])
    cust["address_token"] = ["ADDR-" + h[:10].upper() for h in (uuid.uuid5(uuid.NAMESPACE_OID, c).hex for c in cust.customer_id)]
    cust["ssn_last4_token"] = rng.integers(0, 10_000, len(cust)).astype(str)
    cust["ssn_last4_token"] = cust["ssn_last4_token"].str.zfill(4)
    summary["total_customers"] = len(cust)

    # Accounts by generation (checking only / + savings / + savings + money market)
    mix = {"gen_z": [.90, .08, .02], "millennial": [.86, .10, .04], "gen_x": [.68, .25, .07], "boomer": [.58, .33, .09], "silent": [.48, .40, .12]}
    k = np.array([rng.choice(3, p=mix[g]) for g in cust.generation])
    cust["has_savings"], cust["has_mm"] = k >= 1, k >= 2
    cust["n_accounts"] = 1 + k
    acc = []
    for prod, flag in (("checking", np.ones(len(cust), bool)), ("savings", cust.has_savings.values), ("money_market", cust.has_mm.values)):
        c = cust[flag]
        opened = c.customer_since + pd.to_timedelta(rng.integers(0, 900, len(c)) * (prod != "checking"), unit="D")
        opened = opened.where(opened < pd.Timestamp("2024-04-30"), pd.Timestamp("2024-04-30"))
        acc.append(pd.DataFrame({"account_id": [f"{prod[:2].upper()}-{i}" for i in new_ids(rng, len(c))], "customer_id": c.customer_id.values,
                                 "product": prod, "open_date": opened.dt.date.values, "status": "open"}))
    accounts = pd.concat(acc, ignore_index=True)

    # Monthly balances (DATA_DESIGN 3)
    inc = cust.annual_income.clip(lower=0).astype(float)
    emp = cust.employment_status
    family = (emp == "student") | (inc < 10_000)
    monthly_in = np.where(family, cust.monthly_household_pmt.clip(lower=400) + rng.uniform(200, 500, len(cust)), inc / 12 * 0.75)
    monthly_in = np.where(emp == "unemployed", np.maximum(monthly_in * 0.4, 600), monthly_in)
    age_now = (AS_OF - cust.date_of_birth).dt.days // 365
    dep_type = np.select([family, emp == "retired", emp == "unemployed", emp == "self_employed"],
                         ["family_support", np.where(age_now >= 73, "social_security_pension_rmd", "social_security_pension"),
                          "unemployment_benefits", "self_employment"], "payroll")
    boost = cust.generation.map({"gen_z": 1.0, "millennial": 1.4, "gen_x": 2.2, "boomer": 3.5, "silent": 4.5}).values
    chk0 = monthly_in * rng.uniform(0.4, 1.2, len(cust))
    sav0 = np.where(cust.has_savings, inc / 12 * rng.uniform(1, 4, len(cust)) * boost, 0.0)
    mm0 = np.where(cust.has_mm, inc / 12 * rng.uniform(3, 8, len(cust)) * boost, 0.0)
    floor = cust.origin_group.map({"platinum_bt": 5500, "high_payer": 20000, "gold_suburb": 2700, "greensboro_homeowner_gold_fit": 2700}).fillna(0).values
    scale = np.where((chk0 + sav0 + mm0) < floor, floor / np.maximum(chk0 + sav0 + mm0, 1) * rng.uniform(1.05, 1.6, len(cust)), 1.0)
    chk0, sav0, mm0 = chk0 * scale, sav0 * scale, mm0 * scale
    bal_rows, avg6 = [], {}
    tot_hist = np.zeros((len(BAL_MONTHS), len(cust)))
    for i, p in enumerate(BAL_MONTHS):
        season = 1 + 0.08 * np.sin(2 * np.pi * (p.month - 3) / 12)
        chk = np.maximum(chk0 * season * rng.normal(1, 0.12, len(cust)), 5)
        sav = sav0 * (1 + 0.003 * i) * rng.normal(1, 0.03, len(cust))
        mm = mm0 * (1 + 0.004 * i) * rng.normal(1, 0.02, len(cust))
        tot_hist[i] = chk + sav + mm
        bal_rows.append(pd.DataFrame({"customer_id": cust.customer_id, "month_end": p.end_time.date(),
                                      "checking_balance": chk.round(2), "savings_balance": np.round(sav, 2), "money_market_balance": np.round(mm, 2),
                                      "monthly_deposits": np.round(monthly_in * rng.normal(1, 0.05, len(cust)), 2), "primary_deposit_type": dep_type}))

    # Solicitations: one per customer (DATA_DESIGN 4 and 5)
    macro_z, hpi_growth = load_prices(seed_dir)
    n = len(cust)
    mi = rng.integers(0, 24, n)
    month = [WINDOW[i] for i in mi]
    sent = pd.to_datetime([p.start_time + pd.Timedelta(days=int(d)) for p, d in zip(month, rng.integers(0, 28, n))])
    # 6-month average total balance before the sent month: BAL_MONTHS index of window month i is i + 6
    a6 = np.array([tot_hist[i: i + 6, j].mean() for j, i in enumerate(mi)])
    age_at = ((sent - cust.date_of_birth).dt.days // 365).values
    sc, ic, pm, city = cust.credit_score.values, inc.values, cust.monthly_household_pmt.values, cust.city_clean.values
    qual = {t: (sc >= s) & (sc <= 850) & (ic >= i_) & (a6 >= d) for t, (s, i_, d) in TIERS.items()}
    gen = cust.generation.values
    mg = np.isin(gen, ["millennial", "gen_x"])
    seg_plat = mg & np.isin(city, PLAT_BT_CITIES) & qual["Platinum"] & (pm > 1400)
    seg_gold = ((cust.marital_status.values == "married") & (cust.own_rent_home.values == "own") & (age_at >= 30) & (age_at <= 50)
                & (ic >= 50_000) & (ic <= 125_000) & (sc >= 700) & (pm > 1000) & np.isin(city, GOLD_CITIES))
    seg_silv = (cust.own_rent_home.values == "rent") & (age_at >= 28) & (age_at <= 35) & (sc >= 680) & (sc <= 740) & np.isin(city, SILVER_CITIES)
    offer = np.empty(n, object)
    u = rng.random(n)
    for j in range(n):
        q = [t for t in TIERS if qual[t][j]]
        if seg_plat[j] and u[j] < 0.9:
            offer[j] = "PLT_BT12" if u[j] < 0.6 else "PLT_TE5"
        elif seg_gold[j] and u[j] < 0.75:
            offer[j] = "GLD_GROC5"
        elif seg_silv[j] and u[j] < 0.75:
            offer[j] = "SIL_BT6"
        else:
            best = max(q, key=RANK.get) if q else None
            tier = rng.choice(list(TIERS)) if (not q or rng.random() < 0.12) else (best if rng.random() < 0.5 else rng.choice(q))
            offer[j] = {"Silver": "SIL_BT6", "Gold": "GLD_GROC5", "Cashback": "CB_ALL3"}.get(tier) or rng.choice(["PLT_BT12", "PLT_TE5"])
    card = np.array([OFFERS[o][0] for o in offer])
    qualified = np.array([qual[c][j] for j, c in enumerate(card)])

    z = np.array([macro_z[p] for p in month])
    year2 = mi >= 12
    cal = np.array([p.month for p in month])
    mass_aff = np.where(np.isin(city, list(LOW_COST)), (ic >= 50_000) & (ic <= 150_000), (ic >= 75_000) & (ic <= 250_000))
    urban_sub = np.isin(np.array([MARKET[c] for c in city]), ["urban_core", "suburban", "suburban_style_metro"])
    growth = np.array([hpi_growth[METRO[c]] for c in city])
    high_growth = growth >= np.median(list(hpi_growth.values))

    p = np.select([gen == "gen_z", gen == "millennial", gen == "gen_x"], [0.08, 0.11, 0.10], 0.0)
    named = np.zeros(n, bool)
    boomer = gen == "boomer"
    p = np.where(boomer, np.where(np.isin(city, ["Raleigh", "Charlotte"]), rng.uniform(0.055, 0.06, n), rng.uniform(0.04, 0.05, n)), p)
    p = np.where(gen == "silent", rng.uniform(0.02, 0.04, n), p)
    older = (age_at > 58) & (cust.n_accounts.values >= 2) & (sc > 700)
    p = np.where(older, rng.uniform(0.01, 0.015, n), p)
    fixed = boomer | (gen == "silent") | older
    p = np.where(mg & high_growth, p * rng.uniform(1.3, 1.5, n), p)
    col = urban_sub & mass_aff & ~fixed
    p = np.where(col & np.isin(offer, ["SIL_BT6", "PLT_BT12", "GLD_GROC5"]), p * np.exp(0.30 * z), p)
    p = np.where(col & (offer == "CB_ALL3"), p * np.exp(0.15 * z), p)
    p = np.where(col & (offer == "PLT_TE5"), p * np.exp(-0.30 * z), p)
    macro_pos = np.clip(0.5 + 0.3 * z, 0, 1)

    def in_range(lo, hi, pos):
        return lo + (hi - lo) * np.clip(pos, 0, 1)
    sp = seg_plat & qualified
    pbt = np.where(year2, in_range(0.06, 0.16, macro_pos), np.where((cal >= 3) & (cal <= 9), in_range(0.12, 0.16, macro_pos), in_range(0.08, 0.10, macro_pos)))
    p = np.where(sp & (offer == "PLT_BT12"), pbt, p)
    p = np.where(sp & (offer == "PLT_TE5"), np.where(year2, in_range(0.003, 0.009, macro_pos), in_range(0.01, 0.03, 1 - macro_pos)), p)
    season = np.select([(cal >= 4) & (cal <= 9), cal == 11, cal == 12], [0.2 + (cal - 4) / 5 * 0.7, 0.8, 1.0], 0.3)
    gpos = 0.6 * season + 0.4 * macro_pos
    sg = seg_gold & qualified & (offer == "GLD_GROC5")
    p = np.where(sg, np.where(year2, in_range(0.12, 0.15, gpos), in_range(0.08, 0.10, gpos)), p)
    ss = seg_silv & qualified & (offer == "SIL_BT6")
    p = np.where(ss, rng.uniform(0.18, 0.22, n), p)
    named = sp & np.isin(offer, ["PLT_BT12", "PLT_TE5"]) | sg | ss
    # Calibrate the unnamed segments so overall acceptance (all solicitations) lands near 10%
    free = ~named & ~fixed
    target = 0.10 * n
    f = (target - p[~free].sum()) / p[free].sum()
    p = np.where(free, np.minimum(p * f, 0.45), p)
    accepted = rng.random(n) < p
    summary["calibration_factor"] = round(float(f), 3)
    summary["acceptance_rate_overall"] = round(float(accepted.mean()), 4)

    sol = pd.DataFrame({
        "solicitation_id": [f"S{j:07d}" for j in range(1, n + 1)],
        "customer_id": cust.customer_id, "offer_code": offer, "card_product": card,
        "campaign_code": [OFFERS[o][2] for o in offer], "sent_date": sent.date,
        "response": np.where(accepted, "ACCEPTED", "DECLINED"),
    })
    sol["response_date"] = (sent + pd.to_timedelta(np.where(accepted, rng.integers(3, 45, n), 30), unit="D")).date
    sol["channel"] = rng.choice(["mail", "email", "mobile"], n, p=[0.5, 0.3, 0.2])

    # crm cross-reference: about 1% of customers have no xref row (planted)
    cust["crm_customer_key"] = [f"C{v:09d}" for v in rng.choice(10**9, n, replace=False)]
    unmapped = rng.random(n) < 0.01
    xref = cust.loc[~unmapped, ["crm_customer_key", "customer_id"]].rename(columns={"customer_id": "ecif_customer_id"})
    xref["linked_date"] = cust.loc[~unmapped, "customer_since"].dt.date.values
    sol = sol.merge(cust[["customer_id", "crm_customer_key"]], on="customer_id").drop(columns="customer_id")

    # Planted bad credit scores in ecif (outside 300-850)
    bad = rng.choice(n, 40, replace=False)
    out_c = cust[CUSTOMER_COLS + ["record_origin", "origin_group", "address_token", "ssn_last4_token"]].copy()
    out_c["date_of_birth"] = out_c.date_of_birth.dt.date
    out_c["customer_since"] = out_c.customer_since.dt.date
    out_c.loc[bad, "credit_score"] = rng.choice([0, 999, 1200], 40)

    # Write raw files
    for sub in ("ecif_customers", "ecif_accounts", "ecif_balances", "crm_campaigns", "crm_customer_xref", "crm_solicitations", "macro_prices"):
        d = raw_dir / sub
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    pend = seed_dir / "pending"
    if pend.exists():
        shutil.rmtree(pend)
    pend.mkdir(parents=True)
    stamp = "20261031"
    out_c.to_csv(raw_dir / "ecif_customers" / f"ecif_customers_{stamp}.csv", index=False)
    accounts.to_csv(raw_dir / "ecif_accounts" / f"ecif_accounts_{stamp}.csv", index=False)
    for p_, df in zip(BAL_MONTHS, bal_rows):
        df.to_csv(raw_dir / "ecif_balances" / f"ecif_balances_{p_.strftime('%Y%m')}.csv", index=False)
    camp = pd.DataFrame([{"campaign_code": v[2], "offer_code": k, "card_product": v[0], "offer_description": v[1],
                          "start_date": WINDOW[0].start_time.date(), "end_date": WINDOW[-1].end_time.date()} for k, v in OFFERS.items()])
    camp.to_csv(raw_dir / "crm_campaigns" / f"crm_campaigns_{stamp}.csv", index=False)
    xref.to_csv(raw_dir / "crm_customer_xref" / f"crm_customer_xref_{stamp}.csv", index=False)
    sol["_m"] = pd.to_datetime(sol.sent_date).dt.strftime("%Y%m")
    late_month, resend_month = "202603", "202506"
    for mth, df in sol.groupby("_m"):
        target_dir = pend if mth == late_month else raw_dir / "crm_solicitations"
        df.drop(columns="_m").to_csv(target_dir / f"crm_solicitations_{mth}.csv", index=False)
    shutil.copy(raw_dir / "crm_solicitations" / f"crm_solicitations_{resend_month}.csv",
                raw_dir / "crm_solicitations" / f"crm_solicitations_{resend_month}_resend.csv")
    for f_ in (seed_dir / "public").glob("*.csv"):
        shutil.copy(f_, raw_dir / "macro_prices" / f_.name)

    # Ground truth (never read by the pipeline)
    truth_dir.mkdir(parents=True, exist_ok=True)
    gt = cust[["customer_id", "crm_customer_key", "record_origin", "origin_group", "generation"]].copy()
    gt["xref_unmapped"] = unmapped
    gt["bad_credit_score"] = False
    gt.loc[bad, "bad_credit_score"] = True
    gt["offer_code"], gt["qualified"], gt["p_accept"], gt["accepted"] = offer, qualified, p.round(5), accepted
    gt["seg_platinum_bt"], gt["seg_gold"], gt["seg_silver"] = seg_plat, seg_gold, seg_silv
    gt["avg6_total_balance"] = a6.round(2)
    gt.to_csv(truth_dir / "customer_truth.csv", index=False)
    resend_rows = int((sol._m == resend_month).sum())
    summary.update({
        "accounts": len(accounts), "balance_rows": int(sum(len(b) for b in bal_rows)), "balance_months": len(BAL_MONTHS),
        "solicitations": n, "solicitation_files": int(sol._m.nunique()), "late_file_held_back": f"crm_solicitations_{late_month}.csv",
        "late_file_rows": int((sol._m == late_month).sum()), "resend_file_duplicate_rows": resend_rows,
        "xref_unmapped_customers": int(unmapped.sum()), "bad_credit_scores": 40,
        "qualified_solicitations": int(qualified.sum()), "qualified_acceptance_rate": round(float(accepted[qualified].mean()), 4),
        "segments": {"platinum_bt": int(seg_plat.sum()), "gold": int(seg_gold.sum()), "silver_coastal": int(seg_silv.sum())},
        "acceptance_by_card_qualified": {c: round(float(accepted[qualified & (card == c)].mean()), 4) for c in TIERS},
    })
    (truth_dir / "generation_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, default=str))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed_dir", default="/Volumes/c360_bank/cards/seed")
    ap.add_argument("--raw_dir", default="/Volumes/c360_bank/cards/raw")
    ap.add_argument("--seed", type=int, default=20261120)
    main(ap.parse_args())
