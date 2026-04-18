"""
Additional pharma sales metrics and analytical helpers.

This module extends :mod:`src.main` with higher-level KPI functions used by
the Streamlit dashboard and downstream reporting:

- Revenue-based target attainment (dollar attainment rather than unit attainment)
- Year-over-year (YoY) growth at the DataFrame level
- Rep-ranking helper with configurable tie-breaking
- Cohort comparison between two slices of the same DataFrame
- Filter-by-period helper accepting a list of months or a (start, end) range
- Call effectiveness (revenue per call) and HCP coverage metrics

All helpers are pure functions - they never mutate their inputs and always
return a new DataFrame or scalar.  Division-by-zero, NaN, and empty-input
edge cases are handled explicitly.

Author: github.com/achmadnaufal
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Scalar metrics
# ---------------------------------------------------------------------------

def compute_revenue_attainment(revenue_usd: float, target_revenue_usd: float) -> float:
    """Compute revenue attainment as a percentage of target revenue.

    Dollar-based sibling of
    :func:`src.main.compute_target_achievement`.  Useful when pricing
    differences between products make unit-based attainment misleading.

    Args:
        revenue_usd: Actual revenue booked in the period, in USD.
        target_revenue_usd: Target revenue set for the period, in USD.

    Returns:
        Attainment percentage rounded to 2 decimal places.  Returns ``0.0``
        when ``target_revenue_usd`` is zero, negative, or NaN to avoid
        ``ZeroDivisionError`` / ``inf`` leaking into downstream UI.
    """
    if target_revenue_usd is None or pd.isna(target_revenue_usd):
        return 0.0
    if target_revenue_usd <= 0:
        return 0.0
    if revenue_usd is None or pd.isna(revenue_usd):
        return 0.0
    return round((revenue_usd / target_revenue_usd) * 100, 2)


def compute_yoy_growth(current_value: float, prior_value: float) -> Optional[float]:
    """Compute year-over-year growth as a percentage.

    Args:
        current_value: Value for the current period.
        prior_value: Value for the same period one year earlier.

    Returns:
        Growth rate as a percentage rounded to 2 decimal places
        (e.g., ``12.5`` for 12.5 % growth).  Returns ``None`` when
        ``prior_value`` is zero, negative, or NaN since the growth rate
        is undefined in those cases.  Returning ``None`` lets callers
        decide how to surface "not applicable" in the UI rather than
        hiding the anomaly behind a zero.
    """
    if prior_value is None or pd.isna(prior_value) or prior_value <= 0:
        return None
    if current_value is None or pd.isna(current_value):
        return None
    return round(((current_value - prior_value) / prior_value) * 100, 2)


def compute_revenue_per_call(revenue_usd: float, call_count: float) -> float:
    """Compute revenue per sales call (call effectiveness).

    Args:
        revenue_usd: Revenue booked by the rep.
        call_count: Number of calls made in the period.

    Returns:
        Revenue per call in USD, rounded to 2 decimals.  Returns ``0.0`` when
        ``call_count`` is zero, negative, or NaN.
    """
    if call_count is None or pd.isna(call_count) or call_count <= 0:
        return 0.0
    if revenue_usd is None or pd.isna(revenue_usd):
        return 0.0
    return round(revenue_usd / call_count, 2)


# ---------------------------------------------------------------------------
# DataFrame-level metrics
# ---------------------------------------------------------------------------

def add_attainment_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with attainment columns appended.

    Adds the following columns when the source columns are present:

    - ``unit_attainment_pct`` - ``units_sold`` / ``target_units`` * 100
    - ``revenue_attainment_pct`` - ``revenue_usd`` / ``target_revenue_usd`` * 100
    - ``call_attainment_pct`` - ``calls_made`` / ``calls_target`` * 100
    - ``revenue_per_call`` - ``revenue_usd`` / ``calls_made``

    Missing source columns are skipped silently.  All division edge cases
    (zero, negative, NaN denominator) are handled.

    Args:
        df: Sales DataFrame.

    Returns:
        A new DataFrame with attainment columns appended.  The input is not
        modified.
    """
    if df.empty:
        return df.copy()

    result = df.copy()

    if "units_sold" in result.columns and "target_units" in result.columns:
        result = result.assign(
            unit_attainment_pct=[
                _safe_pct(u, t) for u, t in zip(result["units_sold"], result["target_units"])
            ]
        )

    if "revenue_usd" in result.columns and "target_revenue_usd" in result.columns:
        result = result.assign(
            revenue_attainment_pct=[
                compute_revenue_attainment(r, t)
                for r, t in zip(result["revenue_usd"], result["target_revenue_usd"])
            ]
        )

    if "calls_made" in result.columns and "calls_target" in result.columns:
        result = result.assign(
            call_attainment_pct=[
                _safe_pct(c, t) for c, t in zip(result["calls_made"], result["calls_target"])
            ]
        )

    if "revenue_usd" in result.columns and "calls_made" in result.columns:
        result = result.assign(
            revenue_per_call=[
                compute_revenue_per_call(r, c)
                for r, c in zip(result["revenue_usd"], result["calls_made"])
            ]
        )

    return result


