import subprocess
import json
import os

def export_psql_json(query, filename):
    clean_query = query.strip().rstrip(';')
    cmd = [
        "docker", "exec", "risk_summary_db",
        "psql", "-U", "user", "-d", "risk_db",
        "-t", "-A", "-c", f"SELECT json_agg(t) FROM ({clean_query}) t"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        print(f"Error exporting {filename}: {result.stderr}")
        return
    try:
        stdout = result.stdout.strip()
        if not stdout: data = []
        else: data = json.loads(stdout)
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Exported to {filename}")
    except json.JSONDecodeError:
        print(f"Failed to parse JSON for {filename}: {result.stdout}")

def main():
    # Cleanup
    for f in ['dashboard/data/metrics.json', 'dashboard/data/segments.json', 'dashboard/specs/kpis.json']:
        try: os.remove(f)
        except: pass

    # 1. Industry
    export_psql_json("""
    SELECT industry as segment, to_char(snapshot_date, 'DD.MM') as snapshot_label, npl_rate, par30_rate, portfolio_kzt
    FROM (
        SELECT industry, snapshot_date, SUM(principal_kzt) as portfolio_kzt,
               SUM(CASE WHEN dpd > 90 OR is_restructured THEN principal_kzt ELSE 0 END) / NULLIF(SUM(principal_kzt), 0) as npl_rate,
               SUM(CASE WHEN dpd > 30 THEN principal_kzt ELSE 0 END) / NULLIF(SUM(principal_kzt), 0) as par30_rate
        FROM reporting.v_loans_clean GROUP BY 1, 2
    ) t ORDER BY industry, snapshot_date
    """, 'dashboard/data/industry.json')

    # 2. Program
    export_psql_json("""
    SELECT program as segment, to_char(snapshot_date, 'DD.MM') as snapshot_label, npl_rate, par30_rate, portfolio_kzt
    FROM (
        SELECT program, snapshot_date, SUM(principal_kzt) as portfolio_kzt,
               SUM(CASE WHEN dpd > 90 OR is_restructured THEN principal_kzt ELSE 0 END) / NULLIF(SUM(principal_kzt), 0) as npl_rate,
               SUM(CASE WHEN dpd > 30 THEN principal_kzt ELSE 0 END) / NULLIF(SUM(principal_kzt), 0) as par30_rate
        FROM reporting.v_loans_clean GROUP BY 1, 2
    ) t ORDER BY program, snapshot_date
    """, 'dashboard/data/program.json')

    # 4. Trend
    export_psql_json("""
    SELECT metric, to_char(snapshot_date, 'DD.MM') as snapshot_label, value
    FROM (
        SELECT 'PAR30' as metric, snapshot_date, par30_rate as value FROM reporting.v_metrics
        UNION ALL
        SELECT 'PAR90', snapshot_date, par90_rate FROM reporting.v_metrics
        UNION ALL
        SELECT 'NPL', snapshot_date, npl_rate FROM reporting.v_metrics
        UNION ALL
        SELECT 'Покрытие', snapshot_date, coverage_rate FROM reporting.v_metrics
    ) t ORDER BY metric, snapshot_date
    """, 'dashboard/data/trend.json')

    # 5. Concentration
    export_psql_json("""
    SELECT to_char(snapshot_date, 'DD.MM') as snapshot_label,
           SUM(principal_kzt) / (SELECT SUM(principal_kzt) FROM reporting.v_loans_clean l2 WHERE l2.snapshot_date = l1.snapshot_date) as ratio
    FROM reporting.v_loans_clean l1
    WHERE (group_id, snapshot_date) IN (
        SELECT group_id, snapshot_date FROM (
            SELECT group_id, snapshot_date, ROW_NUMBER() OVER (PARTITION BY snapshot_date ORDER BY SUM(principal_kzt) DESC) as rn
            FROM reporting.v_loans_clean GROUP BY 1, 2
        ) t WHERE rn <= 10
    )
    GROUP BY 1, snapshot_date
    """, 'dashboard/data/concentration.json')

if __name__ == '__main__':
    main()
