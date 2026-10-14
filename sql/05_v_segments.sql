CREATE OR REPLACE VIEW reporting.v_segments AS
SELECT 
    snapshot_date,
    -- Normalize case for better display
    INITCAP(LOWER(industry)) as industry,
    INITCAP(LOWER(program)) as program,
    SUM(principal_kzt) as portfolio_kzt,
    SUM(CASE WHEN dpd > 30 THEN principal_kzt ELSE 0 END) / NULLIF(SUM(principal_kzt), 0) as par30_rate,
    SUM(CASE WHEN is_npl THEN principal_kzt ELSE 0 END) / NULLIF(SUM(principal_kzt), 0) as npl_rate,
    SUM(principal_kzt * provision_rate) as provisions_kzt
FROM reporting.v_loans_clean
GROUP BY snapshot_date, industry, program;
