# Changelog

## [0.4.0] - 2026-04-21
### Added
- `src/bass_diffusion.py` implementing the Bass (1969) new-product diffusion
  model for pharma launch uptake forecasting: `BassParameters`,
  `BassForecast`, `adoption_fraction`, `cumulative_adopters`, `new_adopters`,
  `peak_period`, `peak_new_adopters`, `forecast`, `fit_parameters` (grid-search
  estimator), and `forecast_from_launch_row` for tabular batch forecasting.
- `tests/test_bass_diffusion.py` with 43 pytest cases covering parameter
  validation, closed-form identities, monotonicity, peak timing,
  immutability, and DataFrame helpers.
- `sample_data/bass_diffusion_samples.csv` with 15 realistic launch-plan
  rows (product, therapeutic area, territory, specialty, p, q, m, horizon).
- README section with a runnable Bass diffusion example and updated
  project structure.

## [0.3.0] - 2026-04-19
### Added
- `src/metrics.py` module with revenue attainment, YoY growth, rep ranking,
  cohort comparison, and flexible period filtering helpers.
- `src/streamlit_app.py` entry-point with four tabs: Overview, Rep Leaderboard,
  YoY Growth, Cohort Comparison.
- `tests/test_metrics.py` - 39 new tests covering the metrics module's edge
  cases (zero / negative / NaN denominators, tied ranks, empty cohorts,
  single-year YoY, unknown month names).
- Expanded `demo/sample_data.csv` schema with `region`, `target_revenue_usd`,
  `calls_target`, `new_prescribers` plus prior-year rows to enable YoY demos.
- Expanded README with Overview, Installation, Running, Step-by-Step Usage,
  Sections / Tabs, Data Schema.

### Changed
- Sample data now spans 2024 and 2025 so YoY metrics render out-of-the-box.

## [0.2.0] - 2026-04-15
### Added
- Unit tests with pytest
- Sample data for demo purposes
- Comprehensive docstrings
- Input validation and edge case handling
- Improved README with usage examples
