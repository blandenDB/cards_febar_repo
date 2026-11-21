"""Build the Genie space definition (src/genie/cards_cdo.geniespace.json) from the readable
definitions below. The bundle deploys the JSON (resources/cards_genie.yml).

[YOUR WORDS] The sample questions, instructions and benchmark questions are drafts.
Rewrite them in your own words; they are part of your story.

Usage: python3 src/genie/build_space.py
"""
import hashlib
import json
import os

FQ = "c360_bank.cards"
TABLES = ["v_cdo_summary", "v_cohort_growth", "v_price_trends", "v_review_summary"]

SAMPLE_QUESTIONS = [
    "How many new cards did each city add last month?",
    "What is the Card Product Penetration Rate by tier?",
    "Which cohorts are growing above 10% a year?",
    "How has the Gold penetration rate changed by month in Apex, Holly Springs, Greensboro and Winston-Salem?",
    "Show monthly new Platinum cards next to gasoline prices.",
    "How does penetration compare for mass affluent customers versus others, by market type?",
    "How have campaign reviewers decided on the next campaign's targets, by region?",
]

INSTRUCTIONS = """\
You answer questions from the Chief Data Officer and the Data & Analytics team at Arkterus Bank about credit card adoption by tier. All data is synthetic, except the public price data.

Tables:
- v_cdo_summary: one row per month x city x tier x generation x mass affluent flag. Columns: targeted (offers sent), qualified_targeted (offers to customers who met the tier rules), new_cards (accepted offers from qualified customers), penetration_rate.
- v_cohort_growth: one row per cohort (generation x market type x mass affluent x tier) with qualified acceptance in four 6-month periods (rate_p1 to rate_p4, n_p1 to n_p4), growth_train (period 3 vs 1), growth_test (period 4 vs 2) and growing_above_10pct.
- v_price_trends: monthly public prices by metro_area. CPI series are South region figures (same in every metro); gasoline_usd_per_gallon is the Lower Atlantic average; house_price_index and house_price_yoy are per metro. cpi_interpolated marks October 2025, which was not published and is interpolated.
- v_review_summary: campaign team accept or exclude decisions on next campaign targets, by region and tier.

Definitions:
- Card Product Penetration Rate by Tier = sum(new_cards) / sum(qualified_targeted). Always compute it from the sums; never average penetration_rate across rows.
- "New cards" means new_cards (qualified acceptances), not targeted.
- Tiers: Silver, Gold, Platinum, Cashback. The campaign window is November 2024 to October 2026; campaign year 1 is November 2024 to October 2025, year 2 is November 2025 to October 2026.
- Generations: gen_z, millennial, gen_x, boomer, silent. Mass affluent is relative to local cost of living ($50,000 to $150,000 in lower-cost markets, $75,000 to $250,000 elsewhere).
- Market types: urban_core, suburban, suburban_style_metro, exurban, fast_growing_mid_size, highway_corridor, coastal_resort, mountain_tourism. Filter with equality on these exact codes.
- Join prices to v_cdo_summary on month and metro_area.
- Return rates as fractions rounded to 4 decimal places unless asked for a percentage.

Cost of living: when asked whether prices drive acceptance, show the monthly figures side by side and describe what moves together. Say that the bank's evaluation protocol found the price data's contribution to targeting inconclusive (met in 2 of 4 test runs), so this is an association, not a proven cause.

Fair lending: generation is shown for reporting and fairness monitoring only. Do not suggest targeting customers by age, generation, marital status or gender.
"""

EXAMPLE_SQL = [
    ("What is the Card Product Penetration Rate by tier?",
     f"""SELECT tier, SUM(qualified_targeted) AS qualified_targeted, SUM(new_cards) AS new_cards,
  ROUND(SUM(new_cards) / SUM(qualified_targeted), 4) AS penetration_rate
FROM {FQ}.v_cdo_summary GROUP BY tier ORDER BY tier"""),
    ("How many new cards did each city add in October 2026?",
     f"""SELECT city, SUM(new_cards) AS new_cards FROM {FQ}.v_cdo_summary
WHERE month = DATE'2026-10-01' GROUP BY city ORDER BY new_cards DESC"""),
    ("Show monthly new Gold cards in Apex next to grocery prices.",
     f"""SELECT s.month, SUM(s.new_cards) AS new_gold_cards, ROUND(SUM(s.new_cards) / SUM(s.qualified_targeted), 4) AS penetration_rate,
  MAX(p.cpi_food_at_home) AS cpi_food_at_home, MAX(p.food_at_home_3m_change) AS food_at_home_3m_change
FROM {FQ}.v_cdo_summary s LEFT JOIN {FQ}.v_price_trends p ON p.month = s.month AND p.metro_area = s.metro_area
WHERE s.tier = 'Gold' AND s.city = 'Apex' GROUP BY s.month ORDER BY s.month"""),
]

