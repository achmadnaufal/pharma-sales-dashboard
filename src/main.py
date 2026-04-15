"""
Streamlit sales performance dashboard for pharmaceutical field teams.

This module provides the core PharmaSalesDashboard class with methods for
loading, validating, preprocessing, and analyzing pharma sales data.

Author: github.com/achmadnaufal
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List


REQUIRED_COLUMNS = [
    "rep_id",
    "territory",
    "product_name",
    "month",
    "year",
    "units_sold",
    "revenue_usd",
    "target_units",
]

NUMERIC_COLUMNS = ["units_sold", "revenue_usd", "target_units", "calls_made", "hcp_met", "market_share_pct"]


def compute_target_achievement(units_sold: float, target_units: float) -> float:
    """Compute the target achievement percentage for a single record.

    Handles zero-target edge case by returning 0.0 instead of raising
    a ZeroDivisionError.

    Args:
        units_sold: Actual units sold in the period.
        target_units: Target units set for the period.

    Returns:
        Achievement as a percentage (e.g., 110.5 for 110.5 %).
        Returns 0.0 when target_units is zero or negative.
    """
    if target_units <= 0:
        return 0.0
    return round((units_sold / target_units) * 100, 2)


def compute_revenue(units_sold: float, price_per_unit: float) -> float:
    """Compute total revenue from units sold and price per unit.

    Args:
        units_sold: Number of units sold.
        price_per_unit: Revenue per unit in USD.

    Returns:
        Total revenue in USD, rounded to 2 decimal places.

    Raises:
        ValueError: If either argument is negative.
    """
    if units_sold < 0 or price_per_unit < 0:
        raise ValueError("units_sold and price_per_unit must be non-negative")
    return round(units_sold * price_per_unit, 2)


def aggregate_by_territory(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate sales metrics grouped by territory.

    Args:
        df: Preprocessed sales DataFrame containing at least the columns
            ``territory``, ``units_sold``, ``revenue_usd``, and ``target_units``.

    Returns:
        A new DataFrame with one row per territory and aggregated totals/means.
        Returns an empty DataFrame if ``df`` is empty or ``territory`` column
        is absent.
    """
    if df.empty or "territory" not in df.columns:
        return pd.DataFrame()

    agg_cols = {col: "sum" for col in ["units_sold", "revenue_usd", "target_units", "calls_made", "hcp_met"]
                if col in df.columns}

    if not agg_cols:
        return pd.DataFrame()

    aggregated = df.groupby("territory", as_index=False).agg(agg_cols)

    if "units_sold" in aggregated.columns and "target_units" in aggregated.columns:
        aggregated = aggregated.assign(
            target_achievement_pct=aggregated.apply(
                lambda row: compute_target_achievement(row["units_sold"], row["target_units"]),
                axis=1,
            )
        )

    return aggregated


def compute_market_share(product_units: float, total_market_units: float) -> float:
    """Compute market share as a percentage.

    Args:
        product_units: Units sold for the product.
        total_market_units: Total units sold across all competing products in
            the same market.

    Returns:
        Market share percentage rounded to 2 decimal places.
        Returns 0.0 when total_market_units is zero or negative.
    """
    if total_market_units <= 0:
        return 0.0
    return round((product_units / total_market_units) * 100, 2)


def filter_time_series(
    df: pd.DataFrame,
    year: Optional[int] = None,
    month: Optional[str] = None,
) -> pd.DataFrame:
    """Filter a sales DataFrame by year and/or month.

    Args:
        df: Preprocessed sales DataFrame.  Must contain ``year`` and/or
            ``month`` columns for the respective filters to apply.
        year: Four-digit year to filter by.  ``None`` skips this filter.
        month: Month name (e.g., ``"January"``) to filter by.  Case-insensitive.
            ``None`` skips this filter.

    Returns:
        A new filtered DataFrame.  Returns an empty DataFrame when the
        combination yields no rows.

    Raises:
        ValueError: If ``year`` or ``month`` columns are missing when the
            corresponding filter argument is provided.
    """
    if df.empty:
        return df.copy()

    result = df.copy()

    if year is not None:
        if "year" not in result.columns:
            raise ValueError("DataFrame does not contain a 'year' column")
        result = result[result["year"] == year]

    if month is not None:
        if "month" not in result.columns:
            raise ValueError("DataFrame does not contain a 'month' column")
        result = result[result["month"].str.lower() == month.lower()]

    return result.reset_index(drop=True)


