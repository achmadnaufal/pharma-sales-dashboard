"""
Unit tests for src.metrics - attainment, YoY, rep-ranking, and cohort helpers.

Runs independently of the Streamlit UI; only pure Python / pandas logic is
exercised here.

Run with:
    pytest tests/test_metrics.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.metrics import (
    add_attainment_columns,
    cohort_comparison,
    compute_revenue_attainment,
    compute_revenue_per_call,
    compute_yoy_growth,
    filter_by_period,
    rank_reps,
    yoy_growth_by_group,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def pharma_df() -> pd.DataFrame:
    """Two-year sales fixture for YoY, ranking, and cohort tests."""
    return pd.DataFrame(
        {
            "rep_id": ["R1", "R1", "R2", "R2", "R3", "R3"],
            "rep_name": ["Alice", "Alice", "Bob", "Bob", "Carol", "Carol"],
            "territory": ["Northeast", "Northeast", "Southeast", "Southeast", "West", "West"],
            "product_name": ["A", "A", "B", "B", "C", "C"],
            "month": ["January", "January", "February", "February", "March", "March"],
            "year": [2024, 2025, 2024, 2025, 2024, 2025],
            "units_sold": [100.0, 120.0, 80.0, 90.0, 60.0, 75.0],
            "target_units": [110.0, 115.0, 75.0, 100.0, 70.0, 80.0],
            "revenue_usd": [50000.0, 60000.0, 40000.0, 45000.0, 30000.0, 36000.0],
            "target_revenue_usd": [55000.0, 58000.0, 38000.0, 50000.0, 35000.0, 40000.0],
            "calls_made": [40.0, 45.0, 30.0, 35.0, 20.0, 25.0],
            "calls_target": [50.0, 50.0, 35.0, 35.0, 25.0, 25.0],
        }
    )


# ---------------------------------------------------------------------------
# Scalar metrics
# ---------------------------------------------------------------------------

class TestComputeRevenueAttainment:
    def test_basic_attainment(self):
        assert compute_revenue_attainment(55000, 50000) == 110.0

    def test_exact_target(self):
        assert compute_revenue_attainment(50000, 50000) == 100.0

    def test_zero_target_returns_zero(self):
        assert compute_revenue_attainment(10000, 0) == 0.0

    def test_negative_target_returns_zero(self):
        assert compute_revenue_attainment(10000, -5000) == 0.0

    def test_nan_target_returns_zero(self):
        assert compute_revenue_attainment(10000, float("nan")) == 0.0

    def test_nan_numerator_returns_zero(self):
        assert compute_revenue_attainment(float("nan"), 5000) == 0.0


class TestComputeYoYGrowth:
    def test_positive_growth(self):
        assert compute_yoy_growth(120, 100) == 20.0

    def test_negative_growth(self):
        assert compute_yoy_growth(80, 100) == -20.0

    def test_zero_prior_returns_none(self):
        """Division by zero should surface as None, not inf or a silent zero."""
        assert compute_yoy_growth(100, 0) is None

    def test_negative_prior_returns_none(self):
        assert compute_yoy_growth(100, -10) is None

    def test_nan_prior_returns_none(self):
        assert compute_yoy_growth(100, float("nan")) is None


class TestComputeRevenuePerCall:
    def test_basic_value(self):
        assert compute_revenue_per_call(10000, 20) == 500.0

    def test_zero_calls_returns_zero(self):
        assert compute_revenue_per_call(10000, 0) == 0.0

    def test_nan_calls_returns_zero(self):
        assert compute_revenue_per_call(10000, float("nan")) == 0.0


# ---------------------------------------------------------------------------
# DataFrame metrics
# ---------------------------------------------------------------------------

class TestAddAttainmentColumns:
    def test_adds_unit_and_revenue_attainment(self, pharma_df):
        result = add_attainment_columns(pharma_df)
        assert "unit_attainment_pct" in result.columns
        assert "revenue_attainment_pct" in result.columns
        assert "call_attainment_pct" in result.columns
        assert "revenue_per_call" in result.columns

    def test_does_not_mutate_input(self, pharma_df):
        original_cols = list(pharma_df.columns)
        add_attainment_columns(pharma_df)
        assert list(pharma_df.columns) == original_cols

    def test_missing_optional_columns_are_skipped(self):
        df = pd.DataFrame({"units_sold": [10.0], "target_units": [20.0]})
        result = add_attainment_columns(df)
        assert "unit_attainment_pct" in result.columns
        assert "revenue_attainment_pct" not in result.columns

    def test_empty_dataframe_returns_empty(self):
        assert add_attainment_columns(pd.DataFrame()).empty


class TestRankReps:
    def test_ranks_by_revenue_descending_by_default(self, pharma_df):
        ranked = rank_reps(pharma_df, metric="revenue_usd")
        assert list(ranked["rep_id"]) == ["R1", "R2", "R3"]
        assert list(ranked["rank"]) == [1, 2, 3]

    def test_top_n_limits_rows(self, pharma_df):
        ranked = rank_reps(pharma_df, metric="revenue_usd", top_n=2)
        assert len(ranked) == 2

    def test_ascending_surfaces_under_performers(self, pharma_df):
        ranked = rank_reps(pharma_df, metric="revenue_usd", ascending=True)
        assert ranked.iloc[0]["rep_id"] == "R3"

    def test_missing_rep_id_returns_empty(self):
        df = pd.DataFrame({"revenue_usd": [1000, 2000]})
        assert rank_reps(df).empty

    def test_invalid_top_n_raises(self, pharma_df):
        with pytest.raises(ValueError):
            rank_reps(pharma_df, top_n=0)

    def test_tied_reps_share_rank(self):
        df = pd.DataFrame({"rep_id": ["A", "B", "C"], "revenue_usd": [100, 100, 50]})
        ranked = rank_reps(df)
        # Both A and B sold 100 - they should share rank 1
        ranks = dict(zip(ranked["rep_id"], ranked["rank"]))
        assert ranks["A"] == ranks["B"] == 1
        assert ranks["C"] == 3


class TestCohortComparison:
    def test_basic_comparison(self, pharma_df):
        result = cohort_comparison(
            pharma_df, cohort_column="territory",
            cohort_a="Northeast", cohort_b="Southeast",
        )
        assert result["cohort_a_total"] == 50000.0 + 60000.0
        assert result["cohort_b_total"] == 40000.0 + 45000.0
        assert result["cohort_a_count"] == 2
        assert result["cohort_b_count"] == 2

    def test_delta_is_b_minus_a(self, pharma_df):
        result = cohort_comparison(
            pharma_df, "territory", "Northeast", "West",
        )
        expected = (30000 + 36000) - (50000 + 60000)
        assert result["delta"] == round(expected, 2)

    def test_missing_cohort_value_counts_as_zero(self, pharma_df):
        result = cohort_comparison(
            pharma_df, "territory", "Northeast", "DoesNotExist",
        )
        assert result["cohort_b_total"] == 0.0
        assert result["cohort_b_count"] == 0

    def test_invalid_column_raises(self, pharma_df):
        with pytest.raises(ValueError):
            cohort_comparison(pharma_df, "nonexistent_col", "a", "b")

    def test_empty_dataframe_returns_zeros(self):
        result = cohort_comparison(
            pd.DataFrame(columns=["territory", "revenue_usd"]),
            "territory", "a", "b",
        )
        assert result["cohort_a_total"] == 0.0
        assert result["delta_pct"] is None


class TestYoYGrowthByGroup:
    def test_yoy_growth_per_territory(self, pharma_df):
        growth = yoy_growth_by_group(pharma_df, group_column="territory")
        assert set(growth["territory"]) == {"Northeast", "Southeast", "West"}
        ne = growth[growth["territory"] == "Northeast"].iloc[0]
        assert ne["prior_revenue_usd"] == 50000.0
        assert ne["current_revenue_usd"] == 60000.0
        assert ne["yoy_growth_pct"] == 20.0

    def test_single_year_returns_empty(self):
        df = pd.DataFrame(
            {"territory": ["A"], "year": [2025], "revenue_usd": [1000.0]}
        )
        assert yoy_growth_by_group(df, group_column="territory").empty

    def test_missing_column_returns_empty(self, pharma_df):
        assert yoy_growth_by_group(
            pharma_df.drop(columns=["year"]), group_column="territory"
        ).empty


class TestFilterByPeriod:
    def test_filter_by_multiple_months(self, pharma_df):
        result = filter_by_period(pharma_df, months=["January", "February"])
        assert set(result["month"]) == {"January", "February"}

    def test_filter_by_month_range(self, pharma_df):
        result = filter_by_period(pharma_df, month_range=("January", "February"))
        assert set(result["month"]).issubset({"January", "February"})
        assert len(result) == 4  # two Jan + two Feb rows in fixture

    def test_filter_by_year(self, pharma_df):
        result = filter_by_period(pharma_df, year=2024)
        assert (result["year"] == 2024).all()

    def test_both_months_and_range_raises(self, pharma_df):
        with pytest.raises(ValueError):
            filter_by_period(pharma_df, months=["January"], month_range=("Jan", "Feb"))

    def test_empty_dataframe_returns_empty(self):
        assert filter_by_period(pd.DataFrame(), months=["January"]).empty

    def test_unknown_month_raises(self, pharma_df):
        with pytest.raises(ValueError):
            filter_by_period(pharma_df, months=["NotAMonth"])

    def test_month_range_is_inclusive_and_unordered(self, pharma_df):
        """Range (March, January) should behave the same as (January, March)."""
        reversed_range = filter_by_period(pharma_df, month_range=("March", "January"))
        forward_range = filter_by_period(pharma_df, month_range=("January", "March"))
        assert len(reversed_range) == len(forward_range)
