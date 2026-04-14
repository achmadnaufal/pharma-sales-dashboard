"""
Unit tests for pharma-sales-dashboard core logic.

Tests cover revenue calculation, target achievement, territory aggregation,
market share computation, time-series filtering, and edge cases such as
zero targets and missing rep data.

Run with:
    pytest tests/ -v
"""

import sys
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

# Allow imports from the project root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.main import (
    PharmaSalesDashboard,
    compute_target_achievement,
    compute_revenue,
    aggregate_by_territory,
    compute_market_share,
    filter_time_series,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_df() -> pd.DataFrame:
    """Minimal pharma sales DataFrame covering multiple reps, territories, and months."""
    return pd.DataFrame(
        {
            "rep_id": ["REP001", "REP001", "REP002", "REP002", "REP003"],
            "rep_name": ["Alice", "Alice", "Bob", "Bob", "Carol"],
            "territory": ["Northeast", "Northeast", "Southeast", "Southeast", "Midwest"],
            "product_name": ["Cardivex 10mg", "Neuroplex 25mg", "Cardivex 10mg", "Oncovast 50mg", "Diabetrex 500mg"],
            "therapeutic_area": ["Cardiology", "Neurology", "Cardiology", "Oncology", "Endocrinology"],
            "month": ["January", "January", "January", "February", "February"],
            "year": [2025, 2025, 2025, 2025, 2025],
            "units_sold": [100.0, 80.0, 120.0, 60.0, 200.0],
            "revenue_usd": [50000.0, 48000.0, 60000.0, 120000.0, 40000.0],
            "target_units": [110.0, 90.0, 100.0, 70.0, 180.0],
            "calls_made": [40, 40, 50, 50, 45],
            "hcp_met": [30, 30, 38, 38, 33],
            "market_share_pct": [10.5, 8.2, 11.0, 15.3, 9.7],
        }
    )


@pytest.fixture()
def dashboard() -> PharmaSalesDashboard:
    """Dashboard instance with default config."""
    return PharmaSalesDashboard()


# ---------------------------------------------------------------------------
# 1. Revenue calculation
# ---------------------------------------------------------------------------

class TestComputeRevenue:
    """Tests for the compute_revenue helper function."""

    def test_basic_revenue_calculation(self):
        """Revenue equals units_sold times price_per_unit."""
        assert compute_revenue(100, 500.0) == 50000.0

    def test_revenue_rounds_to_two_decimals(self):
        """Result is rounded to 2 decimal places."""
        result = compute_revenue(3, 1.005)
        assert result == round(3 * 1.005, 2)

    def test_zero_units_yields_zero_revenue(self):
        """No units sold means zero revenue."""
        assert compute_revenue(0, 500.0) == 0.0

    def test_negative_units_raises_value_error(self):
        """Negative unit count is invalid."""
        with pytest.raises(ValueError, match="non-negative"):
            compute_revenue(-10, 500.0)

    def test_negative_price_raises_value_error(self):
        """Negative price per unit is invalid."""
        with pytest.raises(ValueError, match="non-negative"):
            compute_revenue(10, -500.0)


# ---------------------------------------------------------------------------
# 2. Target achievement percentage
# ---------------------------------------------------------------------------

class TestComputeTargetAchievement:
    """Tests for the compute_target_achievement helper function."""

    def test_over_target_returns_correct_percentage(self):
        """Selling more than target yields >100 %."""
        assert compute_target_achievement(120, 100) == 120.0

    def test_exact_target_returns_100(self):
        """Hitting target exactly is 100 %."""
        assert compute_target_achievement(100, 100) == 100.0

    def test_under_target_returns_correct_percentage(self):
        """Selling less than target yields <100 %."""
        assert compute_target_achievement(80, 100) == 80.0

    def test_zero_target_returns_zero(self):
        """Zero target must not raise ZeroDivisionError; returns 0.0."""
        assert compute_target_achievement(50, 0) == 0.0

    def test_negative_target_returns_zero(self):
        """Negative target is treated like zero target."""
        assert compute_target_achievement(50, -10) == 0.0

    def test_result_is_rounded_to_two_decimals(self):
        """Result precision is at most 2 decimal places."""
        result = compute_target_achievement(1, 3)
        assert result == round(1 / 3 * 100, 2)


