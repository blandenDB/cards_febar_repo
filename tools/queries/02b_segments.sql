-- title: Featured segments and generations: acceptance by campaign year (pipeline tables)
WITH f AS (
  SELECT g.*, CASE WHEN g.campaign_month <= 12 THEN 1 ELSE 2 END AS yr,
    (g.generation IN ('millennial','gen_x') AND g.city IN ('Cary','Raleigh','Charlotte','Greenville','Durham','Wilmington','Charleston')
      AND g.card_product = 'Platinum' AND g.qualified AND g.monthly_household_pmt > 1400) AS plat_seg,
    (g.years_at_residence BETWEEN 0 AND 6 AND g.residence_year >= 2020 AND g.own_rent_home = 'own' AND g.age_at_solicitation BETWEEN 30 AND 50 AND g.annual_income BETWEEN 50000 AND 125000
      AND g.credit_score >= 700 AND g.monthly_household_pmt > 1000 AND g.city IN ('Apex','Holly Springs','Greensboro','Winston-Salem')
      AND g.offer_code = 'GLD_GROC5' AND g.qualified) AS gold_seg
  FROM c360_bank.cards.gold_features g
)
SELECT 'Platinum 0% balance transfer segment' segment, count(*) n, round(avg(CASE WHEN yr=1 THEN CAST(accepted AS INT) END),4) year1,
       round(avg(CASE WHEN yr=1 AND month(sent_month) BETWEEN 3 AND 9 THEN CAST(accepted AS INT) END),4) year1_mar_sep,
       round(avg(CASE WHEN yr=2 THEN CAST(accepted AS INT) END),4) year2 FROM f WHERE plat_seg AND offer_code='PLT_BT12'
UNION ALL SELECT 'Same segment, travel and entertainment', count(*), round(avg(CASE WHEN yr=1 THEN CAST(accepted AS INT) END),4), NULL,
       round(avg(CASE WHEN yr=2 THEN CAST(accepted AS INT) END),4) FROM f WHERE plat_seg AND offer_code='PLT_TE5'
UNION ALL SELECT 'Gold grocery segment', count(*), round(avg(CASE WHEN yr=1 THEN CAST(accepted AS INT) END),4), NULL,
       round(avg(CASE WHEN yr=2 THEN CAST(accepted AS INT) END),4) FROM f WHERE gold_seg
UNION ALL SELECT concat('Generation: ', generation), count(*), round(avg(CASE WHEN yr=1 THEN CAST(accepted AS INT) END),4), NULL,
       round(avg(CASE WHEN yr=2 THEN CAST(accepted AS INT) END),4) FROM f GROUP BY generation
UNION ALL SELECT 'All solicitations', count(*), round(avg(CASE WHEN yr=1 THEN CAST(accepted AS INT) END),4), NULL,
       round(avg(CASE WHEN yr=2 THEN CAST(accepted AS INT) END),4) FROM f;
