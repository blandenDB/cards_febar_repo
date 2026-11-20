"""Download public price series used as macro context.

Sources (public, no key needed):
- BLS CPI-U, South region, not seasonally adjusted (api.bls.gov v1)
- EIA Lower Atlantic (PADD 1C) retail gasoline, all grades, monthly
- FHFA House Price Index, all-transactions, by metro (quarterly)
Writes CSVs to data/public/.
"""
import csv, io, json, sys, urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "public"
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (public-data-download)"}

BLS = {
    "CUUR0300SA0": "all_items",
    "CUUR0300SAF11": "food_at_home",
    "CUUR0300SEFV": "food_away_from_home",
    "CUUR0300SETB01": "gasoline",
    "CUUR0300SETA01": "new_vehicles",
    "CUUR0300SETA02": "used_vehicles",
    "CUUR0300SAH1": "shelter",
    "CUUR0300SAH21": "household_energy",
    "CUUR0300SAR": "recreation",
    "CUUR0300SAA": "apparel",
    "CUUR0300SAM": "medical_care",
}
METROS = {  # FHFA CBSA codes
    "39580": "Raleigh-Cary", "20500": "Durham-Chapel Hill", "16740": "Charlotte-Concord-Gastonia",
    "24660": "Greensboro-High Point", "49180": "Winston-Salem", "48900": "Wilmington",
    "16700": "Charleston-North Charleston", "17900": "Columbia", "24860": "Greenville-Anderson",
    "34820": "Myrtle Beach-Conway-North Myrtle Beach", "11700": "Asheville", "22500": "Florence",
    "15500": "Burlington", "25940": "Hilton Head Island-Bluffton-Port Royal",
}

def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers={**UA, **({"Content-Type": "application/json"} if data else {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()

def bls():
    ids = list(BLS)
    rows = []
    for start, end in (("2019", "2026"),):
        body = json.dumps({"seriesid": ids, "startyear": start, "endyear": end}).encode()
        res = json.loads(get("https://api.bls.gov/publicAPI/v1/timeseries/data/", body))
        if res.get("status") != "REQUEST_SUCCEEDED":
            sys.exit(f"BLS failed: {res.get('message')}")
        for s in res["Results"]["series"]:
            for d in s["data"]:
                if d["period"].startswith("M") and d["period"] != "M13" and d["value"] not in ("-", ""):
                    rows.append({"source": "BLS CPI-U South region NSA", "area": "South region", "series_id": s["seriesID"],
                                 "series": BLS[s["seriesID"]], "month": f"{d['year']}-{d['period'][1:]}-01", "value": d["value"]})
    rows.sort(key=lambda r: (r["series"], r["month"]))
    return rows

def eia():
    import re
    # Use the public history page CSV-like table (no key needed)
    html = get("https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=EMM_EPM0_PTE_R1Z_DPG&f=M").decode("utf-8", "ignore")
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        m = re.search(r"class='B4'>&nbsp;&nbsp;(\d{4})", tr)
        if not m: continue
        year = int(m.group(1))
        vals = re.findall(r"class='B3'>([^<]*)</td>", tr)
        for i, v in enumerate(vals[:12]):
            v = v.strip().replace("&nbsp;", "")
            if v and year >= 2019:
                rows.append({"source": "EIA retail gasoline all grades", "area": "Lower Atlantic (PADD 1C)", "series_id": "EMM_EPM0_PTE_R1Z_DPG",
                             "series": "gasoline_usd_per_gallon", "month": f"{year}-{i+1:02d}-01", "value": v})
    return rows

def fhfa():
    raw = get("https://www.fhfa.gov/hpi/download/monthly/hpi_master.csv").decode("utf-8", "ignore")
    rows = []
    for r in csv.DictReader(io.StringIO(raw)):
        if r.get("level") == "MSA" and r.get("place_id") in METROS and r.get("hpi_flavor") == "all-transactions" and int(r["yr"]) >= 2019:
            q = int(r["period"])
            rows.append({"source": "FHFA HPI all-transactions NSA", "area": METROS[r["place_id"]], "series_id": r["place_id"],
                         "series": "house_price_index", "month": f"{r['yr']}-{(q-1)*3+1:02d}-01", "value": r["index_nsa"]})
    return rows

def write(name, rows):
    p = OUT / name
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source", "area", "series_id", "series", "month", "value"])
        w.writeheader(); w.writerows(rows)
    months = sorted({r["month"] for r in rows})
    print(json.dumps({"file": name, "rows": len(rows), "series": len({(r['area'], r['series']) for r in rows}),
                      "first_month": months[0] if months else None, "last_month": months[-1] if months else None}))

if __name__ == "__main__":
    write("bls_cpi_south.csv", bls())
    write("eia_gasoline_lower_atlantic.csv", eia())
    write("fhfa_hpi_metros.csv", fhfa())