BENCHMARKS = [
    ("How many new cards were issued in total?", f"SELECT SUM(new_cards) AS new_cards FROM {FQ}.v_cdo_summary"),
    ("What is the Card Product Penetration Rate by tier?",
     f"SELECT tier, ROUND(SUM(new_cards) / SUM(qualified_targeted), 4) AS penetration_rate FROM {FQ}.v_cdo_summary GROUP BY tier ORDER BY tier"),
    ("Which 5 cities had the most new cards?",
     f"SELECT city, SUM(new_cards) AS new_cards FROM {FQ}.v_cdo_summary GROUP BY city ORDER BY new_cards DESC LIMIT 5"),
    ("What is the Gold penetration rate in Apex?",
     f"SELECT ROUND(SUM(new_cards) / SUM(qualified_targeted), 4) AS penetration_rate FROM {FQ}.v_cdo_summary WHERE tier = 'Gold' AND city = 'Apex'"),
    ("What is the penetration rate by generation across all tiers?",
     f"SELECT generation, ROUND(SUM(new_cards) / SUM(qualified_targeted), 4) AS penetration_rate FROM {FQ}.v_cdo_summary GROUP BY generation ORDER BY generation"),
    ("How many cohorts are growing above 10% a year?",
     f"SELECT COUNT(*) AS cohorts FROM {FQ}.v_cohort_growth WHERE growing_above_10pct"),
    ("Which tiers have cohorts growing above 10% a year, and how many in each?",
     f"SELECT tier, COUNT(*) AS cohorts FROM {FQ}.v_cohort_growth WHERE growing_above_10pct GROUP BY tier ORDER BY tier"),
    ("What was the gasoline price per gallon in October 2026?",
     f"SELECT MAX(gasoline_usd_per_gallon) AS gasoline_usd_per_gallon FROM {FQ}.v_price_trends WHERE month = DATE'2026-10-01'"),
    ("How many new cards were issued in each month of 2026?",
     f"SELECT month, SUM(new_cards) AS new_cards FROM {FQ}.v_cdo_summary WHERE year(month) = 2026 GROUP BY month ORDER BY month"),
    ("What is the penetration rate for mass affluent customers compared with other customers?",
     f"SELECT mass_affluent, ROUND(SUM(new_cards) / SUM(qualified_targeted), 4) AS penetration_rate FROM {FQ}.v_cdo_summary GROUP BY mass_affluent ORDER BY mass_affluent"),
]


def hid(*parts):
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def lines(text):
    ls = text.splitlines(keepends=True)
    return ls if ls else [text]


def main():
    space = {
        "version": 2,
        "config": {"sample_questions": sorted([{"id": hid("q", q), "question": [q]} for q in SAMPLE_QUESTIONS], key=lambda x: x["id"])},
        "data_sources": {"tables": [{"identifier": f"{FQ}.{t}"} for t in sorted(TABLES)]},
        "instructions": {
            "text_instructions": [{"id": hid("instructions"), "content": lines(INSTRUCTIONS)}],
            "example_question_sqls": sorted([{"id": hid("ex", q), "question": [q], "sql": lines(s)} for q, s in EXAMPLE_SQL], key=lambda x: x["id"]),
        },
        "benchmarks": {"questions": sorted([{"id": hid("bm", q), "question": [q], "answer": [{"format": "SQL", "content": lines(s)}]}
                                            for q, s in BENCHMARKS], key=lambda x: x["id"])},
    }
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cards_cdo.geniespace.json")
    with open(out, "w") as f:
        json.dump(space, f, indent=2)
    print(f"wrote {out}: {len(TABLES)} tables, {len(SAMPLE_QUESTIONS)} sample questions, {len(EXAMPLE_SQL)} example SQLs, {len(BENCHMARKS)} benchmarks")


if __name__ == "__main__":
    main()
