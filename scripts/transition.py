from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
P = pd.read_csv(ROOT / "data/portfolio.csv")
F = pd.read_csv(ROOT / "data/fx.csv")
P["report_date"] = pd.to_datetime(P["report_date"])
F["date"] = pd.to_datetime(F["date"])
D1, D2 = pd.Timestamp("2026-09-01"), pd.Timestamp("2026-10-01")

# дедупликация, курс as-of на дату среза (KZT = 1)
P = P.drop_duplicates()
F = F.sort_values("date")
parts = []
for cur, g in P.groupby("currency"):
    g = g.sort_values("report_date")
    if cur == "KZT":
        g = g.assign(rate=1.0)
    else:
        g = pd.merge_asof(g, F[F.currency == cur][["date", "rate_kzt"]],
                          left_on="report_date", right_on="date").rename(columns={"rate_kzt": "rate"})
    parts.append(g)
P = pd.concat(parts)
assert P["rate"].notna().all(), "нет курса"
P["kzt"] = P["principal_outstanding"] * P["rate"]

wo_oct = set(P[(P.report_date == D2) & (P.written_off == 1)].loan_id)
C = P[P.written_off == 0]                       # очищенная витрина
a = C[C.report_date == D1].set_index("loan_id")
b = C[C.report_date == D2].set_index("loan_id")
a90 = a[a.days_past_due > 90]
b90 = b[b.days_past_due > 90]

rows = []
def add(name, ids, with_fx=False):
    s1 = a.loc[a.index.intersection(ids), "kzt"].sum() if len(ids) else 0
    inb = b.index.intersection(ids)
    s2 = b.loc[inb, "kzt"].sum() if len(inb) else 0
    fx = "—"
    both = a.index.intersection(b.index).intersection(ids)
    if with_fx and len(both):
        fx = (a.loc[both, "principal_outstanding"] * (b.loc[both, "rate"] - a.loc[both, "rate"])).sum() / 1e9
    rows.append((name, len(ids), s1 / 1e9, s2 / 1e9, fx))

ids = set(a90.index)
stay = {i for i in ids if i in b90.index}
ret = {i for i in ids if i in b.index and i not in b90.index}
gone = ids - set(b.index)
add("(а) остались dpd>90", stay, True)
add("(б) вернулись в dpd<=90", ret, True)
add("(в1) исчезли: списаны (written_off=1 на 01.10)", {i for i in gone if i in wo_oct})
add("(в2) исчезли: нет в данных на 01.10", {i for i in gone if i not in wo_oct})
inflow = set(b90.index) - ids
add("(г1) приток: были в витрине 01.09 с dpd<=90", {i for i in inflow if i in a.index})
add("(г2) приток: не было в витрине 01.09", {i for i in inflow if i not in a.index})

T = pd.DataFrame(rows, columns=["корзина", "кредитов", "сумма 01.09, млрд", "сумма 01.10, млрд", "эффект курса, млрд"])
pd.set_option("display.width", 200)
print(T.round(3).to_string(index=False))
print("\nпроверка: 01.10 в корзине dpd>90 (а + г) =", round(b90.kzt.sum() / 1e9, 2), "(эталон 21.64)")
print("проверка: 01.09 в корзине dpd>90 (а + б + в) =", round(a90.kzt.sum() / 1e9, 2), "(эталон 31.10)")
print("из (б) restructured=1 на 01.10:", int((b.loc[list(ret), "restructured"] == 1).sum()), "из", len(ret))

g2 = [i for i in inflow if i not in a.index]
raw1 = P[(P.report_date == D1) & P.loan_id.isin(g2)]
print("\n(г2): есть в сырых данных на 01.09:", raw1.loan_id.nunique(), "из них списаны:", int((raw1.written_off == 1).sum()))
print(b.loc[g2, ["issue_date", "days_past_due", "kzt"]].sort_values("issue_date").to_string())
r = b.loc[list(ret)]
print("\n(б) на 01.10 по корзинам dpd:")
print(pd.cut(r.days_past_due, [-1, 0, 30, 90]).value_counts().sort_index())
print("сумма (б) с dpd 31-90, млрд:", round(r[r.days_past_due > 30].kzt.sum() / 1e9, 2))