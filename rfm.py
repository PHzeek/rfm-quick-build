"""Quick Build #1 — RFM segments from a real order export.

Run: uv run python rfm.py
Fill in the five TODOs. rfm_solution.py has the answers — try first, then compare."""
import time 
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

RAW = Path("data/online_retail_II.xlsx")
CACHE = Path("data/orders.parquet")
OUT = Path("outputs")


def load_orders() -> pd.DataFrame:
    if CACHE.exists():
        return pd.read_parquet(CACHE)
    sheets = pd.read_excel(RAW, sheet_name=None)      # every sheet, whatever it's named
    df = pd.concat(sheets.values(), ignore_index=True)
    for col in ["Invoice", "StockCode", "Description", "Country"]:
        df[col] = df[col].astype("string")
    df.to_parquet(CACHE)
    return df


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    report = {"raw rows": len(df)}
    df = df.drop_duplicates();                            report["exact duplicates"] = report["raw rows"] - len(df)
    n = len(df); df = df[df["Customer ID"].notna()];      report["no customer ID"] = n - len(df)
    inv_mask = df["Invoice"].str.startswith("C")
    n = len(df); df = df[~inv_mask]; report["cancellations"] = n - len(df)
    qp_mask = (df["Quantity"] <= 0) | (df["Price"] <= 0)
    n = len(df); df = df[~qp_mask]; report["zero/negative qty or price"] = n - len(df)
    # TODO 1: drop cancellations — invoices whose number starts with "C".
    #         Follow the pattern above: record n, filter, then report["cancellations"] = n - len(df)

    # TODO 2: drop rows where Quantity <= 0 or Price <= 0.
    #         Record the count as report["zero/negative qty or price"]
    df = df.assign(Revenue=df["Quantity"] * df["Price"], **{"Customer ID": df["Customer ID"].astype(int)})
    report["clean rows"] = len(df)
    return df, report


def compute_rfm(df: pd.DataFrame) -> pd.DataFrame:
    snapshot = df["InvoiceDate"].max() + pd.Timedelta(days=1)
    rfm = df.groupby("Customer ID").agg(
        Recency=("InvoiceDate", lambda d: (snapshot - d.max()).days),
        Frequency=("Invoice", "nunique"),
        Monetary=("Revenue", "sum"),
    )
    # TODO 3: one row per customer with three columns:
    #   Recency   = days between `snapshot` and that customer's most recent InvoiceDate
    #   Frequency = number of distinct invoices (not rows — one invoice has many lines)
    #   Monetary  = total Revenue
    # Hint: df.groupby("Customer ID").agg(Recency=("InvoiceDate", ...), Frequency=(...), Monetary=(...))
    return rfm


def score_rfm(rfm: pd.DataFrame) -> pd.DataFrame:
    rfm = rfm.copy()
    rfm["R"] = pd.qcut(rfm["Recency"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
    rfm["F"] = pd.qcut(rfm["Frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["M"] = pd.qcut(rfm["Monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    # TODO 4: score F and M the same way — but notice the labels flip.
    #   For Recency, FEWER days is better, so the labels run 5 → 1.
    #   For Frequency and Monetary, MORE is better, so they run 1 → 5.
    return rfm 


def name_segment(r: int, f: int, m: int) -> str:
    if r >= 4 and f>= 4:
        return "Champions"
    if r <= 2 and (f >= 4 or m >= 4):
        return "At Risk"
    if r >= 4 and f <= 2:
        return "Promising"
    if r <= 2 and f <= 2:
        return "Lost"
    # TODO 5: add the three segments from the Day 10 post, in this order:
    #   "At risk"   — haven't bought lately (r <= 2) but used to buy often OR spend a lot (f >= 4 or m >= 4)
    #   "Promising" — bought recently (r >= 4) but only once or twice (f <= 2)
    #   "Lost"      — not recent (r <= 2) and rarely bought (f <= 2)
    # Order matters: a customer matches the FIRST rule that fits.
    return "Steady"


def summarize(rfm: pd.DataFrame) -> pd.DataFrame:
    s = rfm.groupby("Segment").agg(customers=("Monetary", "size"), revenue=("Monetary", "sum"))
    s["% customers"] = (100 * s["customers"] / s["customers"].sum()).round(1)
    s["% revenue"]  = (100 * s["revenue"] / s["revenue"].sum()).round(1)
    s["revenue"] = s["revenue"].round().astype(int)
    return s.sort_values("revenue", ascending=False)


def plot(summary: pd.DataFrame) -> Path:
    OUT.mkdir(exist_ok=True)
    ax = summary[["% customers", "% revenue"]].plot.barh(figsize=(8, 4.5))
    ax.invert_xaxis(); ax.set_xlabel("%"); ax.set_title("Share of customers vs. share of revenue, by RFM segment")
    plt.tight_layout; path = OUT / "rfm_segment.png"; plt.savefig(path, dpi=200); plt.close()
    return path


if __name__ == "__main__":
    t0 = time.perf_counter()
    orders = load_orders()
    orders, report = clean(orders)
    for k, v in report.items():
        print(f"{k:>28}: {v:,}")
    rfm = score_rfm(compute_rfm(orders))
    rfm["Segment"] = [name_segment(r, f, m) for r, f, m in zip(rfm["R"], rfm["F"], rfm["M"])]
    summary = summarize(rfm)
    print("\n", summary.to_string())
    OUT.mkdir(exist_ok=True); rfm.to_csv(OUT / "rfm_customers.csv")
    print("\nchart:", plot(summary), f"| customers: {len(rfm):,} | {time.perf_counter() - t0:.1f}s")




