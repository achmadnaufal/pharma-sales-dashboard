"""
Unit tests for the Bass diffusion module.

Covers parameter validation, adoption-fraction closed-form, peak timing,
forecast monotonicity, dataclass immutability, grid-search fitting, and
tabular helper functions.

Run with:
    pytest tests/test_bass_diffusion.py -v
"""

from __future__ import annotations

import sys
from math import exp, isclose, log
from pathlib import Path

import pandas as pd
import pytest

# Allow imports from the project root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bass_diffusion import (
    BassForecast,
    BassForecastPoint,
    BassParameters,
    adoption_fraction,
    cumulative_adopters,
    fit_parameters,
    forecast,
    forecast_from_launch_row,
    new_adopters,
    peak_new_adopters,
    peak_period,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def typical_params() -> BassParameters:
    """Empirically typical Rx launch parameters (Mahajan/Muller survey)."""
    return BassParameters(p=0.01, q=0.4, m=10_000.0, product_name="Cardivex")


@pytest.fixture()
def pure_innovation_params() -> BassParameters:
    """Degenerate case with q = 0 (pure innovation, no imitation)."""
    return BassParameters(p=0.05, q=0.0, m=5_000.0)


# ---------------------------------------------------------------------------
# 1. BassParameters validation
# ---------------------------------------------------------------------------

class TestBassParameters:
    """Dataclass construction and validation."""

    def test_valid_parameters_construct(self):
        params = BassParameters(p=0.01, q=0.4, m=1_000.0)
        assert params.p == 0.01
        assert params.q == 0.4
        assert params.m == 1_000.0

    def test_invalid_p_too_low_raises(self):
        with pytest.raises(ValueError, match="innovation"):
            BassParameters(p=0.0, q=0.4, m=1_000.0)

    def test_invalid_p_too_high_raises(self):
        with pytest.raises(ValueError, match="innovation"):
            BassParameters(p=1.5, q=0.4, m=1_000.0)

    def test_invalid_q_negative_raises(self):
        with pytest.raises(ValueError, match="imitation"):
            BassParameters(p=0.01, q=-0.1, m=1_000.0)

    def test_invalid_q_too_high_raises(self):
        with pytest.raises(ValueError, match="imitation"):
            BassParameters(p=0.01, q=2.0, m=1_000.0)

    def test_invalid_m_too_low_raises(self):
        with pytest.raises(ValueError, match="potential"):
            BassParameters(p=0.01, q=0.4, m=0.0)

    def test_parameters_are_frozen(self, typical_params):
        with pytest.raises(Exception):
            typical_params.p = 0.05  # frozen dataclass

    def test_with_market_potential_returns_new_instance(self, typical_params):
        updated = typical_params.with_market_potential(20_000.0)
        assert updated.m == 20_000.0
        assert typical_params.m == 10_000.0   # original unchanged
        assert updated is not typical_params


# ---------------------------------------------------------------------------
# 2. Adoption fraction F(t)
# ---------------------------------------------------------------------------

class TestAdoptionFraction:
    """Closed-form F(t) correctness."""

    def test_fraction_at_zero_is_zero(self):
        assert adoption_fraction(0, p=0.01, q=0.4) == 0.0

    def test_fraction_matches_closed_form(self):
        p, q, t = 0.02, 0.3, 5
        r = p + q
        expected = (1 - exp(-r * t)) / (1 + (q / p) * exp(-r * t))
        assert isclose(adoption_fraction(t, p, q), expected, rel_tol=1e-9)

    def test_fraction_monotonically_increases(self):
        fracs = [adoption_fraction(t, p=0.01, q=0.4) for t in range(0, 30)]
        assert all(b >= a for a, b in zip(fracs, fracs[1:]))

    def test_fraction_bounded_in_unit_interval(self):
        for t in [0, 1, 5, 20, 100]:
            val = adoption_fraction(t, p=0.01, q=0.4)
            assert 0.0 <= val <= 1.0

    def test_fraction_approaches_one_at_infinity(self):
        assert adoption_fraction(1_000, p=0.01, q=0.4) > 0.9999

    def test_negative_t_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            adoption_fraction(-1, p=0.01, q=0.4)

    def test_non_positive_p_raises(self):
        with pytest.raises(ValueError, match="strictly positive"):
            adoption_fraction(1, p=0.0, q=0.4)

    def test_negative_q_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            adoption_fraction(1, p=0.01, q=-0.1)


