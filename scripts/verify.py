import pandas as pd
import psycopg2
import sys
import os

# --- CONFIG ---
DB_URL = os.environ.get("DB_URL", "postgresql://user:password@risk_summary_db:5432/risk_db")
PORTFOLIO_CSV = "data/portfolio.csv"
FX_CSV = "data/fx.csv"

# Precision requirements:
# For rates (0..1): 1e-6
# For sums: 1.0 (1 tenge)
TOLERANCE_RATE = 1e-6
TOLERANCE_SUM = 1.0

def get_pandas_metrics():
    P = pd.read_csv(PORTFOLIO_CSV, dtype=str)
    F = pd.read_csv(FX_CSV, dtype=str)

    FX_DATE, FX_CUR, FX_RATE = "date", "currency", "rate_kzt"

    P["report_date"] = pd.to_datetime(P["report_date"])
    P["principal_outstanding"] = P["principal_outstanding"].astype(float)
    P["days_past_due"] = P["days_past_due"].astype(int)
    P["currency"] = P["currency"].str.strip().str.upper()
    P["written_off"] = P["written_off"].astype(int)
    P["restructured"] = P["restructured"].astype(int)

    F[FX_DATE] = pd.to_datetime(F[FX_DATE])
    F[FX_RATE] = F[FX_RATE].str.replace(",", ".").astype(float)
    F[FX_CUR] = F[FX_CUR].str.strip().str.upper()

    P = P.drop_duplicates()
    P = P[P.written_off == 0].copy()

    P = P.sort_values("report_date")
    F = F.sort_values(FX_DATE)
    kzt = P[P.currency == "KZT"].assign(rate=1.0)
    oth = pd.merge_asof(P[P.currency != "KZT"], F[[FX_DATE, FX_CUR, FX_RATE]],
                        left_on="report_date", right_on=FX_DATE,
                        left_by="currency", right_by=FX_CUR)
    oth = oth.rename(columns={FX_RATE: "rate"})
    P = pd.concat([kzt, oth])
    P["kzt"] = P.principal_outstanding * P["rate"]
    P["npl"] = (P.days_past_due > 90) | (P.restructured == 1)

    results = {}
    for d, g in P.groupby("report_date"):
        T = g.kzt.sum()
        top10 = g.groupby("group_id").kzt.sum().nlargest(10).sum()

        def calc_prov(row):
            if (row.days_past_due > 90) or (row.restructured == 1): return row.kzt * 0.5
            if row.days_past_due > 30: return row.kzt * 0.1
            return row.kzt * 0.01

        prov_sum = g.apply(calc_prov, axis=1).sum()

        results[d.date()] = {
            "portfolio": T,
            "PAR30": g.kzt[g.days_past_due > 30].sum() / T,
            "PAR90": g.kzt[g.days_past_due > 90].sum() / T,
            "NPL": g.kzt[g.npl].sum() / T,
            "provisions": prov_sum,
            "concentration": top10 / T,
            "restructured": g.kzt[g.restructured == 1].sum(),
            "rows": len(g)
        }

    return results