# ---------------------------------------------------------------------------
# 3. Territory aggregation
# ---------------------------------------------------------------------------

class TestAggregateByTerritory:
    """Tests for the aggregate_by_territory function."""

    def test_returns_one_row_per_territory(self, sample_df):
        """Resulting DataFrame has exactly as many rows as unique territories."""
        result = aggregate_by_territory(sample_df)
        assert len(result) == sample_df["territory"].nunique()

    def test_units_sold_summed_correctly(self, sample_df):
        """Units sold are correctly totalled per territory."""
        result = aggregate_by_territory(sample_df)
        northeast = result[result["territory"] == "Northeast"]["units_sold"].iloc[0]
        expected = sample_df[sample_df["territory"] == "Northeast"]["units_sold"].sum()
        assert northeast == expected

    def test_revenue_summed_correctly(self, sample_df):
        """Revenue is correctly totalled per territory."""
        result = aggregate_by_territory(sample_df)
        southeast = result[result["territory"] == "Southeast"]["revenue_usd"].iloc[0]
        expected = sample_df[sample_df["territory"] == "Southeast"]["revenue_usd"].sum()
        assert southeast == expected

    def test_target_achievement_column_added(self, sample_df):
        """Aggregated result includes a target_achievement_pct column."""
        result = aggregate_by_territory(sample_df)
        assert "target_achievement_pct" in result.columns

    def test_empty_dataframe_returns_empty(self):
        """Empty input returns empty DataFrame without raising."""
        result = aggregate_by_territory(pd.DataFrame())
        assert result.empty

    def test_missing_territory_column_returns_empty(self, sample_df):
        """DataFrame without 'territory' column returns empty result."""
        df_no_territory = sample_df.drop(columns=["territory"])
        result = aggregate_by_territory(df_no_territory)
        assert result.empty

    def test_does_not_mutate_input(self, sample_df):
        """Input DataFrame is not modified in place."""
        original_shape = sample_df.shape
        original_cols = list(sample_df.columns)
        aggregate_by_territory(sample_df)
        assert sample_df.shape == original_shape
        assert list(sample_df.columns) == original_cols


# ---------------------------------------------------------------------------
# 4. Market share computation
# ---------------------------------------------------------------------------

class TestComputeMarketShare:
    """Tests for the compute_market_share helper function."""

    def test_basic_market_share(self):
        """50 units out of 200 total is 25 %."""
        assert compute_market_share(50, 200) == 25.0

    def test_zero_total_market_returns_zero(self):
        """Zero total market must not raise ZeroDivisionError."""
        assert compute_market_share(100, 0) == 0.0

    def test_negative_total_market_returns_zero(self):
        """Negative total market is treated like zero."""
        assert compute_market_share(100, -50) == 0.0

    def test_full_market_returns_100(self):
        """Owning the entire market is 100 %."""
        assert compute_market_share(300, 300) == 100.0

    def test_result_rounds_to_two_decimals(self):
        """Market share is rounded to 2 decimal places."""
        result = compute_market_share(1, 3)
        assert result == round(1 / 3 * 100, 2)


# ---------------------------------------------------------------------------
# 5. Time-series filtering
# ---------------------------------------------------------------------------

