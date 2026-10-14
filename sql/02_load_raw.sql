DROP TABLE IF EXISTS raw.portfolio CASCADE;
CREATE TABLE raw.portfolio (
    report_date text, loan_id text, borrower_id text, group_id text, sector text, 
    program text, currency text, issue_date text, maturity_date text, 
    principal_outstanding text, days_past_due text, restructured text, written_off text
);
\copy raw.portfolio FROM '/app/data/portfolio.csv' WITH (FORMAT csv, HEADER true);

DROP TABLE IF EXISTS raw.fx CASCADE;
CREATE TABLE raw.fx (
    snapshot_date text, currency text, fx_rate text
);
\copy raw.fx FROM '/app/data/fx.csv' WITH (FORMAT csv, HEADER true);
