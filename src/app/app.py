"""Card adoption app for Arkterus Bank: new cards by city, growing cohorts, next campaign target
review (accept or exclude) and target detail.

Reads only the Lakebase `app` views and writes app.target_reviews. The signed-in user comes from
the X-Forwarded-Email header that Databricks Apps sets; every query runs in a transaction that sets
app.reviewer, so Postgres views and row-level security return only that reviewer's regions.
All customer data is synthetic.
"""
import os

import altair as alt
import pandas as pd
import psycopg
import streamlit as st
from databricks.sdk import WorkspaceClient

ENDPOINT = os.environ.get("LAKEBASE_ENDPOINT", "projects/cards-lakebase/branches/production/endpoints/primary")
TIERS = ["Silver", "Gold", "Platinum", "Cashback"]
GEN_LABEL = {"gen_z": "Gen Z", "millennial": "Millennials", "gen_x": "Gen X", "boomer": "Boomers", "silent": "Silent"}
MARKET_LABEL = {"urban_core": "Urban core", "suburban": "Suburban", "suburban_style_metro": "Suburban-style metro",
                "exurban": "Exurban", "fast_growing_mid_size": "Fast-growing mid-size", "highway_corridor": "Highway corridor",
                "coastal_resort": "Coastal and resort", "mountain_tourism": "Mountain and tourism"}
BAR = "#2a78d6"  # single-series marks
# Categorical palette in fixed order (validated for colorblind separation in the earlier build).
CATS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]

st.set_page_config(page_title="Card adoption by tier", layout="wide")


@st.cache_resource
def workspace():
    return WorkspaceClient()


@st.cache_resource(ttl=40 * 60)  # database OAuth tokens last about an hour
def credential():
    w = workspace()
    return {"token": w.postgres.generate_database_credential(endpoint=ENDPOINT).token,
            "user": os.environ.get("PGUSER") or w.current_user.me().user_name,
            "host": os.environ.get("PGHOST") or w.postgres.get_endpoint(name=ENDPOINT).status.hosts.host,
            "dbname": os.environ.get("PGDATABASE", "cards")}


def run(reviewer, sql, params=None, write=False):
    c = credential()
    with psycopg.connect(host=c["host"], dbname=c["dbname"], user=c["user"], password=c["token"], sslmode="require", connect_timeout=10) as conn:
        with conn.transaction():
            cur = conn.cursor()
            cur.execute("SELECT set_config('app.reviewer', %s, true)", (reviewer,))
            cur.execute(sql, params or ())
            if write:
                return None
            return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])


reviewer = st.context.headers.get("X-Forwarded-Email", "")
if not reviewer and not os.environ.get("DATABRICKS_APP_NAME"):
    reviewer = os.environ.get("CARDS_DEV_REVIEWER", "")  # local testing only; never used inside Databricks Apps
if not reviewer:
    st.error("No signed-in user was forwarded to the app. Open it from the Databricks Apps URL.")
    st.stop()

regions = run(reviewer, "SELECT region FROM app.my_regions ORDER BY region")["region"].tolist()
st.sidebar.markdown("### Arkterus Bank card campaigns")
st.sidebar.write(reviewer)
if not regions:
    st.title("Card adoption by tier")
    st.info("You are not on the campaign team roster. Ask your data owner to add you (cards_campaign_roster).")
    st.stop()
st.sidebar.write("Regions: " + ", ".join(regions))
page = st.sidebar.radio("View", ["New cards by city", "Growing cohorts", "Target review", "Target detail"], key="page")
st.sidebar.caption("Synthetic customer data; public price data from BLS, EIA and FHFA. Penetration rate = accepted offers "
                   "from qualified customers / qualified customers targeted.")


def rate(df):
    q = df["qualified_targeted"].sum()
    return df["new_cards"].sum() / q if q else float("nan")


