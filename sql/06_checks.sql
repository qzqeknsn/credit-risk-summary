DO $$
DECLARE
    v_null_fx BOOLEAN;
    v_bounds_error BOOLEAN;
    v_hierarchy_error BOOLEAN;
    v_duplicates_error BOOLEAN;
    v_rates_error BOOLEAN;
BEGIN
    -- 1. Нет NULL в курсах
    SELECT EXISTS (SELECT 1 FROM raw.fx WHERE rate_kzt IS NULL) INTO v_null_fx;
    IF v_null_fx THEN RAISE EXCEPTION 'DATA_ERROR: NULL values found in fx.rate_kzt'; END IF;

    -- 2. Доли в диапазоне [0; 1]
    SELECT EXISTS (
        SELECT 1 FROM reporting.v_metrics
        WHERE par30_d1 NOT BETWEEN 0 AND 1 OR par30_d2 NOT BETWEEN 0 AND 1
        OR npl_d1 NOT BETWEEN 0 AND 1 OR npl_d2 NOT BETWEEN 0 AND 1
    ) INTO v_bounds_error;
    IF v_bounds_error THEN RAISE EXCEPTION 'DATA_ERROR: Metric rates outside [0, 1] range'; END IF;

    -- 3. Иерархия просрочки: PAR90 <= PAR30 <= 1
    SELECT EXISTS (
        SELECT 1 FROM reporting.v_loans_clean
        WHERE par90_kzt > par30_kzt
        OR par30_kzt > principal_kzt
    ) INTO v_hierarchy_error;
    IF v_hierarchy_error THEN RAISE EXCEPTION 'DATA_ERROR: Hierarchy violation: PAR90 > PAR30 or PAR30 > Principal'; END IF;

    -- 4. Нет дублей (loan_id, snapshot_date)
    SELECT EXISTS (
        SELECT 1 FROM reporting.v_loans_clean
        GROUP BY loan_id, snapshot_date
        HAVING COUNT(*) > 1
    ) INTO v_duplicates_error;
    IF v_duplicates_error THEN RAISE EXCEPTION 'DATA_ERROR: Duplicate loan_id found for the same snapshot_date'; END IF;

    -- 5. Курсы строго > 0
    SELECT EXISTS (SELECT 1 FROM raw.fx WHERE rate_kzt <= 0) INTO v_rates_error;
    IF v_rates_error THEN RAISE EXCEPTION 'DATA_ERROR: Non-positive FX rates found'; END IF;

END $$;
