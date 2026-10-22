"""Quick Build #2 — the churn-rhythm column.

For every customer: days since their last order ÷ their usual gap between orders.
Above 2 means they're drifting. Reuses load_orders() and clean() from rfm.py.

Run: uv run python rhythm.py
"""
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from rfm import OUT, clean, compute_rfm, load_orders

LABELS = ["On rhythm", "Slipping", "Drifting", "One-time buyer"]


def one_row_per_order(df: pd.DataFrame) -> pd.DataFrame:
    df = df[["Customer ID", "Invoice", "InvoiceDate"]].drop_duplicates(subset=["Customer ID", "Invoice"]).sort_values(["Customer ID", "InvoiceDate"])
    return df


def add_gaps(orders: pd.DataFrame) -> pd.DataFrame:
    orders = orders.copy()
    orders["gap_days"] = orders.groupby("Customer ID")["InvoiceDate"].diff().dt.days
    return orders


def compute_rhythm(orders: pd.DataFrame, snapshot: pd.Timestamp) -> pd.DataFrame:
    r = orders.groupby("Customer ID").agg(
        orders=("Invoice", "nunique"),
        last_order=("InvoiceDate", "max"),
        usual_gap=("gap_days", "median")
    )
    r["days_since"] = (snapshot - r["last_order"]).dt.days
    r["usual_gap"] = r["usual_gap"].clip(lower=1)        # same-day repeat orders have a 0-day gap
    r["ratio"] = round(r["days_since"] / r["usual_gap"], 2)
    # TODO 3b: r["ratio"] = days_since ÷ usual_gap, rounded to 2 decimals
    return r


def rhythm_label(ratio: float) -> str:
    if pd.isna(ratio):
        return "One-time buyer"
    if ratio <= 1:
        return "On rhythm"
    if ratio <= 2:
        return "Slipping"
    else:
        return "Drifting"


def summarize(r: pd.DataFrame) -> pd.DataFrame:
    s = r.groupby("Rhythm").agg(customers=("ratio", "size"), revenue=("Monetary", "sum")).reindex(LABELS).fillna(0)
    s["% customers"] = (100 * s["customers"] / s["customers"].sum()).round(1)
    s["% revenue"] = (100 * s["revenue"] / s["revenue"].sum()).round(1)
    s["revenue"] = s["revenue"].round().astype(int)
    s["customers"] = s["customers"].astype(int)
    return s


def plot(summary: pd.DataFrame):
    OUT.mkdir(exist_ok=True)
    ax = summary[["% customers", "% revenue"]].plot.barh(figsize=(8, 4.5))
    ax.invert_yaxis(); ax.set_xlabel("%"); ax.set_title("Customers vs revenue, by order rhythm")
    plt.tight_layout(); path = OUT / "rhythm.png"; plt.savefig(path, dpi=200); plt.close()
    return path


if __name__ == "__main__":
    t0 = time.perf_counter()
    df, _ = clean(load_orders())
    snapshot = df["InvoiceDate"].max() + pd.Timedelta(days=1)
    orders = add_gaps(one_row_per_order(df))
    r = compute_rhythm(orders, snapshot).join(compute_rfm(df)["Monetary"])
    r["Rhythm"] = r["ratio"].map(rhythm_label)
    print(f"order lines: {len(df):,} → orders: {len(orders):,} → customers: {len(r):,}\n")
    summary = summarize(r)
    print(summary.to_string())
    calls = r[r["Rhythm"] == "Drifting"].sort_values("Monetary", ascending=False).head(10)
    print("\nTop 10 drifting customers by past spend — this week's call list:")
    print(calls[["orders", "usual_gap", "days_since", "ratio", "Monetary"]].round(1).to_string())
    OUT.mkdir(exist_ok=True); r.to_csv(OUT / "rhythm_customers.csv")
    print("\nchart:", plot(summary), f"| {time.perf_counter() - t0:.1f}s")
