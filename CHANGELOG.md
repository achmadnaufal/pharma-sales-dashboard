# Changelog

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
