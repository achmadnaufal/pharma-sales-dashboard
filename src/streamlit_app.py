"""
Streamlit entry-point for the Pharma Sales Dashboard.

Run with:

    streamlit run src/streamlit_app.py

The app is organized into four tabs:

1. **Overview** - headline KPIs and territory summary
2. **Rep Leaderboard** - ranked reps by revenue or unit sales
3. **YoY Growth** - year-over-year growth per territory and product
4. **Cohort Comparison** - side-by-side revenue comparison for two groups

All data mutation is kept out of this module; the heavy lifting lives in
:mod:`src.main` and :mod:`src.metrics`.  This file is intentionally thin so
the analytical layer remains testable without a Streamlit runtime.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    import streamlit as st  # type: ignore
except ImportError:  # pragma: no cover - only hit when streamlit missing
    st = None  # allows this module to be imported for syntax checks in CI

from src.main import PharmaSalesDashboard, aggregate_by_territory, filter_time_series
from src.metrics import (
    add_attainment_columns,
    cohort_comparison,
    filter_by_period,
    rank_reps,
    yoy_growth_by_group,
)


DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "demo" / "sample_data.csv"


def load_frame(path: Path) -> pd.DataFrame:
    """Load, validate, and preprocess a pharma sales CSV/Excel file.

    Args:
        path: Absolute or relative filesystem path.

    Returns:
        Preprocessed DataFrame ready for metric computation.  Returns an
        empty DataFrame if the file cannot be loaded.
    """
    dashboard = PharmaSalesDashboard()
    try:
        raw = dashboard.load_data(str(path))
        dashboard.validate(raw)
        return dashboard.preprocess(raw)
    except (FileNotFoundError, ValueError):
        return pd.DataFrame()


def _require_streamlit() -> None:
    """Raise a helpful error if streamlit is not installed."""
    if st is None:  # pragma: no cover
        raise RuntimeError(
            "streamlit is not installed. Install with: pip install streamlit"
        )


def render_overview_tab(df: pd.DataFrame) -> None:
    """Render the Overview tab content."""
    _require_streamlit()
    st.subheader("Headline KPIs")

    if df.empty:
        st.warning("No data loaded. Upload a CSV to begin.")
        return

    total_revenue = float(df.get("revenue_usd", pd.Series(dtype=float)).sum())
    total_units = float(df.get("units_sold", pd.Series(dtype=float)).sum())
    total_target = float(df.get("target_units", pd.Series(dtype=float)).sum())
    attainment = round(total_units / total_target * 100, 2) if total_target > 0 else 0.0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total revenue (USD)", f"${total_revenue:,.0f}")
    col2.metric("Total units sold", f"{total_units:,.0f}")
    col3.metric("Unit attainment", f"{attainment:.1f}%")

    st.subheader("Territory summary")
    territory_df = aggregate_by_territory(df)
    if territory_df.empty:
        st.info("Territory column not available in this dataset.")
    else:
        st.dataframe(territory_df, use_container_width=True)


def render_leaderboard_tab(df: pd.DataFrame) -> None:
    """Render the Rep Leaderboard tab."""
    _require_streamlit()
    st.subheader("Rep leaderboard")

    if df.empty or "rep_id" not in df.columns:
        st.warning("Rep-level data unavailable.")
        return

    metric_choices = [c for c in ("revenue_usd", "units_sold", "calls_made") if c in df.columns]
    if not metric_choices:
        st.warning("No rankable numeric metric present.")
        return

    metric = st.selectbox("Rank by metric", metric_choices)
    top_n = st.slider("Top N", min_value=3, max_value=max(3, df["rep_id"].nunique()), value=5)
    ranked = rank_reps(df, metric=metric, top_n=top_n)
    st.dataframe(ranked, use_container_width=True)


def render_yoy_tab(df: pd.DataFrame) -> None:
    """Render the Year-over-Year growth tab."""
    _require_streamlit()
    st.subheader("Year-over-year growth")

    if df.empty or "year" not in df.columns:
        st.info("Year column required for YoY analysis.")
        return

    group_choices = [c for c in ("territory", "product_name", "rep_id") if c in df.columns]
    if not group_choices:
        st.warning("No grouping column available.")
        return

    group = st.selectbox("Group by", group_choices)
    growth_df = yoy_growth_by_group(df, group_column=group, metric="revenue_usd")
    if growth_df.empty:
        st.info("Need at least two distinct years in the data to compute YoY growth.")
    else:
        st.dataframe(growth_df, use_container_width=True)


def render_cohort_tab(df: pd.DataFrame) -> None:
    """Render the Cohort Comparison tab."""
    _require_streamlit()
    st.subheader("Cohort comparison")

    if df.empty:
        st.warning("Load data to compare cohorts.")
        return

    cohort_choices = [c for c in ("territory", "product_name", "therapeutic_area") if c in df.columns]
    if not cohort_choices:
        st.info("No cohort column available in dataset.")
        return

    cohort_col = st.selectbox("Cohort column", cohort_choices)
    values = sorted(df[cohort_col].dropna().unique().tolist())
    if len(values) < 2:
        st.info("Need at least two distinct values to compare cohorts.")
        return

    col_a, col_b = st.columns(2)
    cohort_a = col_a.selectbox("Cohort A", values, index=0)
    cohort_b = col_b.selectbox("Cohort B", values, index=1)

    result = cohort_comparison(df, cohort_col, cohort_a, cohort_b, metric="revenue_usd")
    st.json(result)


def main() -> None:
    """Streamlit app entry-point."""
    _require_streamlit()
    st.set_page_config(page_title="Pharma Sales Dashboard", layout="wide")
    st.title("Pharma Sales Dashboard")
    st.caption("Sales performance for pharmaceutical field teams")

    uploaded = st.sidebar.file_uploader("Upload sales CSV", type=["csv", "xlsx", "xls"])
    if uploaded is not None:
        df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
        df = PharmaSalesDashboard().preprocess(df)
    else:
        df = load_frame(DEFAULT_DATA_PATH)

    df = add_attainment_columns(df)

    # Optional period filter
    if "month" in df.columns:
        all_months = sorted(df["month"].dropna().unique().tolist(), key=str.lower)
        selected = st.sidebar.multiselect("Months", all_months, default=all_months)
        if selected and len(selected) != len(all_months):
            df = filter_by_period(df, months=selected)

    tabs = st.tabs(["Overview", "Rep Leaderboard", "YoY Growth", "Cohort Comparison"])
    with tabs[0]:
        render_overview_tab(df)
    with tabs[1]:
        render_leaderboard_tab(df)
    with tabs[2]:
        render_yoy_tab(df)
    with tabs[3]:
        render_cohort_tab(df)


if __name__ == "__main__":  # pragma: no cover
    main()