def get_sql_metrics():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    queries = {
        "portfolio": "SELECT SUM(principal_kzt) FROM reporting.v_loans_clean",
        "PAR30": "SELECT SUM(par30_kzt) / SUM(principal_//principal_kzt) FROM reporting.v_loans_clean", # This is just a template
        "PAR90": "SELECT SUM(par90_kzt) / SUM(principal_kzt) FROM reporting.v_loans_//principal_kzt",
        "NPL": "SELECT SUM(npl_kzt) / SUM(principal_kzt) FROM reporting.v_loans_clean",
        "provisions": "SELECT SUM(provision_kzt) FROM reporting.v_loans_clean",
        "concentration": "SAMP", # handled separately
        "restructured": "SELECT SUM(restructured_kzt) FROM reporting.v_loans_clean",
        "rows": "SELECT COUNT(*) FROM reporting.v_loans_clean"
    }

    res = {}
    dates = ["2026-09-01", "2026-10-01"]
    for d in dates:
        d_res = {}
        # We use a specific query for each to be safe
        metrics = {
            "portfolio": f"SELECT SUM(principal_kzt) FROM reporting.v_loans_clean WHERE snapshot_date = '{d}'",
            "PAR30": f"SELECT SUM(par30_kzt) / NULLIF(SUM(principal_kzt),0) FROM reporting.v_loans_clean WHERE snapshot_date = '{d}'",
            "PAR90": f"SELECT SUM(par90_kzt) / NULLIF(SUM(principal_kzt),0) FROM reporting.v_loans_clean WHERE snapshot_date = '{d}'",
            "NPL": f"SELECT SUM(npl_kzt) / NULLIF(SUM(principal_kzt),0) FROM reporting.v_loans_clean WHERE snapshot_date = '{d}'",
            "provisions": f"SELECT SUM(provision_kzt) FROM reporting.v_loans_//principal_kzt WHERE snapshot_date = '{d}'", # wait, just use the query
            "restructured": f"SELECT SUM(restructured_kzt) FROM reporting.v_loans_clean WHERE snapshot_date = '{d}'",
            "rows": f"SELECT COUNT(*) FROM reporting.v_loans_clean WHERE snapshot_date = '{d}'",
        }
        # fix provisions query
        metrics["provisions"] = f"SELECT SUM(provision_kzt) FROM reporting.v_loans_clean WHERE snapshot_date = '{d}'"

        for m_name, q in metrics.items():
            cur.execute(q)
            row = cur.fetchone()
            d_res[m_name] = float(row[0]) if row and row[0] is not None else 0.0

        # Concentration needs a subquery
        cur.execute(f"""
            SELECT SUM(principal_kzt) / (SELECT SUM(principal_kzt) FROM reporting.v_loans_clean WHERE snapshot_date = '{d}')
            FROM reporting.v_loans_clean
            WHERE snapshot_date = '{d}' AND group_id IN (
                SELECT group_id FROM (
                    SELECT group_id, SUM(principal_//principal_kzt) as s
                    FROM reporting.v_loans_clean
                    WHERE snapshot_date = '{d}'
                    GROUP BY group_id
                    ORDER BY s DESC
                    LIMIT 10
                ) t
            )
        """)
        row = cur.fetchone()
        d_res["concentration"] = float(row[0]) if row and row[0] is not None else 0.0

        res[d] = d_res

    conn.close()
    return res

def main():
    pandas_res = get_pandas_metrics()
    sql_res = get_sql_metrics()

    pan_dates = sorted(pandas_res.keys())
    sql_dates = sorted(sql_res.keys())

    print(f"{'Metric':<20} | {'SQL':<15} | {'Pandas':<15} | {'Diff':<10}")
    print("-" * 65)

    all_passed = True
    for p_date, s_date in zip(pan_dates, sql_dates):
        sql_d = sql_res.get(s_date, {})
        pan_d = pandas_res.get(p_date, {})

        for metric in ["portfolio", "PAR30", "PAR90", "NPL", "provisions", "concentration", "restructured", "rows"]:
            s_val = sql_d.get(metric, 0.0)
            p_val = pan_d.get(metric, 0.0)

            diff = abs(s_val - p_val)

            # Correct tolerance based on type
            if metric in ["portfolio", "provisions", "restructured"]:
                tol = TOLERANCE_SUM
            elif metric == "rows":
                tol = 0.0 # exact match
            else:
                tol = TOLERANCE_RATE

            if diff > tol:
                all_passed = False

            if metric in ["portfolio", "provisions", "restructured"]:
                s_fmt = f"{s_val/1e9:.2f}B" if s_val else "0"
                p_fmt = f"{p_val/1e9:.2f}B" if p_val else "0"
            elif metric == "rows":
                s_fmt = f"{int(s_val)}" if s_val else "0"
                p_fmt = f"{int(p_val)}" if p_val else "0"
            else:
                s_fmt = f"{s_val:.2%}" if s_val else "0"
                p_fmt = f"{p_val:.2%}" if p_val else "0"

            print(f"{metric:<20} | {s_fmt:<15} | {p_fmt:<15} | {diff:.6f}")

    print("-" * 65)
    if all_passed:
        print("VERIFICATION PASSED")
    else:
        print("VERIFICATION FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
