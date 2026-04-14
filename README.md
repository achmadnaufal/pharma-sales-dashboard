# Pharma Sales Dashboard

Streamlit sales performance dashboard for pharmaceutical field teams.

## Features

- Data ingestion from CSV / Excel input files
- Automated analysis and KPI calculation
- Summary statistics and trend reporting
- Territory-level aggregation with target achievement
- Time-series filtering by year and month
- Sample data for demo purposes
- Full pytest test suite

## Installation

```bash
pip install -r requirements.txt
```

To run the tests you also need pytest:

```bash
pip install pytest
```

## Quick Start

```python
from src.main import PharmaSalesDashboard

dashboard = PharmaSalesDashboard()
result = dashboard.run("demo/sample_data.csv")

print("Total records:", result["total_records"])
print("Revenue total:", result["totals"]["revenue_usd"])
print("Territory summary:", result["territory_summary"])
```

## Sample Data

A ready-to-use sample file lives at `demo/sample_data.csv` with 20 rows of
realistic pharma sales data.

### Columns

| Column | Type | Description |
|---|---|---|
| `rep_id` | string | Sales representative identifier |
| `rep_name` | string | Representative full name |
| `territory` | string | Sales territory (e.g. Northeast) |
| `product_name` | string | Product SKU and strength |
| `therapeutic_area` | string | Medical area (e.g. Cardiology) |
| `month` | string | Month name (e.g. January) |
| `year` | integer | Four-digit year |
| `units_sold` | float | Actual units sold |
| `revenue_usd` | float | Revenue in USD |
| `target_units` | float | Unit target for the period |
| `calls_made` | integer | Total HCP calls made |
| `hcp_met` | integer | Number of unique HCPs met |
| `market_share_pct` | float | Product market share % |

### Preview

```
rep_id,rep_name,territory,product_name,...,units_sold,revenue_usd,target_units
REP001,Sarah Johnson,Northeast,Cardivex 10mg,...,142,71000.00,130
REP002,Michael Chen,Southeast,Cardivex 10mg,...,115,57500.00,120
...
```

## Example Usage

### Load and analyze data

```python
from src.main import PharmaSalesDashboard

dashboard = PharmaSalesDashboard()

# Full pipeline from file
result = dashboard.run("demo/sample_data.csv")

# Or step by step
df = dashboard.load_data("demo/sample_data.csv")
dashboard.validate(df)
result = dashboard.analyze(df)

# Export results as a tidy DataFrame
output_df = dashboard.to_dataframe(result)
output_df.to_csv("output/summary.csv", index=False)
```

### Helper functions

```python
from src.main import (
    compute_target_achievement,
    compute_revenue,
    compute_market_share,
    aggregate_by_territory,
    filter_time_series,
)

# Target achievement (safe against zero targets)
pct = compute_target_achievement(units_sold=142, target_units=130)  # 109.23

# Revenue
rev = compute_revenue(units_sold=142, price_per_unit=500.0)  # 71000.0

# Market share (safe against zero total market)
share = compute_market_share(product_units=142, total_market_units=1000)  # 14.2

# Territory rollup
import pandas as pd
df = pd.read_csv("demo/sample_data.csv")
territory_df = aggregate_by_territory(df)

# Time-series filter
q1 = filter_time_series(df, year=2025, month="January")
```

### Generate larger datasets

```python
from src.data_generator import generate_sample

df = generate_sample(n=500, seed=99)
df.to_csv("data/large_sample.csv", index=False)
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --tb=short

# Run a specific test class
pytest tests/test_dashboard.py::TestComputeTargetAchievement -v
```

Expected output:

```
tests/test_dashboard.py::TestComputeRevenue::test_basic_revenue_calculation PASSED
tests/test_dashboard.py::TestComputeTargetAchievement::test_zero_target_returns_zero PASSED
...
```

## Project Structure

```
pharma-sales-dashboard/
├── src/
│   ├── __init__.py
│   ├── main.py            # Core dashboard class and helper functions
│   └── data_generator.py  # Synthetic data generator
├── tests/
│   ├── __init__.py
│   └── test_dashboard.py  # pytest test suite
├── demo/
│   └── sample_data.csv    # 20-row realistic sample dataset
├── examples/
│   └── basic_usage.py     # Runnable usage example
├── data/                  # Data directory (gitignored for real data)
├── CHANGELOG.md
├── requirements.txt
└── README.md
```

## License

MIT License - free to use, modify, and distribute.
