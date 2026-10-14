DROP VIEW IF EXISTS reporting.v_loans_clean CASCADE;

CREATE VIEW reporting.v_loans_clean AS
WITH deduped AS (
    SELECT DISTINCT ON (loan_id, report_date) *
    FROM raw.portfolio
    ORDER BY loan_id, report_date, principal_outstanding::numeric DESC
),
cleaned AS (
    SELECT
        d.report_date::date AS snapshot_date,
        d.loan_id,
        d.borrower_id,
        d.group_id,
        d.sector AS industry,
        d.program AS program,
        UPPER(d.currency) AS currency,
        d.principal_outstanding::numeric AS principal_raw,
        d.days_past_due::integer AS dpd,
        CASE WHEN d.restructured = '1' THEN TRUE
             WHEN d.restructured = '0' THEN FALSE
             ELSE NULL END AS is_restructured,
        CASE WHEN d.written_off = '1' THEN TRUE
             WHEN d.written_off = '0' THEN FALSE
             ELSE NULL END AS is_written_off,
        COALESCE(fx.fx_rate::numeric,
                 CASE WHEN UPPER(d.currency) = 'KZT' THEN 1.0 ELSE NULL END) AS fx_rate
    FROM deduped d
    LEFT JOIN LATERAL (
        SELECT fx_rate
        FROM raw.fx
        WHERE raw.fx.currency = d.currency
          AND raw.fx.snapshot_date::date <= d.report_date::date
        ORDER BY raw.fx.snapshot_date DESC
        LIMIT 1
    ) fx ON TRUE
    WHERE d.written_off = '0'
),
priced AS (
    SELECT c.*,
           principal_raw * fx_rate AS principal_kzt,
           CASE WHEN dpd > 90 OR is_restructured THEN TRUE ELSE FALSE END AS is_npl
    FROM cleaned c
),
rated AS (
    SELECT p.*,
           CASE WHEN is_npl THEN 0.50
                WHEN dpd > 30 THEN 0.10
                ELSE 0.01 END AS provision_rate
    FROM priced p
)
SELECT r.*,
       principal_kzt * provision_rate                          AS provision_kzt,
       CASE WHEN dpd > 30 THEN principal_kzt ELSE 0 END        AS par30_kzt,
       CASE WHEN dpd > 90 THEN principal_kzt ELSE 0 END        AS par90_kzt,
       CASE WHEN is_npl THEN principal_kzt ELSE 0 END          AS npl_kzt,
       CASE WHEN is_restructured THEN principal_kzt ELSE 0 END AS restructured_kzt
FROM rated r;