def rank_reps(
    df: pd.DataFrame,
    metric: str = "revenue_usd",
    top_n: Optional[int] = None,
    ascending: bool = False,
) -> pd.DataFrame:
    """Return reps ranked by an aggregate metric.

    Aggregates the metric per rep (sum) and returns a ranked DataFrame with
    columns ``rep_id``, ``rep_name`` (when present), ``<metric>``, and
    ``rank``.  Ties receive the same rank using the ``"min"`` method.

    Args:
        df: Input sales DataFrame.  Must contain a ``rep_id`` column and the
            metric column.
        metric: Numeric column to rank on.  Defaults to ``revenue_usd``.
        top_n: Optional cut-off - keep only the top ``n`` reps after
            ranking.  ``None`` keeps all rows.
        ascending: When ``True``, smaller values rank first (useful for
            under-performer reports).

    Returns:
        A new DataFrame sorted by rank ascending.  Empty DataFrame when
        ``df`` is empty or missing the required columns.

    Raises:
        ValueError: When ``top_n`` is not a positive integer.
    """
    if top_n is not None and (not isinstance(top_n, int) or top_n <= 0):
        raise ValueError("top_n must be a positive integer or None")

    if df.empty or "rep_id" not in df.columns or metric not in df.columns:
        return pd.DataFrame()

    group_cols = ["rep_id"]
    if "rep_name" in df.columns:
        group_cols.append("rep_name")

    aggregated = (
        df.groupby(group_cols, as_index=False)[metric]
        .sum()
        .sort_values(metric, ascending=ascending, kind="mergesort")
        .reset_index(drop=True)
    )
    aggregated = aggregated.assign(
        rank=aggregated[metric].rank(method="min", ascending=ascending).astype(int)
    )
    aggregated = aggregated.sort_values("rank", kind="mergesort").reset_index(drop=True)

    if top_n is not None:
        aggregated = aggregated.head(top_n).reset_index(drop=True)

    return aggregated


def cohort_comparison(
    df: pd.DataFrame,
    cohort_column: str,
    cohort_a: str,
    cohort_b: str,
    metric: str = "revenue_usd",
) -> dict:
    """Compare an aggregate metric between two cohorts.

    Example: compare total revenue for ``territory="Northeast"`` against
    ``territory="West"``.

    Args:
        df: Input sales DataFrame.
        cohort_column: Column defining the cohort (e.g., ``"territory"`` or
            ``"product_name"``).
        cohort_a: Value identifying cohort A.
        cohort_b: Value identifying cohort B.
        metric: Numeric column to aggregate (sum).  Defaults to
            ``revenue_usd``.

    Returns:
        Dictionary with keys ``cohort_a_total``, ``cohort_b_total``,
        ``delta``, ``delta_pct`` (``None`` when cohort A total is zero),
        ``cohort_a_count``, ``cohort_b_count``.

    Raises:
        ValueError: When ``cohort_column`` or ``metric`` are missing from
            ``df``.
    """
    if df.empty:
        return _empty_cohort_result()
    if cohort_column not in df.columns:
        raise ValueError(f"cohort_column '{cohort_column}' not in DataFrame")
    if metric not in df.columns:
        raise ValueError(f"metric '{metric}' not in DataFrame")

    slice_a = df[df[cohort_column] == cohort_a]
    slice_b = df[df[cohort_column] == cohort_b]

    total_a = float(slice_a[metric].sum()) if not slice_a.empty else 0.0
    total_b = float(slice_b[metric].sum()) if not slice_b.empty else 0.0

    delta = round(total_b - total_a, 2)
    delta_pct = compute_yoy_growth(total_b, total_a)  # same math: (new-old)/old

    return {
        "cohort_a_total": round(total_a, 2),
        "cohort_b_total": round(total_b, 2),
        "delta": delta,
        "delta_pct": delta_pct,
        "cohort_a_count": int(len(slice_a)),
        "cohort_b_count": int(len(slice_b)),
    }


