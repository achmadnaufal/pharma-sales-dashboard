# Pharma Sales Dashboard

Streamlit sales performance dashboard for pharmaceutical field teams

## Features
- Data ingestion from CSV/Excel input files
- Automated analysis and KPI calculation
- Summary statistics and trend reporting
- Sample data generator for testing and development

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from src.main import PharmaSalesDashboard

analyzer = PharmaSalesDashboard()
df = analyzer.load_data("data/sample.csv")
result = analyzer.analyze(df)
print(result)
```

## Data Format

Expected CSV columns: `rep_id, territory, product, month, actual_units, target_units, revenue_usd`

## Project Structure

```
pharma-sales-dashboard/
├── src/
│   ├── main.py          # Core analysis logic
│   └── data_generator.py # Sample data generator
├── data/                # Data directory (gitignored for real data)
├── examples/            # Usage examples
├── requirements.txt
└── README.md
```

## License

MIT License — free to use, modify, and distribute.