# ---------------------------------------------------------------------------
# 3. Cumulative and new adopters
# ---------------------------------------------------------------------------

class TestCumulativeAndNewAdopters:
    """Cumulative N(t) = m * F(t) and incremental n(t)."""

    def test_cumulative_scales_with_m(self, typical_params):
        n1 = cumulative_adopters(5, typical_params)
        doubled = typical_params.with_market_potential(typical_params.m * 2)
        n2 = cumulative_adopters(5, doubled)
        assert isclose(n2, 2 * n1, rel_tol=1e-9)

    def test_new_adopters_equals_delta_cumulative(self, typical_params):
        incr = new_adopters(3, typical_params)
        expected = (
            cumulative_adopters(3, typical_params)
            - cumulative_adopters(2, typical_params)
        )
        assert isclose(incr, expected, rel_tol=1e-9)

    def test_new_adopters_requires_period_ge_1(self, typical_params):
        with pytest.raises(ValueError, match=">= 1"):
            new_adopters(0, typical_params)


# ---------------------------------------------------------------------------
# 4. Peak timing and peak rate
# ---------------------------------------------------------------------------

class TestPeakTiming:
    """Closed-form peak period and peak new-adopter rate."""

    def test_peak_period_closed_form(self, typical_params):
        expected = log(typical_params.q / typical_params.p) / (
            typical_params.p + typical_params.q
        )
        assert isclose(peak_period(typical_params), expected, rel_tol=1e-9)

    def test_peak_period_none_when_q_le_p(self):
        params = BassParameters(p=0.05, q=0.05, m=1_000.0)
        assert peak_period(params) is None

    def test_peak_period_none_for_pure_innovation(self, pure_innovation_params):
        assert peak_period(pure_innovation_params) is None

    def test_peak_new_adopters_closed_form(self, typical_params):
        p, q, m = typical_params.p, typical_params.q, typical_params.m
        expected = m * (p + q) ** 2 / (4 * q)
        assert isclose(peak_new_adopters(typical_params), expected, rel_tol=1e-9)

    def test_peak_new_adopters_pure_innovation(self, pure_innovation_params):
        # When q == 0 we define peak rate as m * p (instantaneous at t=0+).
        expected = pure_innovation_params.m * pure_innovation_params.p
        assert isclose(
            peak_new_adopters(pure_innovation_params), expected, rel_tol=1e-9
        )


# ---------------------------------------------------------------------------
# 5. forecast() builder
# ---------------------------------------------------------------------------

class TestForecast:
    """Multi-period forecast construction."""

    def test_horizon_matches_points_length(self, typical_params):
        fc = forecast(typical_params, horizon=12)
        assert fc.horizon == 12
        assert len(fc.points) == 12

    def test_periods_are_1_indexed_and_contiguous(self, typical_params):
        fc = forecast(typical_params, horizon=6)
        assert [pt.period for pt in fc.points] == [1, 2, 3, 4, 5, 6]

    def test_cumulative_is_monotonically_non_decreasing(self, typical_params):
        fc = forecast(typical_params, horizon=24)
        cums = [pt.cumulative_adopters for pt in fc.points]
        assert all(b >= a for a, b in zip(cums, cums[1:]))

    def test_cumulative_bounded_by_market_potential(self, typical_params):
        fc = forecast(typical_params, horizon=50)
        for pt in fc.points:
            assert pt.cumulative_adopters <= typical_params.m + 1e-6

    def test_new_adopters_never_negative(self, typical_params):
        fc = forecast(typical_params, horizon=24)
        assert all(pt.new_adopters >= 0 for pt in fc.points)

    def test_adoption_fraction_in_unit_interval(self, typical_params):
        fc = forecast(typical_params, horizon=24)
        for pt in fc.points:
            assert 0.0 <= pt.adoption_fraction <= 1.0

    def test_horizon_below_one_raises(self, typical_params):
        with pytest.raises(ValueError, match=">= 1"):
            forecast(typical_params, horizon=0)

    def test_forecast_to_dataframe(self, typical_params):
        df = forecast(typical_params, horizon=5).to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        assert set(df.columns) == {
            "period",
            "cumulative_adopters",
            "new_adopters",
            "adoption_fraction",
        }

    def test_empty_forecast_to_dataframe_returns_expected_columns(
        self, typical_params
    ):
        empty = BassForecast(parameters=typical_params, points=tuple())
        df = empty.to_dataframe()
        assert df.empty
        assert set(df.columns) == {
            "period",
            "cumulative_adopters",
            "new_adopters",
            "adoption_fraction",
        }

    def test_peak_new_adopter_period_near_closed_form(self, typical_params):
        """Discrete peak should land within 1 period of the continuous t*."""
        fc = forecast(typical_params, horizon=40)
        discrete_peak = max(fc.points, key=lambda pt: pt.new_adopters)
        continuous_peak = peak_period(typical_params)
        assert continuous_peak is not None
        assert abs(discrete_peak.period - continuous_peak) <= 1.5


