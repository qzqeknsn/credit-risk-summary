CREATE OR REPLACE VIEW reporting.v_metrics AS
WITH snapshots AS (
    SELECT
        snapshot_date,
        SUM(principal_kzt) as portfolio,
        SUM(par30_kzt) as par30_sum,
        SUM(par90_kzt) as par90_sum,
        SUM(npl_kzt) as npl_sum,
        SUM(provision_kzt) as provisions,
        COUNT(loan_id) as loan_count
    FROM reporting.v_loans_clean
    GROUP BY snapshot_date
),
dates AS (
    SELECT
        MIN(snapshot_date) as d1,
        MAX(snapshot_date) as d2
    FROM snapshots
),
metrics AS (
    SELECT
        s.snapshot_date,
        s.portfolio,
        s.par30_sum / NULLIF(s.portfolio, 0) as par30_rate,
        s.par90_sum / NULLIF(s.portfolio, 0) as par90_rate,
        s.npl_sum / NULLIF(s.portfolio, 0) as npl_rate,
        s.provisions,
        s.provisions / NULLIF(s.npl_sum, 0) as coverage_rate,
        s.loan_count
    FROM snapshots s
)
SELECT
    m1.snapshot_date as date_1,
    m2.snapshot_date as date_2,
    -- Portfolio
    m1.portfolio as portfolio_d1,
    m2.portfolio as portfolio_d2,
    (m2.portfolio - m1.portfolio) / NULLIF(m1.portfolio, 0) as portfolio_delta,
    -- PAR30
    m1.par30_rate as par30_d1,
    m2.par30_rate as par30_d2,
    (m2.par30_rate - m1.par30_rate) as par30_delta,
    -- PAR90
    m1.par90_rate as par90_d1,
    m2.par90_rate as par90_d2,
    (m2.par90_rate - m1.par90_rate) as par90_delta,
    -- NPL
    m1.npl_rate as npl_d1,
    m2.npl_rate as npl_d2,
    (m2.npl_rate - m1.npl_rate) as npl_delta,
    -- Provisions
    m1.provisions as prov_d1,
    m2.provisions as prov_d2,
    (m2.provisions - m1.provisions) / NULLIF(m1.provisions, 0) as prov_delta,
    -- Coverage
    m1.coverage_rate as cov_d1,
    m2.coverage_rate as cov_d2,
    (m2.coverage_rate - m1.coverage_rate) as cov_delta,
    -- Loan Count
    m1.loan_count as count_d1,
    m2.loan_count as count_d2,
    (m2.loan_count - m1.loan_count) as count_delta
FROM metrics m1, metrics m2, dates d
WHERE m1.snapshot_date = d.d1 AND m2.snapshot_date = d.d2;