if page == "New cards by city":
    st.title("New cards by city")
    cs = run(reviewer, "SELECT month, city, market_type, tier, cohort_generation, mass_affluent, qualified_targeted, new_cards FROM app.city_summary")
    cs["month"] = pd.to_datetime(cs["month"])
    cs["campaign_year"] = (cs["month"] >= "2025-11-01").map({False: "Year 1 (Nov 2024 to Oct 2025)", True: "Year 2 (Nov 2025 to Oct 2026)"})
    c1, c2 = st.columns([1, 1])
    year = c1.selectbox("Campaign year", ["Both years"] + sorted(cs["campaign_year"].unique()), key="year")
    tier = c2.selectbox("Tier", ["All tiers"] + TIERS, key="tier")
    d = cs if year == "Both years" else cs[cs.campaign_year == year]
    d = d if tier == "All tiers" else d[d.tier == tier]
    k1, k2, k3 = st.columns(3)
    k1.metric("New cards", f"{int(d.new_cards.sum()):,}")
    k2.metric("Qualified customers targeted", f"{int(d.qualified_targeted.sum()):,}")
    k3.metric("Card Product Penetration Rate", f"{rate(d):.1%}")
    by_city = d.groupby("city", as_index=False)[["new_cards", "qualified_targeted"]].sum()
    by_city["penetration_rate"] = by_city.new_cards / by_city.qualified_targeted
    by_city = by_city.sort_values("new_cards", ascending=False)
    sel = alt.selection_point(fields=["city"], name="pick")
    chart = alt.Chart(by_city).mark_bar(color=BAR, cornerRadiusEnd=4).encode(
        x=alt.X("new_cards:Q", title="New cards"), y=alt.Y("city:N", sort="-x", title=None),
        opacity=alt.condition(sel, alt.value(1), alt.value(0.45)),
        tooltip=[alt.Tooltip("city:N"), alt.Tooltip("new_cards:Q", format=","), alt.Tooltip("penetration_rate:Q", format=".1%", title="Penetration rate")],
    ).add_params(sel).properties(height=420)
    ev = st.altair_chart(chart, width="stretch", on_select="rerun", key="city_chart")
    picked = [p["city"] for p in (ev.selection.get("pick") or [])] if ev and ev.selection else []
    city = picked[0] if picked else st.selectbox("Or pick a city to break down", by_city.city.tolist(), key="city_pick")
    st.subheader(f"{city}: by tier and cohort")
    dc = d[d.city == city]
    t = dc.groupby("tier", as_index=False)[["new_cards", "qualified_targeted"]].sum()
    t["penetration_rate"] = (t.new_cards / t.qualified_targeted).map("{:.1%}".format)
    st.dataframe(t, hide_index=True, width="stretch")
    g = dc.groupby(["cohort_generation", "mass_affluent"], as_index=False)[["new_cards", "qualified_targeted"]].sum()
    g["cohort"] = g.cohort_generation.map(GEN_LABEL) + g.mass_affluent.map({True: ", mass affluent", False: ""})
    g["penetration_rate"] = (g.new_cards / g.qualified_targeted).map("{:.1%}".format)
    st.dataframe(g[["cohort", "qualified_targeted", "new_cards", "penetration_rate"]].sort_values("new_cards", ascending=False),
                 hide_index=True, width="stretch")
    st.caption("Cohorts are shown for reporting only; targeting never uses age, generation, marital status or gender.")

elif page == "Growing cohorts":
    st.title("Cohorts growing above 10% a year")
    st.caption("Growth = qualified acceptance rate versus the same months a year earlier, above 10% in both the training "
               "period (months 13 to 18 vs 1 to 6) and the test period (19 to 24 vs 7 to 12), with at least 200 qualified offers each (EVAL_PROTOCOL.md section 8).")
    cg = run(reviewer, "SELECT * FROM app.cohort_growth WHERE growing_above_10pct ORDER BY tier, generation")
    if cg.empty:
        st.info("No cohort meets the growth rule.")
        st.stop()
    cg["cohort"] = cg.generation.map(GEN_LABEL) + ", " + cg.market_type.map(MARKET_LABEL) + cg.mass_affluent.map({True: ", mass affluent", False: ""}) + " (" + cg.tier + ")"
    show = cg[["cohort", "growth_train", "growth_test", "rate_p1", "rate_p2", "rate_p3", "rate_p4"]].copy()
    for c in show.columns[1:]:
        show[c] = show[c].astype(float).map("{:.1%}".format)
    st.dataframe(show.rename(columns={"growth_train": "growth (train)", "growth_test": "growth (test)", "rate_p1": "months 1-6",
                                      "rate_p2": "months 7-12", "rate_p3": "months 13-18", "rate_p4": "months 19-24"}), hide_index=True, width="stretch")
    long = cg.melt(id_vars=["cohort"], value_vars=["rate_p1", "rate_p2", "rate_p3", "rate_p4"], var_name="period", value_name="rate")
    long["period"] = long.period.map({"rate_p1": "1-6", "rate_p2": "7-12", "rate_p3": "13-18", "rate_p4": "19-24"})
    long["rate"] = long.rate.astype(float)
    order = cg.cohort.tolist()
    line = alt.Chart(long).mark_line(point=alt.OverlayMarkDef(size=64), strokeWidth=2).encode(
        x=alt.X("period:N", title="Campaign months", sort=["1-6", "7-12", "13-18", "19-24"]),
        y=alt.Y("rate:Q", title="Qualified acceptance rate", axis=alt.Axis(format="%")),
        color=alt.Color("cohort:N", scale=alt.Scale(domain=order, range=CATS[:len(order)]), legend=alt.Legend(title=None, orient="bottom", columns=2)),
        tooltip=["cohort:N", "period:N", alt.Tooltip("rate:Q", format=".1%")]).properties(height=380)
    st.altair_chart(line, width="stretch")

