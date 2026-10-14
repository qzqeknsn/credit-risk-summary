CREATE OR REPLACE VIEW reporting.v_dashboard_kpi AS 
SELECT 
    m1.snapshot_date as date_from, 
    m2.snapshot_date as date_to,
    m1.portfolio_kzt as port_from, 
    m2.portfolio_kzt as port_to,
    (m2.portfolio_kzt - m1.portfolio_kzt) / m1.portfolio_kzt as port_delta,
    m1.par30_rate as par30_from, 
    m2.par30_rate as par30_to,
    (m2.par30_rate - m1.par30_rate) as par30_delta,
    m1.par90_rate as par90_from, 
    m2.par90_rate as par90_to,
    (m2.par90_rate - m1.par90_rate) as par90_delta,
    m1.npl_rate as npl_from, 
    m2.npl_rate as npl_to,
    (m2.npl_rate - m1.npl_rate) as npl_delta,
    m1.provisions_kzt as prov_from, 
    m2.provisions_kzt as prov_to,
    (m2.provisions_kzt - m1.provisions_kzt) / m1.provisions_kzt as prov_delta
FROM reporting.v_metrics m1, reporting.v_metrics m2
WHERE m1.snapshot_date = '2026-09-01' AND m2.snapshot_date = '2026-10-01';

CREATE OR REPLACE VIEW reporting.v_dashboard_trend AS 
SELECT snapshot_date, portfolio_kzt, par30_rate, par90_rate, npl_rate, provisions_kzt / portfolio_kzt as coverage_rate
FROM reporting.v_metrics;

CREATE OR REPLACE VIEW reporting.v_dashboard_industry AS 
SELECT 
    industry, 
    snapshot_date, 
    SUM(principal_kzt) as portfolio, 
    SUM(CASE WHEN dpd > 30 THEN principal_kzt ELSE 0 END) / NULLIF(SUM(principal_kzt), 0) as par30_rate
FROM reporting.v_loans_clean
GROUP BY 1, 2;

CREATE OR REPLACE VIEW reporting.v_dashboard_program AS 
SELECT 
    program, 
    snapshot_date, 
    SUM(principal_kzt) as portfolio, 
    SUM(CASE WHEN dpd > 30 THEN principal_kzt ELSE 0 END) / NULLIF(SUM(principal_kzt), 0) as par30_rate
FROM reporting.v_loans_clean
GROUP BY 1, 2;

CREATE OR REPLACE VIEW reporting.v_dashboard_concentration AS 
SELECT 
    'Top 10 Groups' as segment,
    snapshot_date,
    SUM(principal_kzt) as portfolio,
    (SELECT SUM(principal_kzt) FROM reporting.v_loans_clean l2 WHERE l2.snapshot_date = l1.snapshot_date) as total_portfolio
FROM reporting.v_loans_clean l1
WHERE (group_id, snapshot_date) IN (
    SELECT group_id, snapshot_date FROM (
        SELECT group_id, snapshot_date, SUM(principal_kzt) as sum_p, ROW_NUMBER() OVER (PARTITION BY snapshot_date ORDER BY SUM(principal_kzt) DESC) as rn
        FROM reporting.v_loans_clean
        GROUP BY 1, 2
    ) t WHERE rn <= 10
)
GROUP BY 1, 2;