# ---------------------------------------------------------------------------
# 6. Grid-search parameter fitting
# ---------------------------------------------------------------------------

class TestFitParameters:
    """Simple grid-search fit against simulated data."""

    def test_fit_recovers_known_parameters_approximately(self):
        true_params = BassParameters(p=0.01, q=0.4, m=10_000.0)
        simulated = [
            pt.new_adopters for pt in forecast(true_params, horizon=20).points
        ]
        fitted = fit_parameters(
            simulated, market_potential=true_params.m
        )
        # Grid recovers the true value because 0.01/0.4 are on the default grid.
        assert isclose(fitted.p, true_params.p, rel_tol=1e-6)
        assert isclose(fitted.q, true_params.q, rel_tol=1e-6)

    def test_fit_raises_on_empty_input(self):
        with pytest.raises(ValueError, match="empty"):
            fit_parameters([], market_potential=1_000.0)

    def test_fit_raises_on_negative_adopters(self):
        with pytest.raises(ValueError, match="non-negative"):
            fit_parameters([1.0, -2.0, 3.0], market_potential=1_000.0)

    def test_fit_raises_on_non_positive_market(self):
        with pytest.raises(ValueError, match="positive"):
            fit_parameters([1.0, 2.0], market_potential=0.0)

    def test_fit_respects_custom_grids(self):
        observed = [10.0, 20.0, 30.0]
        fitted = fit_parameters(
            observed,
            market_potential=1_000.0,
            p_grid=[0.01],
            q_grid=[0.3],
        )
        assert fitted.p == 0.01
        assert fitted.q == 0.3


# ---------------------------------------------------------------------------
# 7. forecast_from_launch_row helper
# ---------------------------------------------------------------------------

class TestForecastFromLaunchRow:
    """Tabular helper for DataFrame-driven batch forecasting."""

    def test_builds_forecast_from_valid_row(self):
        row = pd.Series(
            {
                "product_name": "Neuroplex 25mg",
                "p": 0.01,
                "q": 0.4,
                "market_potential": 5_000.0,
                "launch_period_label": "2025-Q1",
            }
        )
        fc = forecast_from_launch_row(row, horizon=12)
        assert fc.horizon == 12
        assert fc.parameters.product_name == "Neuroplex 25mg"
        assert fc.parameters.launch_period_label == "2025-Q1"

    def test_raises_on_missing_columns(self):
        row = pd.Series({"product_name": "X", "p": 0.01})
        with pytest.raises(ValueError, match="Missing required columns"):
            forecast_from_launch_row(row, horizon=6)


# ---------------------------------------------------------------------------
# 8. Immutability guarantees
# ---------------------------------------------------------------------------

class TestImmutability:
    """Ensure functions never mutate their inputs."""

    def test_forecast_does_not_mutate_parameters(self, typical_params):
        snapshot = (typical_params.p, typical_params.q, typical_params.m)
        forecast(typical_params, horizon=10)
        assert (
            typical_params.p,
            typical_params.q,
            typical_params.m,
        ) == snapshot

    def test_fit_does_not_mutate_observed_sequence(self):
        observed = [5.0, 10.0, 12.0, 9.0]
        copy = list(observed)
        fit_parameters(observed, market_potential=1_000.0)
        assert observed == copy