elif page == "Target review":
    st.title("Next campaign: target review")
    c1, c2, c3 = st.columns(3)
    region = c1.selectbox("Region", regions, key="rv_region")
    tier = c2.selectbox("Tier", TIERS, key="rv_tier")
    offers = run(reviewer, "SELECT DISTINCT offer_code, offer_description FROM app.targets WHERE campaign_region = %s AND card_product = %s ORDER BY offer_code", (region, tier))
    if offers.empty:
        st.info("No targets for this region and tier.")
        st.stop()
    offer_by_label = dict(zip(offers.offer_description, offers.offer_code))
    offer = offer_by_label[c3.selectbox("Offer", list(offer_by_label), key="rv_offer")]
    mix = run(reviewer, "SELECT age_group, qualified, selected, share_of_qualified, share_of_selected, adverse_impact_ratio FROM app.selection_mix WHERE campaign_region = %s AND card_product = %s", (region, tier))
    with st.expander("Fairness check: age-group mix of selected targets versus all qualified customers", expanded=True):
        if mix.empty:
            st.write("No mix available.")
        else:
            mix["age group"] = mix.age_group.map(GEN_LABEL)
            mix["flag"] = mix.adverse_impact_ratio.astype(float).map(lambda r: "below 0.8" if r < 0.8 else "")
            for c in ["share_of_qualified", "share_of_selected"]:
                mix[c] = mix[c].astype(float).map("{:.0%}".format)
            mix["adverse_impact_ratio"] = mix.adverse_impact_ratio.astype(float).map("{:.2f}".format)
            st.dataframe(mix[["age group", "qualified", "selected", "share_of_qualified", "share_of_selected", "adverse_impact_ratio", "flag"]],
                         hide_index=True, width="stretch")
            st.caption("The model never uses age, but it can pick up age-linked patterns through other facts. Ratio = selection rate "
                       "of the group / the most-selected group; below 0.8 is flagged for review. Selection is not adjusted by age.")
    tg = run(reviewer, """SELECT t.target_id, t.city, t.rank_in_tier, t.score, t.explanation, t.reason_1, r.decision
                          FROM app.targets t LEFT JOIN app.latest_reviews r ON r.target_id = t.target_id
                          WHERE t.campaign_region = %s AND t.card_product = %s AND t.offer_code = %s
                          ORDER BY t.rank_in_tier LIMIT 200""", (region, tier, offer))
    tg["decision"] = tg.decision.fillna("not reviewed")
    tg["why"] = tg.explanation.fillna("").str.replace("^Why: ", "", regex=True).where(tg.explanation.notna(), tg.reason_1)
    st.write(f"Top {len(tg)} targets by rank in tier (of the top 20%).")
    pick = st.dataframe(tg[["target_id", "city", "rank_in_tier", "decision", "why"]], hide_index=True, width="stretch",
                        on_select="rerun", selection_mode="single-row", key="rv_table")
    rows = pick.selection.rows if pick else []
    by_label = {f"#{int(r.rank_in_tier)}  {r.target_id}": r.target_id for r in tg.itertuples()}
    chosen = st.selectbox("Or choose a target", ["(select a target)"] + list(by_label), key="rv_pick")
    tid = tg.iloc[rows[0]].target_id if rows else by_label.get(chosen)
    if tid:
        st.session_state["detail_target"] = tid
        with st.form("decide", clear_on_submit=True):
            st.markdown(f"**Decide on target {tid}**")
            decision = st.radio("Decision", ["accept", "exclude"], horizontal=True)
            reason = st.text_input("Reason (optional)", max_chars=500)
            if st.form_submit_button("Record decision"):
                run(reviewer, "INSERT INTO app.target_reviews (target_id, campaign_region, card_product, offer_code, decision, reason) VALUES (%s, %s, %s, %s, %s, %s)",
                    (tid, region, tier, offer, decision, reason or None), write=True)
                st.success(f"Recorded: {decision}. Decisions are copied to the Lakehouse nightly.")
    else:
        st.caption("Select a row, or choose a target above, to accept or exclude it.")

else:
    st.title("Target detail")
    tid = st.text_input("Target ID", value=st.session_state.get("detail_target", ""), key="detail_id")
    if not tid:
        st.caption("Pick a target on the Target review screen, or paste a target ID.")
        st.stop()
    t = run(reviewer, "SELECT * FROM app.targets WHERE target_id = %s", (tid,))
    if t.empty:
        st.warning("Target not found in your regions.")
        st.stop()
    r = t.iloc[0]
    st.subheader(f"{r.card_product} card: {r.offer_description}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Rank in tier", f"{int(r.rank_in_tier):,} of {int(r.tier_size):,}")
    c2.metric("Annual fee", f"${int(r.annual_fee)}")
    c3.metric("City", r.city)
    st.markdown("**Why this target**")
    st.write((r.explanation or "").replace("Why: ", "") or "No generated explanation; see the reasons below.")
    st.markdown("**Top reasons (largest effect on the score)**")
    for x in (r.reason_1, r.reason_2, r.reason_3):
        st.write("- " + x)
    hist = run(reviewer, "SELECT decision, reason, created_at FROM app.target_reviews WHERE target_id = %s ORDER BY created_at DESC", (tid,))
    st.markdown("**Review history**")
    st.dataframe(hist, hide_index=True, width="stretch") if not hist.empty else st.write("Not reviewed yet.")
    st.caption(f"Customer {r.customer_id} (synthetic). Model version {r.model_version}.")