class TestFilterTimeSeries:
    """Tests for the filter_time_series function."""

    def test_filter_by_year(self, sample_df):
        """Filtering by year returns only rows matching that year."""
        result = filter_time_series(sample_df, year=2025)
        assert len(result) == len(sample_df)
        assert (result["year"] == 2025).all()

    def test_filter_by_month(self, sample_df):
        """Filtering by month returns only rows for that month."""
        result = filter_time_series(sample_df, month="January")
        assert (result["month"] == "January").all()
        assert len(result) == 3  # Three January rows in fixture

    def test_filter_by_year_and_month(self, sample_df):
        """Combined year+month filter intersects both conditions."""
        result = filter_time_series(sample_df, year=2025, month="February")
        assert len(result) == 2
        assert (result["month"] == "February").all()

    def test_no_filter_returns_all_rows(self, sample_df):
        """Calling with no filter arguments returns all rows."""
        result = filter_time_series(sample_df)
        assert len(result) == len(sample_df)

    def test_nonexistent_month_returns_empty(self, sample_df):
        """Filtering for a month not in data returns empty DataFrame."""
        result = filter_time_series(sample_df, month="December")
        assert result.empty

    def test_filter_is_case_insensitive(self, sample_df):
        """Month matching is case-insensitive."""
        lower = filter_time_series(sample_df, month="january")
        upper = filter_time_series(sample_df, month="JANUARY")
        assert len(lower) == len(upper)

    def test_missing_year_column_raises(self, sample_df):
        """Filtering by year on a DataFrame without 'year' column raises ValueError."""
        df_no_year = sample_df.drop(columns=["year"])
        with pytest.raises(ValueError, match="year"):
            filter_time_series(df_no_year, year=2025)

    def test_missing_month_column_raises(self, sample_df):
        """Filtering by month on a DataFrame without 'month' column raises ValueError."""
        df_no_month = sample_df.drop(columns=["month"])
        with pytest.raises(ValueError, match="month"):
            filter_time_series(df_no_month, month="January")

    def test_empty_input_returns_empty(self):
        """Empty DataFrame in returns empty DataFrame without raising."""
        result = filter_time_series(pd.DataFrame(), year=2025)
        assert result.empty

    def test_does_not_mutate_input(self, sample_df):
        """Input DataFrame is not modified in place."""
        original_len = len(sample_df)
        filter_time_series(sample_df, month="January")
        assert len(sample_df) == original_len


