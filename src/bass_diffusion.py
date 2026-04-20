"""
Bass Diffusion Model for pharmaceutical new-product uptake curves.

This module implements the classic Bass (1969) diffusion model, which is
widely used by pharma commercial analytics teams to forecast the launch
trajectory of a newly-approved drug based on:

- ``p``: coefficient of innovation (early prescribers / KOL-driven adoption)
- ``q``: coefficient of imitation (word-of-mouth and peer-to-peer adoption)
- ``m``: market potential (eligible patient population or prescription ceiling)

Functional form (discrete-time, period t in 1..T)::

    F(t) = (1 - exp(-(p + q) * t)) / (1 + (q / p) * exp(-(p + q) * t))
    N(t) = m * F(t)                           # cumulative adopters
    n(t) = N(t) - N(t - 1)                    # new adopters in period t

Peak adoption timing (continuous-time closed-form)::

    t*   = ln(q / p) / (p + q)                # when q > p
    n*   = m * (p + q)^2 / (4 * q)            # peak new adopters / period

References
----------
- Bass, F. M. (1969). "A New Product Growth for Model Consumer Durables."
  Management Science, 15(5), 215-227.
- Mahajan, V., Muller, E., & Bass, F. M. (1990). "New Product Diffusion
  Models in Marketing: A Review and Directions for Research."
  Journal of Marketing, 54(1), 1-26.
- Hahn, M., Park, S., Krishnamurthi, L., & Zoltners, A. A. (1994).
  "Analysis of New Product Diffusion Using a Four-Segment Trial-Repeat
  Model." Marketing Science, 13(3), 224-247.  (Adapted for Rx launches.)

All public functions are pure and immutable: inputs are never mutated and
new objects are returned.

Author: github.com/achmadnaufal
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import exp, log
from typing import List, Optional, Sequence, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

MIN_INNOVATION = 1e-6          # p must be strictly positive for log(q/p)
MAX_INNOVATION = 1.0
MIN_IMITATION = 0.0
MAX_IMITATION = 1.5            # Empirical Rx launches rarely exceed ~1.0
MIN_MARKET_POTENTIAL = 1.0     # at least one eligible patient/Rx

# Typical empirical ranges published for pharma Rx launches
# (Mahajan/Muller 1990 survey + Hahn 1994 Rx segment):
TYPICAL_P_RX = (0.001, 0.05)
TYPICAL_Q_RX = (0.20, 0.80)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BassParameters:
    """Immutable container for Bass-model parameters.

    Attributes:
        p: Coefficient of innovation (external influence). Must be in
            ``(0, 1]``.
        q: Coefficient of imitation (internal / word-of-mouth influence).
            Must be in ``[0, 1.5]``.
        m: Market potential (total eligible adopters). Must be positive.
        product_name: Optional label for the product under study.
        launch_period_label: Optional label for t=0 (e.g. "2024-Q1").
    """

    p: float
    q: float
    m: float
    product_name: Optional[str] = None
    launch_period_label: Optional[str] = None

    def __post_init__(self) -> None:
        if not (MIN_INNOVATION <= self.p <= MAX_INNOVATION):
            raise ValueError(
                f"Coefficient of innovation p={self.p} must be in "
                f"[{MIN_INNOVATION}, {MAX_INNOVATION}]"
            )
        if not (MIN_IMITATION <= self.q <= MAX_IMITATION):
            raise ValueError(
                f"Coefficient of imitation q={self.q} must be in "
                f"[{MIN_IMITATION}, {MAX_IMITATION}]"
            )
        if self.m < MIN_MARKET_POTENTIAL:
            raise ValueError(
                f"Market potential m={self.m} must be >= "
                f"{MIN_MARKET_POTENTIAL}"
            )

    def with_market_potential(self, new_m: float) -> "BassParameters":
        """Return a new ``BassParameters`` with an updated market potential.

        Supports immutable parameter-tuning workflows such as scenario
        sensitivity analysis.
        """
        return replace(self, m=new_m)


@dataclass(frozen=True)
class BassForecastPoint:
    """One period of a Bass-model forecast."""

    period: int
    cumulative_adopters: float
    new_adopters: float
    adoption_fraction: float   # F(t) in [0, 1]


@dataclass(frozen=True)
class BassForecast:
    """Full multi-period Bass forecast for a launch."""

    parameters: BassParameters
    points: Tuple[BassForecastPoint, ...] = field(default_factory=tuple)

    @property
    def horizon(self) -> int:
        """Number of forecast periods (length of ``points``)."""
        return len(self.points)

    def to_dataframe(self) -> pd.DataFrame:
        """Return a tidy DataFrame representation of this forecast."""
        if not self.points:
            return pd.DataFrame(
                columns=[
                    "period",
                    "cumulative_adopters",
                    "new_adopters",
                    "adoption_fraction",
                ]
            )
        return pd.DataFrame(
            [
                {
                    "period": pt.period,
                    "cumulative_adopters": pt.cumulative_adopters,
                    "new_adopters": pt.new_adopters,
                    "adoption_fraction": pt.adoption_fraction,
                }
                for pt in self.points
            ]
        )


# ---------------------------------------------------------------------------
# Core Bass functions
# ---------------------------------------------------------------------------

def adoption_fraction(t: float, p: float, q: float) -> float:
    """Evaluate the Bass cumulative adoption fraction F(t).

    Args:
        t: Time since launch in the same period units used for ``p`` and
            ``q`` (>=0).
        p: Coefficient of innovation, strictly positive.
        q: Coefficient of imitation, non-negative.

    Returns:
        F(t) in ``[0, 1]``.
    """
    if t < 0:
        raise ValueError(f"t={t} must be non-negative")
    if p <= 0:
        raise ValueError(f"p={p} must be strictly positive")
    if q < 0:
        raise ValueError(f"q={q} must be non-negative")

    if t == 0:
        return 0.0

    r = p + q
    numerator = 1.0 - exp(-r * t)
    denominator = 1.0 + (q / p) * exp(-r * t)
    value = numerator / denominator
    # Guard against tiny negative or slightly >1 floats from round-off.
    return max(0.0, min(1.0, value))


def cumulative_adopters(t: float, params: BassParameters) -> float:
    """Expected cumulative adopters N(t) = m * F(t)."""
    return params.m * adoption_fraction(t, params.p, params.q)


def new_adopters(t: int, params: BassParameters) -> float:
    """Expected new adopters in discrete period ``t`` (t >= 1)."""
    if t < 1:
        raise ValueError(f"period t={t} must be >= 1 for discrete new_adopters")
    return cumulative_adopters(t, params) - cumulative_adopters(t - 1, params)


def peak_period(params: BassParameters) -> Optional[float]:
    """Continuous-time peak adoption period t* = ln(q/p) / (p+q).

    Returns:
        ``None`` when ``q <= p`` (pure-innovation case has no interior peak;
        adoption decays monotonically after t=0).
    """
    if params.q <= params.p:
        return None
    return log(params.q / params.p) / (params.p + params.q)


def peak_new_adopters(params: BassParameters) -> float:
    """Peak new-adopter rate n* = m * (p+q)^2 / (4*q).

    For the pure-innovation case ``q == 0`` the Bass model reduces to
    exponential decay of potential, so the peak occurs at t=0+ with
    instantaneous rate ``m * p``.
    """
    if params.q == 0:
        return params.m * params.p
    return params.m * (params.p + params.q) ** 2 / (4.0 * params.q)


# ---------------------------------------------------------------------------
# Forecast builder
# ---------------------------------------------------------------------------

def forecast(
    params: BassParameters,
    horizon: int,
) -> BassForecast:
    """Build a multi-period Bass forecast.

    Args:
        params: Model parameters.
        horizon: Number of discrete periods to forecast (>= 1).

    Returns:
        ``BassForecast`` with one point per period from 1..horizon.
    """
    if horizon < 1:
        raise ValueError(f"horizon={horizon} must be >= 1")

    points: List[BassForecastPoint] = []
    prev_cum = 0.0
    for t in range(1, horizon + 1):
        frac = adoption_fraction(t, params.p, params.q)
        cum = params.m * frac
        # Numerical safety: cumulative is monotonically non-decreasing in
        # the Bass model, so floor the new adopters at zero.
        incr = max(0.0, cum - prev_cum)
        points.append(
            BassForecastPoint(
                period=t,
                cumulative_adopters=cum,
                new_adopters=incr,
                adoption_fraction=frac,
            )
        )
        prev_cum = cum

    return BassForecast(parameters=params, points=tuple(points))


# ---------------------------------------------------------------------------
# Simple grid-search parameter fitter
# ---------------------------------------------------------------------------

def _sse(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Sum of squared errors between two equal-length sequences."""
    if len(actual) != len(predicted):
        raise ValueError(
            "actual and predicted sequences must have equal length"
        )
    return sum((a - b) ** 2 for a, b in zip(actual, predicted))


