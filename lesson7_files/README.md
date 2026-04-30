# E-commerce Business Analytics

A configurable, modular framework for analyzing e-commerce sales data.
The refactored solution separates data loading, metric calculation, and
visualization into reusable components that work for any date range.

## Project Structure

```
lesson7_files/
├── EDA_Refactored.ipynb     # Main analysis notebook
├── data_loader.py           # Data loading, cleaning, and joining
├── business_metrics.py      # Metric calculations and visualizations
├── requirements.txt         # Python dependencies
├── README.md                # This file
└── ecommerce_data/          # CSV data files
    ├── orders_dataset.csv
    ├── order_items_dataset.csv
    ├── products_dataset.csv
    ├── customers_dataset.csv
    ├── order_reviews_dataset.csv
    └── order_payments_dataset.csv
```

## Quick Start

1. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

2. Run the Streamlit dashboard:
   ```bash
   .venv/bin/streamlit run dashboard.py
   ```

3. Or open the notebook:
   ```bash
   .venv/bin/jupyter notebook EDA_Refactored.ipynb
   ```

## Dashboard

`dashboard.py` is a Streamlit application with the following layout:

**Header** — Title on the left; Year and Month filters on the right (default: 2023, All Months). All charts update when filters change.

**KPI Row** — Four metric cards with trend indicators vs the prior year:
- Total Revenue, Monthly Growth, Avg Order Value, Total Orders
- Green arrow = positive trend, red arrow = negative trend

**Charts (2 x 2 grid)** — All charts use Plotly:
- Monthly Revenue Trend: solid line = selected year, dashed = prior year, Y-axis in $K/$M
- Top 10 Categories: horizontal bar chart with blue gradient, sorted descending by revenue
- Revenue by State: US choropleth map with blue gradient
- Customer Satisfaction by Delivery Speed: bar chart of avg review score per delivery bucket

**Bottom Row** — Two summary cards:
- Average Delivery Time with trend indicator (lower = better = green)
- Review Score with star rating and "Average Review Score" subtitle

## Configuring the Analysis

Edit the configuration cell at the top of the notebook:

```python
ANALYSIS_YEAR   = 2023   # Year to analyze
COMPARISON_YEAR = 2022   # Comparison year (set to None to skip YoY)
ANALYSIS_MONTH  = None   # Specific month (1-12) or None for the full year
DATA_PATH       = 'ecommerce_data/'
```

To analyze a specific quarter, run the notebook once per month and collect results,
or set `ANALYSIS_MONTH` to filter down to a single month.

## Module Reference

### data_loader.py

Provides `EcommerceDataLoader` and the convenience function `load_and_process_data`.

```python
from data_loader import load_and_process_data

loader, processed_data = load_and_process_data('ecommerce_data/')

# Create a filtered sales dataset (delivered orders only)
sales_data = loader.create_sales_dataset(
    year_filter=2023,
    month_filter=None,       # None = full year
    status_filter='delivered'
)
```

`create_sales_dataset` returns a denormalized DataFrame joining order items,
orders, products, customers, reviews, and computed delivery days.

### business_metrics.py

Provides `BusinessMetricsCalculator`, `MetricsVisualizer`, and `print_metrics_summary`.

```python
from business_metrics import BusinessMetricsCalculator, MetricsVisualizer, print_metrics_summary

calc   = BusinessMetricsCalculator(sales_data)
report = calc.generate_comprehensive_report(current_year=2023, previous_year=2022)

print_metrics_summary(report)

viz = MetricsVisualizer(report)
viz.plot_revenue_trend()
viz.plot_category_performance()
viz.plot_geographic_heatmap()
viz.plot_review_distribution()
viz.plot_delivery_satisfaction()
```

## Notebook Sections

| Section | What it covers |
|---------|---------------|
| Introduction | Business objectives and configuration parameters |
| Data Loading | Loading all CSV files and summarizing dataset sizes |
| Data Dictionary | Column definitions and calculated metric explanations |
| Data Preparation | Building the analysis and comparison datasets |
| Order Status | Distribution of all order statuses in the analysis year |
| Revenue Analysis | Total revenue, AOV, YoY growth, monthly trend chart |
| Product Performance | Revenue by category with horizontal bar chart |
| Geographic Analysis | Revenue by state with US choropleth map |
| Customer Experience | Review score distribution and delivery speed vs satisfaction |
| Summary | Executive summary and data-driven recommendations |

## Key Business Metrics

- **Total Revenue** - Sum of item prices for all delivered orders
- **Average Order Value (AOV)** - Average total value per unique order
- **Revenue Growth Rate** - Year-over-year percentage change in revenue
- **Review Score Distribution** - Proportion of orders at each rating (1-5)
- **Delivery Speed Categories** - 1-3 days, 4-7 days, 8+ days
- **Delivery Satisfaction** - Average review score per delivery speed category