def yoy_growth_by_group(
    df: pd.DataFrame,
    group_column: str,
    metric: str = "revenue_usd",
    year_column: str = "year",
) -> pd.DataFrame:
    """Compute YoY growth per group, using the two most recent years in data.

    Args:
        df: Sales DataFrame containing ``year_column`` and ``metric``.
        group_column: Column to group by (e.g., ``territory``, ``rep_id``).
        metric: Numeric metric to sum per group and year.
        year_column: Name of the year column.

    Returns:
        DataFrame with columns ``<group_column>``, ``prior_<metric>``,
        ``current_<metric>``, ``yoy_growth_pct``.  Empty DataFrame when
        fewer than two distinct years are present or required columns are
        missing.
    """
    required = {group_column, metric, year_column}
    if df.empty or not required.issubset(df.columns):
        return pd.DataFrame()

    years = sorted(df[year_column].dropna().unique())
    if len(years) < 2:
        return pd.DataFrame()

    prior_year, current_year = years[-2], years[-1]

    prior = (
        df[df[year_column] == prior_year]
        .groupby(group_column, as_index=False)[metric]
        .sum()
        .rename(columns={metric: f"prior_{metric}"})
    )
    current = (
        df[df[year_column] == current_year]
        .groupby(group_column, as_index=False)[metric]
        .sum()
        .rename(columns={metric: f"current_{metric}"})
    )

    merged = prior.merge(current, on=group_column, how="outer").fillna(0.0)
    merged = merged.assign(
        yoy_growth_pct=[
            compute_yoy_growth(c, p)
            for c, p in zip(merged[f"current_{metric}"], merged[f"prior_{metric}"])
        ]
    )
    return merged.reset_index(drop=True)


def filter_by_period(
    df: pd.DataFrame,
    months: Optional[Iterable[str]] = None,
    month_range: Optional[Tuple[str, str]] = None,
    year: Optional[int] = None,
) -> pd.DataFrame:
    """Filter a DataFrame by a list of months, a month range, and/or a year.

    Unlike :func:`src.main.filter_time_series` (which supports a single
    month), this helper accepts multiple months or a ``(start, end)``
    inclusive range based on calendar order.

    Args:
        df: Sales DataFrame.
        months: Iterable of month names (case-insensitive).  Mutually
            exclusive with ``month_range``.
        month_range: ``(start_month, end_month)`` tuple, inclusive.
            Evaluated by calendar order (``January`` = 1, ...,
            ``December`` = 12).
        year: Four-digit year to filter by.

    Returns:
        A new filtered DataFrame.

    Raises:
        ValueError: When both ``months`` and ``month_range`` are provided,
            or when a month name is not a valid calendar month.
    """
    if df.empty:
        return df.copy()
    if months is not None and month_range is not None:
        raise ValueError("Pass either months or month_range, not both")

    result = df.copy()

    if year is not None and "year" in result.columns:
        result = result[result["year"] == year]

    if "month" in result.columns:
        if months is not None:
            wanted = {_month_index(m) for m in months}
            result = result[result["month"].map(_month_index).isin(wanted)]
        elif month_range is not None:
            start_idx = _month_index(month_range[0])
            end_idx = _month_index(month_range[1])
            lo, hi = min(start_idx, end_idx), max(start_idx, end_idx)
            result = result[result["month"].map(_month_index).between(lo, hi)]

    return result.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_MONTHS: List[str] = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


def _month_index(name: object) -> int:
    """Return 1-based calendar index for a month name.

    Raises ``ValueError`` if the input is not a recognized month.  ``NaN``
    inputs return ``0`` so they are filtered out of month-range matches
    rather than raising inside vectorized mapping.
    """
    if name is None or (isinstance(name, float) and np.isnan(name)):
        return 0
    try:
        return _MONTHS.index(str(name).strip().lower()) + 1
    except ValueError as exc:
        raise ValueError(f"Unknown month name: {name!r}") from exc


def _safe_pct(numerator: float, denominator: float) -> float:
    """Return numerator/denominator * 100 with NaN/zero guards."""
    if denominator is None or pd.isna(denominator) or denominator <= 0:
        return 0.0
    if numerator is None or pd.isna(numerator):
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _empty_cohort_result() -> dict:
    """Zero-valued cohort comparison result for the empty-DataFrame case."""
    return {
        "cohort_a_total": 0.0,
        "cohort_b_total": 0.0,
        "delta": 0.0,
        "delta_pct": None,
        "cohort_a_count": 0,
        "cohort_b_count": 0,
    }