class PharmaSalesDashboard:
    """Pharma sales performance dashboard.

    Provides a full pipeline for loading, validating, preprocessing, and
    analyzing pharmaceutical sales data from CSV or Excel files.

    Args:
        config: Optional configuration dictionary.  Supported keys:

            - ``required_columns`` (list[str]): Override the default list of
              required columns checked during validation.

    Example::

        dashboard = PharmaSalesDashboard()
        result = dashboard.run("demo/sample_data.csv")
        print(result["totals"])
    """

    def __init__(self, config: Optional[Dict] = None) -> None:
        """Initialize the dashboard with optional configuration.

        Args:
            config: Optional mapping of configuration values.
        """
        self.config = config or {}

    def load_data(self, filepath: str) -> pd.DataFrame:
        """Load sales data from a CSV or Excel file.

        Args:
            filepath: Path to the data file.  Supports ``.csv``, ``.xlsx``,
                and ``.xls`` extensions.

        Returns:
            Raw DataFrame loaded from the file.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file extension is not supported.
        """
        p = Path(filepath)
        if not p.exists():
            raise FileNotFoundError(f"Data file not found: {filepath}")
        if p.suffix in (".xlsx", ".xls"):
            return pd.read_excel(filepath)
        if p.suffix == ".csv":
            return pd.read_csv(filepath)
        raise ValueError(f"Unsupported file extension '{p.suffix}'. Use .csv, .xlsx, or .xls.")

    def validate(self, df: pd.DataFrame) -> bool:
        """Validate that the DataFrame meets minimum structural requirements.

        Checks that the DataFrame is non-empty.  When ``required_columns`` is
        present in the instance config, also verifies those columns exist.

        Args:
            df: DataFrame to validate.

        Returns:
            ``True`` when validation passes.

        Raises:
            ValueError: If the DataFrame is empty or required columns are
                missing.
        """
        if df.empty:
            raise ValueError("Input DataFrame is empty")

        required = self.config.get("required_columns", [])
        if required:
            missing = [col for col in required if col not in df.columns]
            if missing:
                raise ValueError(f"Missing required columns: {missing}")

        return True

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and preprocess input data.

        Performs the following transformations (all immutable - returns a new
        DataFrame):

        1. Drops fully-empty rows.
        2. Standardizes column names to lowercase with underscores.
        3. Coerces known numeric columns to ``float``, setting non-parseable
           values to ``NaN``.
        4. Fills missing numeric values with ``0``.
        5. Strips leading/trailing whitespace from string columns.

        Args:
            df: Raw input DataFrame.

        Returns:
            A new, cleaned DataFrame.
        """
        result = df.copy()
        result = result.dropna(how="all")
        result = result.rename(columns=lambda c: c.lower().strip().replace(" ", "_"))

        for col in NUMERIC_COLUMNS:
            if col in result.columns:
                result = result.assign(**{col: pd.to_numeric(result[col], errors="coerce").fillna(0.0)})

        str_cols = result.select_dtypes(include=["object"]).columns
        for col in str_cols:
            result = result.assign(**{col: result[col].str.strip()})

        return result

    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Run core analysis and return a summary metrics dictionary.

        Preprocesses the data first, then computes:

        - Record count and column list
        - Per-column missing-value percentages
        - Summary statistics, totals, and means for numeric columns
        - Territory-level aggregation
        - Target achievement percentage per row

        Args:
            df: Raw or preprocessed sales DataFrame.

        Returns:
            Dictionary with keys: ``total_records``, ``columns``,
            ``missing_pct``, ``summary_stats`` (when numeric columns exist),
            ``totals``, ``means``, ``territory_summary``,
            ``target_achievement``.
        """
        processed = self.preprocess(df)
        result: Dict[str, Any] = {
            "total_records": len(processed),
            "columns": list(processed.columns),
            "missing_pct": (processed.isnull().sum() / max(len(processed), 1) * 100).round(1).to_dict(),
        }

        numeric_df = processed.select_dtypes(include="number")
        if not numeric_df.empty:
            result["summary_stats"] = numeric_df.describe().round(3).to_dict()
            result["totals"] = numeric_df.sum().round(2).to_dict()
            result["means"] = numeric_df.mean().round(3).to_dict()

        territory_agg = aggregate_by_territory(processed)
        if not territory_agg.empty:
            result["territory_summary"] = territory_agg.to_dict(orient="records")

        if "units_sold" in processed.columns and "target_units" in processed.columns:
            result["target_achievement"] = processed.apply(
                lambda row: compute_target_achievement(row["units_sold"], row["target_units"]),
                axis=1,
            ).tolist()

        return result

    def run(self, filepath: str) -> Dict[str, Any]:
        """Full pipeline: load, validate, and analyze data from a file.

        Args:
            filepath: Path to the CSV or Excel data file.

        Returns:
            Analysis results dictionary as returned by :meth:`analyze`.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is empty, has unsupported format, or
                fails validation.
        """
        df = self.load_data(filepath)
        self.validate(df)
        return self.analyze(df)

    def to_dataframe(self, result: Dict) -> pd.DataFrame:
        """Convert a flat or nested analysis result dict to a tidy DataFrame.

        Each scalar value becomes its own row.  Nested dicts are flattened
        using dot notation (e.g., ``totals.revenue_usd``).  List values are
        skipped.

        Args:
            result: Dictionary as returned by :meth:`analyze`.

        Returns:
            Two-column DataFrame with columns ``metric`` and ``value``.
        """
        rows: List[Dict[str, Any]] = []
        for k, v in result.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    if not isinstance(vv, (dict, list)):
                        rows.append({"metric": f"{k}.{kk}", "value": vv})
            elif not isinstance(v, list):
                rows.append({"metric": k, "value": v})
        return pd.DataFrame(rows)