def fit_parameters(
    observed_new_adopters: Sequence[float],
    market_potential: float,
    p_grid: Optional[Sequence[float]] = None,
    q_grid: Optional[Sequence[float]] = None,
) -> BassParameters:
    """Fit Bass ``p`` and ``q`` by grid-search SSE minimization.

    A lightweight estimator that avoids adding SciPy as a dependency while
    still producing useful fits for Rx-launch backcasting. For publication-
    grade fits, see Srinivasan & Mason (1986) or nonlinear least squares.

    Args:
        observed_new_adopters: Observed new adopters per period, starting
            at period 1.
        market_potential: Known or assumed ``m``.
        p_grid: Candidate values for ``p``. Defaults to a log-spaced grid
            across the typical Rx range.
        q_grid: Candidate values for ``q``. Defaults to a linear grid
            across the typical Rx range.

    Returns:
        Best-fit ``BassParameters``.
    """
    if not observed_new_adopters:
        raise ValueError("observed_new_adopters must not be empty")
    if any(x < 0 for x in observed_new_adopters):
        raise ValueError("observed_new_adopters must be non-negative")
    if market_potential <= 0:
        raise ValueError("market_potential must be positive")

    if p_grid is None:
        p_grid = [0.001, 0.003, 0.005, 0.01, 0.02, 0.03, 0.05]
    if q_grid is None:
        q_grid = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

    horizon = len(observed_new_adopters)
    best: Optional[Tuple[float, float, float]] = None  # (sse, p, q)

    for p in p_grid:
        for q in q_grid:
            try:
                params = BassParameters(p=p, q=q, m=market_potential)
            except ValueError:
                continue
            fc = forecast(params, horizon=horizon)
            predicted = [pt.new_adopters for pt in fc.points]
            err = _sse(observed_new_adopters, predicted)
            if best is None or err < best[0]:
                best = (err, p, q)

    assert best is not None  # At least one grid point must be valid.
    _, best_p, best_q = best
    return BassParameters(p=best_p, q=best_q, m=market_potential)


# ---------------------------------------------------------------------------
# Helper: build a forecast directly from a launch-planning row
# ---------------------------------------------------------------------------

def forecast_from_launch_row(
    row: pd.Series,
    horizon: int,
) -> BassForecast:
    """Build a forecast from a tabular launch-planning row.

    Expected columns: ``product_name`` (optional), ``p``, ``q``,
    ``market_potential``, ``launch_period_label`` (optional).
    """
    required = ("p", "q", "market_potential")
    missing = [c for c in required if c not in row.index]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    params = BassParameters(
        p=float(row["p"]),
        q=float(row["q"]),
        m=float(row["market_potential"]),
        product_name=row.get("product_name"),
        launch_period_label=row.get("launch_period_label"),
    )
    return forecast(params, horizon=horizon)