# ---------------------------------------------------------------------------
# 6. Edge cases: zero targets and missing reps
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge case tests for unusual but valid data scenarios."""

    def test_all_zero_targets_in_analysis(self, dashboard):
        """Dashboard analysis handles an entire column of zero targets gracefully."""
        df = pd.DataFrame(
            {
                "rep_id": ["REP001", "REP002"],
                "territory": ["North", "South"],
                "product_name": ["ProdA", "ProdB"],
                "month": ["January", "January"],
                "year": [2025, 2025],
                "units_sold": [50.0, 80.0],
                "revenue_usd": [25000.0, 40000.0],
                "target_units": [0.0, 0.0],
                "calls_made": [30, 40],
                "hcp_met": [20, 28],
                "market_share_pct": [5.0, 7.0],
            }
        )
        result = dashboard.analyze(df)
        assert "target_achievement" in result
        assert all(v == 0.0 for v in result["target_achievement"])

    def test_missing_rep_columns_do_not_crash_analysis(self, dashboard):
        """Analysis completes even when optional rep-level columns are absent."""
        df = pd.DataFrame(
            {
                "territory": ["Northeast", "Southeast"],
                "units_sold": [100.0, 120.0],
                "revenue_usd": [50000.0, 60000.0],
                "target_units": [110.0, 115.0],
            }
        )
        result = dashboard.analyze(df)
        assert result["total_records"] == 2
        assert "totals" in result

    def test_single_row_dataframe(self, dashboard):
        """Single-row DataFrames are analyzed without error."""
        df = pd.DataFrame(
            {
                "rep_id": ["REP001"],
                "territory": ["Northeast"],
                "units_sold": [100.0],
                "revenue_usd": [50000.0],
                "target_units": [90.0],
            }
        )
        result = dashboard.analyze(df)
        assert result["total_records"] == 1

    def test_nan_units_coerced_to_zero(self, dashboard):
        """Non-numeric / NaN values in numeric columns are coerced to 0, not errors."""
        df = pd.DataFrame(
            {
                "territory": ["Northeast"],
                "units_sold": ["N/A"],
                "revenue_usd": [50000.0],
                "target_units": [90.0],
            }
        )
        # Should not raise
        result = dashboard.analyze(df)
        assert result["total_records"] == 1

    def test_validate_raises_on_empty_dataframe(self, dashboard):
        """validate() raises ValueError on an empty DataFrame."""
        with pytest.raises(ValueError, match="empty"):
            dashboard.validate(pd.DataFrame())

    def test_validate_raises_on_missing_required_columns(self):
        """validate() raises ValueError when configured required columns are missing."""
        cfg_dashboard = PharmaSalesDashboard(config={"required_columns": ["rep_id", "territory"]})
        df = pd.DataFrame({"revenue_usd": [1000]})
        with pytest.raises(ValueError, match="Missing required columns"):
            cfg_dashboard.validate(df)

    def test_preprocess_does_not_mutate_input(self, dashboard, sample_df):
        """preprocess() returns a new DataFrame and does not modify the original."""
        original_columns = list(sample_df.columns)
        dashboard.preprocess(sample_df)
        assert list(sample_df.columns) == original_columns

    def test_load_data_raises_on_missing_file(self, dashboard, tmp_path):
        """load_data() raises FileNotFoundError for a path that does not exist."""
        with pytest.raises(FileNotFoundError):
            dashboard.load_data(str(tmp_path / "nonexistent.csv"))

    def test_load_data_raises_on_unsupported_extension(self, dashboard, tmp_path):
        """load_data() raises ValueError for unsupported file types."""
        fake_file = tmp_path / "data.parquet"
        fake_file.write_text("dummy")
        with pytest.raises(ValueError, match="Unsupported"):
            dashboard.load_data(str(fake_file))


# ---------------------------------------------------------------------------
# 7. PharmaSalesDashboard integration: analyze()
# ---------------------------------------------------------------------------

class TestDashboardAnalyze:
    """Integration-level tests for PharmaSalesDashboard.analyze()."""

    def test_analyze_returns_required_keys(self, dashboard, sample_df):
        """analyze() result contains total_records, columns, and missing_pct."""
        result = dashboard.analyze(sample_df)
        assert "total_records" in result
        assert "columns" in result
        assert "missing_pct" in result

    def test_total_records_matches_row_count(self, dashboard, sample_df):
        """total_records value equals the number of input rows."""
        result = dashboard.analyze(sample_df)
        assert result["total_records"] == len(sample_df)

    def test_analyze_includes_territory_summary(self, dashboard, sample_df):
        """analyze() builds a territory_summary list when territory column exists."""
        result = dashboard.analyze(sample_df)
        assert "territory_summary" in result
        assert isinstance(result["territory_summary"], list)

    def test_analyze_includes_target_achievement(self, dashboard, sample_df):
        """analyze() computes target_achievement list for each row."""
        result = dashboard.analyze(sample_df)
        assert "target_achievement" in result
        assert len(result["target_achievement"]) == len(sample_df)

    def test_to_dataframe_converts_result(self, dashboard, sample_df):
        """to_dataframe() returns a non-empty DataFrame with metric and value columns."""
        result = dashboard.analyze(sample_df)
        df_result = dashboard.to_dataframe(result)
        assert isinstance(df_result, pd.DataFrame)
        assert not df_result.empty
        assert set(df_result.columns) == {"metric", "value"}


# ---------------------------------------------------------------------------
# 8. run() integration with sample CSV
# ---------------------------------------------------------------------------

class TestDashboardRunWithFile:
    """Tests that exercise the full load → validate → analyze pipeline from disk."""

    def test_run_with_sample_csv(self, dashboard):
        """run() completes without error on the bundled sample_data.csv."""
        sample_path = Path(__file__).parent.parent / "demo" / "sample_data.csv"
        if not sample_path.exists():
            pytest.skip("demo/sample_data.csv not found")
        result = dashboard.run(str(sample_path))
        assert result["total_records"] == 20

    def test_run_with_generated_csv(self, dashboard, tmp_path):
        """run() works on a dynamically generated CSV file."""
        csv_path = tmp_path / "test_data.csv"
        df = pd.DataFrame(
            {
                "rep_id": ["R1", "R2", "R3"],
                "territory": ["North", "South", "East"],
                "product_name": ["ProdA", "ProdB", "ProdC"],
                "month": ["January", "January", "February"],
                "year": [2025, 2025, 2025],
                "units_sold": [100.0, 200.0, 150.0],
                "revenue_usd": [10000.0, 20000.0, 15000.0],
                "target_units": [90.0, 180.0, 160.0],
            }
        )
        df.to_csv(csv_path, index=False)
        result = dashboard.run(str(csv_path))
        assert result["total_records"] == 3
        assert "totals" in result
