import json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def q(sql):
    out = subprocess.run(
        ["docker", "exec", "-i", "risk_summary_db", "psql", "-U", "user", "-d", "risk_db",
         "-t", "-A", "-F", ",", "-c", sql],
        capture_output=True, text=True, check=True).stdout.strip().splitlines()
    return [r.split(",") for r in out]

m = {r[0]: [float(x) for x in r[1:]] for r in q("""
    SELECT snapshot_date, SUM(principal_kzt), SUM(par30_kzt), SUM(par90_kzt),
           SUM(npl_kzt), SUM(provision_kzt)
    FROM reporting.v_loans_clean GROUP BY 1 ORDER BY 1""")}
c = {r[0]: float(r[1]) for r in q("""
    SELECT snapshot_date, SUM(s) FROM (
      SELECT snapshot_date, SUM(principal_kzt) s,
             ROW_NUMBER() OVER (PARTITION BY snapshot_date ORDER BY SUM(principal_kzt) DESC) rn
      FROM reporting.v_loans_clean GROUP BY snapshot_date, group_id) t
    WHERE rn <= 10 GROUP BY 1""")}

d1, d2 = sorted(m)
a, b = m[d1], m[d2]
RED, GREEN, GRAY = "#c53030", "#2f855a", "#718096"

def sign(x): return "+" if x > 0 else "−" if x < 0 else ""
def pct_delta(x, y):                       # для сумм, в %
    v = (y / x - 1) * 100
    return f"{sign(round(v, 1))}{abs(v):.1f}%"
def pp_delta(x, y, risk_up_is_bad=True):   # для долей, в п.п.
    v = (y - x) * 100
    if round(v, 1) == 0:
        return "0.0 п.п.", GRAY
    bad = (v > 0) == risk_up_is_bad
    return f"{sign(v)}{abs(v):.1f} п.п.", RED if bad else GREEN

rows = [(1, "Портфель", f"{b[0]/1e9:.1f} млрд ₸", pct_delta(a[0], b[0]), GRAY)]
for i, (name, k, bad) in enumerate([("PAR30", 1, True), ("PAR90", 2, True), ("NPL", 3, True)], 2):
    t, col = pp_delta(a[k]/a[0], b[k]/b[0], bad)
    rows.append((i, name, f"{b[k]/b[0]*100:.1f}%", t, col))
rows.append((5, "Провизии", f"{b[4]/1e9:.1f} млрд ₸", pct_delta(a[4], b[4]), GRAY))
t, col = pp_delta(a[4]/a[0], b[4]/b[0], False)           # покрытие вниз = красный
rows.append((6, "Покрытие", f"{b[4]/b[0]*100:.2f}%", t, col))
t, col = pp_delta(c[d1]/a[0], c[d2]/b[0], True)
rows.append((7, "Концентрация топ-10", f"{c[d2]/b[0]*100:.1f}%", t, col))

out = [dict(order=o, label=l, value_text=v, delta_text=dt, delta_color=dc) for o, l, v, dt, dc in rows]
(ROOT / "dashboard/data/kpi.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(json.dumps(out, ensure_ascii=False, indent=1))