"""
Business metrics calculation module for e-commerce data analysis.

Provides:
    - BusinessMetricsCalculator: computes revenue, product, geographic, and
      customer experience metrics from a processed sales DataFrame.
    - MetricsVisualizer: generates matplotlib/plotly charts from a metrics report.
    - print_metrics_summary: prints a formatted console summary of a report.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt


DELIVERY_CATEGORIES = ['1-3 days', '4-7 days', '8+ days']

BUSINESS_COLOR_PALETTE = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
]


def categorize_delivery_speed(days: float) -> str:
    """Return a delivery speed label for a given number of delivery days."""
    if pd.isna(days):
        return 'Unknown'
    if days <= 3:
        return '1-3 days'
    if days <= 7:
        return '4-7 days'
    return '8+ days'


def format_currency(value: float) -> str:
    """Format a number as a USD currency string."""
    return f"${value:,.2f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format a number as a percentage string."""
    return f"{value:.{decimals}f}%"


class BusinessMetricsCalculator:
    """Calculates business performance metrics from a processed e-commerce sales DataFrame."""

    def __init__(self, sales_data: pd.DataFrame):
        """
        Args:
            sales_data: DataFrame with at minimum the columns price, order_id,
                        and purchase_year. Optional enrichment columns include
                        purchase_month, product_category_name, customer_state,
                        review_score, and delivery_days.
        """
        self.sales_data = sales_data.copy()
        self._validate_data()

    def _validate_data(self) -> None:
        required = ['price', 'order_id', 'purchase_year']
        missing = [c for c in required if c not in self.sales_data.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

    def calculate_revenue_metrics(
        self,
        current_year: int,
        previous_year: Optional[int] = None,
    ) -> Dict:
        """
        Calculate revenue KPIs for a given year with optional YoY comparison.

        Args:
            current_year: The year to analyze.
            previous_year: Optional prior year for growth rate calculations.

        Returns:
            Dictionary of revenue metrics. If previous_year is provided, also
            contains revenue_growth_rate, order_growth_rate, aov_growth_rate,
            and the corresponding previous-year baseline values.
        """
        current = self.sales_data[self.sales_data['purchase_year'] == current_year]

        metrics = {
            'total_revenue': current['price'].sum(),
            'total_orders': current['order_id'].nunique(),
            'average_order_value': current.groupby('order_id')['price'].sum().mean(),
            'total_items_sold': len(current),
        }

        if previous_year:
            previous = self.sales_data[self.sales_data['purchase_year'] == previous_year]
            prev_revenue = previous['price'].sum()
            prev_orders = previous['order_id'].nunique()
            prev_aov = previous.groupby('order_id')['price'].sum().mean()

            metrics.update({
                'previous_year_revenue': prev_revenue,
                'previous_year_orders': prev_orders,
                'previous_year_aov': prev_aov,
                'revenue_growth_rate': (
                    (metrics['total_revenue'] - prev_revenue) / prev_revenue * 100
                    if prev_revenue > 0 else 0
                ),
                'order_growth_rate': (
                    (metrics['total_orders'] - prev_orders) / prev_orders * 100
                    if prev_orders > 0 else 0
                ),
                'aov_growth_rate': (
                    (metrics['average_order_value'] - prev_aov) / prev_aov * 100
                    if prev_aov > 0 else 0
                ),
            })

        return metrics

    def calculate_monthly_trends(self, year: int) -> pd.DataFrame:
        """
        Calculate month-over-month revenue, order, and AOV trends.

        Args:
            year: The year to analyze.

        Returns:
            DataFrame with columns: month, revenue, orders, avg_order_value,
            revenue_growth (%), order_growth (%), aov_growth (%).
        """
        year_data = self.sales_data[self.sales_data['purchase_year'] == year]

        monthly = (
            year_data.groupby('purchase_month')
            .agg(revenue=('price', 'sum'), orders=('order_id', 'nunique'))
            .reset_index()
            .rename(columns={'purchase_month': 'month'})
        )

        # AOV: average of per-order totals within each month
        aov_by_month = (
            year_data.groupby(['purchase_month', 'order_id'])['price']
            .sum()
            .groupby(level='purchase_month')
            .mean()
            .rename('avg_order_value')
            .reset_index()
            .rename(columns={'purchase_month': 'month'})
        )
        monthly = monthly.merge(aov_by_month, on='month', how='left')

        monthly['revenue_growth'] = monthly['revenue'].pct_change() * 100
        monthly['order_growth'] = monthly['orders'].pct_change() * 100
        monthly['aov_growth'] = monthly['avg_order_value'].pct_change() * 100

        return monthly

    def analyze_product_performance(self, year: int, top_n: int = 10) -> Dict:
        """
        Aggregate revenue by product category and identify top performers.

        Args:
            year: The year to analyze.
            top_n: Number of leading categories to surface separately.

        Returns:
            Dictionary with keys 'all_categories' and 'top_categories' (DataFrames),
            or {'error': message} if product_category_name is missing.
        """
        year_data = self.sales_data[self.sales_data['purchase_year'] == year]

        if 'product_category_name' not in year_data.columns:
            return {'error': 'Product category data not available'}

        category_metrics = (
            year_data.groupby('product_category_name')
            .agg(
                total_revenue=('price', 'sum'),
                avg_item_price=('price', 'mean'),
                items_sold=('price', 'count'),
                unique_orders=('order_id', 'nunique'),
            )
            .round(2)
            .reset_index()
            .sort_values('total_revenue', ascending=False)
        )

        total_rev = category_metrics['total_revenue'].sum()
        category_metrics['revenue_share'] = (
            category_metrics['total_revenue'] / total_rev * 100
        ).round(2)

        return {
            'all_categories': category_metrics,
            'top_categories': category_metrics.head(top_n),
        }

    def analyze_geographic_performance(self, year: int) -> pd.DataFrame:
        """
        Aggregate revenue and orders by customer state.

        Args:
            year: The year to analyze.

        Returns:
            DataFrame with columns state, revenue, orders, avg_order_value,
            sorted by revenue descending.
            Returns a DataFrame with an 'error' column if customer_state is missing.
        """
        year_data = self.sales_data[self.sales_data['purchase_year'] == year]

        if 'customer_state' not in year_data.columns:
            return pd.DataFrame({'error': ['Geographic data not available']})

        state_metrics = (
            year_data.groupby('customer_state')
            .agg(revenue=('price', 'sum'), orders=('order_id', 'nunique'))
            .reset_index()
            .rename(columns={'customer_state': 'state'})
        )

        # AOV: average of per-order totals within each state
        aov_by_state = (
            year_data.groupby(['customer_state', 'order_id'])['price']
            .sum()
            .groupby(level='customer_state')
            .mean()
            .rename('avg_order_value')
            .reset_index()
            .rename(columns={'customer_state': 'state'})
        )
        state_metrics = state_metrics.merge(aov_by_state, on='state', how='left')

        return state_metrics.sort_values('revenue', ascending=False).reset_index(drop=True)

    def analyze_customer_satisfaction(self, year: int) -> Dict:
        """
        Compute review score statistics and the per-score proportion distribution.

        Args:
            year: The year to analyze.

        Returns:
            Dictionary with avg_review_score, total_reviews, score_distribution
            (dict mapping score -> proportion), score_5_percentage,
            score_4_plus_percentage, score_1_2_percentage.
            Returns {'error': message} if review_score is missing.
        """
        year_data = self.sales_data[self.sales_data['purchase_year'] == year]

        if 'review_score' not in year_data.columns:
            return {'error': 'Review data not available'}

        order_data = year_data.drop_duplicates('order_id').dropna(subset=['review_score'])

        score_dist = (
            order_data['review_score'].value_counts(normalize=True).sort_index()
        )

        return {
            'avg_review_score': order_data['review_score'].mean(),
            'total_reviews': len(order_data),
            'score_distribution': score_dist.to_dict(),
            'score_5_percentage': (order_data['review_score'] == 5).mean() * 100,
            'score_4_plus_percentage': (order_data['review_score'] >= 4).mean() * 100,
            'score_1_2_percentage': (order_data['review_score'] <= 2).mean() * 100,
        }

    def analyze_delivery_performance(self, year: int) -> Dict:
        """
        Compute delivery speed summary statistics.

        Args:
            year: The year to analyze.

        Returns:
            Dictionary with avg_delivery_days, median_delivery_days,
            fast_delivery_percentage (<=3 days), slow_delivery_percentage (>7 days).
            Returns {'error': message} if delivery_days is missing.
        """
        year_data = self.sales_data[self.sales_data['purchase_year'] == year]

        if 'delivery_days' not in year_data.columns:
            return {'error': 'Delivery data not available'}

        order_data = (
            year_data.drop_duplicates('order_id').dropna(subset=['delivery_days'])
        )

        return {
            'avg_delivery_days': order_data['delivery_days'].mean(),
            'median_delivery_days': order_data['delivery_days'].median(),
            'fast_delivery_percentage': (order_data['delivery_days'] <= 3).mean() * 100,
            'slow_delivery_percentage': (order_data['delivery_days'] > 7).mean() * 100,
        }

    def analyze_delivery_satisfaction(self, year: int) -> pd.DataFrame:
        """
        Compute average review score for each delivery speed category.

        Args:
            year: The year to analyze.

        Returns:
            DataFrame with columns delivery_category and avg_review_score,
            ordered as '1-3 days', '4-7 days', '8+ days'.
            Returns an empty DataFrame if required columns are missing.
        """
        year_data = self.sales_data[self.sales_data['purchase_year'] == year]

        if (
            'delivery_days' not in year_data.columns
            or 'review_score' not in year_data.columns
        ):
            return pd.DataFrame()

        order_data = (
            year_data.drop_duplicates('order_id')
            .dropna(subset=['delivery_days', 'review_score'])
            .copy()
        )
        order_data['delivery_category'] = order_data['delivery_days'].apply(
            categorize_delivery_speed
        )

        result = (
            order_data.groupby('delivery_category')['review_score']
            .mean()
            .reset_index()
            .rename(columns={'review_score': 'avg_review_score'})
        )

        result['delivery_category'] = pd.Categorical(
            result['delivery_category'],
            categories=DELIVERY_CATEGORIES,
            ordered=True,
        )
        return result.sort_values('delivery_category').reset_index(drop=True)

    def generate_comprehensive_report(
        self,
        current_year: int,
        previous_year: Optional[int] = None,
    ) -> Dict:
        """
        Compile all metric sections into a single report dictionary.

        Args:
            current_year: The year to analyze.
            previous_year: Optional comparison year for growth calculations.

        Returns:
            Dictionary with keys: analysis_period, comparison_period,
            revenue_metrics, monthly_trends, product_performance,
            geographic_performance, customer_satisfaction,
            delivery_performance, delivery_satisfaction.
        """
        return {
            'analysis_period': current_year,
            'comparison_period': previous_year,
            'revenue_metrics': self.calculate_revenue_metrics(current_year, previous_year),
            'monthly_trends': self.calculate_monthly_trends(current_year),
            'product_performance': self.analyze_product_performance(current_year),
            'geographic_performance': self.analyze_geographic_performance(current_year),
            'customer_satisfaction': self.analyze_customer_satisfaction(current_year),
            'delivery_performance': self.analyze_delivery_performance(current_year),
            'delivery_satisfaction': self.analyze_delivery_satisfaction(current_year),
        }


class MetricsVisualizer:
    """Generates charts from a business metrics report produced by BusinessMetricsCalculator."""

    def __init__(self, report_data: Dict):
        """
        Args:
            report_data: Output of BusinessMetricsCalculator.generate_comprehensive_report.
        """
        self.report_data = report_data
        self.color_palette = BUSINESS_COLOR_PALETTE

    def plot_revenue_trend(self, figsize: Tuple[int, int] = (12, 6)) -> plt.Figure:
        """
        Line chart of monthly revenue with data labels.

        Args:
            figsize: Figure width and height in inches.

        Returns:
            Matplotlib Figure.
        """
        monthly = self.report_data['monthly_trends']
        year = self.report_data['analysis_period']

        fig, ax = plt.subplots(figsize=figsize)
        ax.plot(
            monthly['month'], monthly['revenue'],
            marker='o', linewidth=2, markersize=8, color=self.color_palette[0],
        )
        ax.set_title(
            f'Monthly Revenue Trend - {year}', fontsize=16, fontweight='bold', pad=20
        )
        ax.set_xlabel('Month', fontsize=12)
        ax.set_ylabel('Revenue (USD)', fontsize=12)
        ax.set_xticks(monthly['month'])
        ax.grid(True, alpha=0.3)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x:,.0f}'))

        for _, row in monthly.iterrows():
            ax.annotate(
                f'${row["revenue"]:,.0f}',
                (row['month'], row['revenue']),
                textcoords='offset points', xytext=(0, 10),
                ha='center', fontsize=9,
            )

        plt.tight_layout()
        return fig

    def plot_category_performance(
        self, top_n: int = 10, figsize: Tuple[int, int] = (12, 8)
    ) -> plt.Figure:
        """
        Horizontal bar chart of the top product categories by revenue.

        Args:
            top_n: Number of categories to display.
            figsize: Figure width and height in inches.

        Returns:
            Matplotlib Figure.
        """
        if 'error' in self.report_data['product_performance']:
            fig, ax = plt.subplots(figsize=figsize)
            ax.text(
                0.5, 0.5, 'Product category data not available',
                ha='center', va='center', transform=ax.transAxes, fontsize=14,
            )
            return fig

        year = self.report_data['analysis_period']
        category_data = (
            self.report_data['product_performance']['top_categories'].head(top_n)
        )

        fig, ax = plt.subplots(figsize=figsize)
        ax.barh(
            category_data['product_category_name'],
            category_data['total_revenue'],
            color=self.color_palette[1],
        )
        ax.set_title(
            f'Top {top_n} Product Categories by Revenue - {year}',
            fontsize=16, fontweight='bold', pad=20,
        )
        ax.set_xlabel('Revenue (USD)', fontsize=12)
        ax.set_ylabel('Product Category', fontsize=12)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'${x:,.0f}'))

        for i, (rev, _) in enumerate(
            zip(category_data['total_revenue'], category_data['product_category_name'])
        ):
            ax.text(rev, i, f'  ${rev:,.0f}', va='center', fontsize=9)

        plt.tight_layout()
        return fig

    def plot_geographic_heatmap(self) -> go.Figure:
        """
        Choropleth map of revenue by US state.

        Returns:
            Plotly Figure.
        """
        geo_data = self.report_data['geographic_performance']
        year = self.report_data['analysis_period']

        if 'error' in geo_data.columns:
            fig = go.Figure()
            fig.add_annotation(
                text='Geographic data not available',
                x=0.5, y=0.5, showarrow=False, font_size=16,
            )
            return fig

        fig = px.choropleth(
            geo_data,
            locations='state',
            color='revenue',
            locationmode='USA-states',
            scope='usa',
            title=f'Revenue by State - {year}',
            color_continuous_scale='Blues',
            labels={'revenue': 'Revenue (USD)'},
        )
        fig.update_layout(
            title_font_size=16,
            title_x=0.5,
            geo=dict(showframe=False, showcoastlines=True),
        )
        return fig

    def plot_review_distribution(self, figsize: Tuple[int, int] = (10, 6)) -> plt.Figure:
        """
        Horizontal bar chart of review score proportions (scores 1 through 5).

        Args:
            figsize: Figure width and height in inches.

        Returns:
            Matplotlib Figure.
        """
        year = self.report_data['analysis_period']
        satisfaction = self.report_data['customer_satisfaction']

        fig, ax = plt.subplots(figsize=figsize)

        if 'error' in satisfaction or 'score_distribution' not in satisfaction:
            ax.text(
                0.5, 0.5, 'Review data not available',
                ha='center', va='center', transform=ax.transAxes, fontsize=14,
            )
            return fig

        dist = pd.Series(satisfaction['score_distribution']).sort_index()

        ax.barh(dist.index.astype(int), dist.values, color=self.color_palette[0])
        ax.set_xlabel('Proportion of Reviews', fontsize=12)
        ax.set_ylabel('Review Score', fontsize=12)
        ax.set_title(
            f'Review Score Distribution - {year}', fontsize=16, fontweight='bold', pad=20
        )
        ax.set_yticks([1, 2, 3, 4, 5])
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.0%}'))

        for score, prop in dist.items():
            ax.text(prop + 0.002, int(score), f'{prop:.1%}', va='center', fontsize=10)

        plt.tight_layout()
        return fig

    def plot_delivery_satisfaction(self, figsize: Tuple[int, int] = (10, 6)) -> plt.Figure:
        """
        Bar chart of average review score by delivery speed category.

        Args:
            figsize: Figure width and height in inches.

        Returns:
            Matplotlib Figure.
        """
        year = self.report_data['analysis_period']
        data = self.report_data.get('delivery_satisfaction', pd.DataFrame())

        fig, ax = plt.subplots(figsize=figsize)

        if data.empty:
            ax.text(
                0.5, 0.5, 'Delivery satisfaction data not available',
                ha='center', va='center', transform=ax.transAxes, fontsize=14,
            )
            return fig

        bars = ax.bar(
            data['delivery_category'], data['avg_review_score'],
            color=self.color_palette[2],
        )
        ax.set_title(
            f'Average Review Score by Delivery Speed - {year}',
            fontsize=16, fontweight='bold', pad=20,
        )
        ax.set_xlabel('Delivery Speed', fontsize=12)
        ax.set_ylabel('Average Review Score (out of 5)', fontsize=12)
        ax.set_ylim(0, 5)

        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2, height + 0.05,
                f'{height:.2f}', ha='center', fontsize=11,
            )

        plt.tight_layout()
        return fig


def print_metrics_summary(report: Dict) -> None:
    """
    Print a formatted console summary of a comprehensive metrics report.

    Args:
        report: Output of BusinessMetricsCalculator.generate_comprehensive_report.
    """
    print("=" * 60)
    print(f"BUSINESS METRICS SUMMARY - {report['analysis_period']}")
    print("=" * 60)

    revenue = report['revenue_metrics']
    print("\nREVENUE PERFORMANCE:")
    print(f"  Total Revenue:       {format_currency(revenue['total_revenue'])}")
    print(f"  Total Orders:        {revenue['total_orders']:,}")
    print(f"  Average Order Value: {format_currency(revenue['average_order_value'])}")

    if 'revenue_growth_rate' in revenue:
        comparison = report['comparison_period']
        print(f"  Revenue Growth:      {format_percentage(revenue['revenue_growth_rate'])} vs {comparison}")
        print(f"  Order Growth:        {format_percentage(revenue['order_growth_rate'])} vs {comparison}")

    satisfaction = report['customer_satisfaction']
    if 'error' not in satisfaction:
        print("\nCUSTOMER SATISFACTION:")
        print(f"  Average Review Score:        {satisfaction['avg_review_score']:.2f} / 5.0")
        print(f"  High Satisfaction (4+ stars): {format_percentage(satisfaction['score_4_plus_percentage'])}")
        print(f"  Low Satisfaction (1-2 stars): {format_percentage(satisfaction['score_1_2_percentage'])}")

    delivery = report['delivery_performance']
    if 'error' not in delivery:
        print("\nDELIVERY PERFORMANCE:")
        print(f"  Average Delivery Time:      {delivery['avg_delivery_days']:.1f} days")
        print(f"  Fast Deliveries (<=3 days): {format_percentage(delivery['fast_delivery_percentage'])}")
        print(f"  Slow Deliveries (>7 days):  {format_percentage(delivery['slow_delivery_percentage'])}")

    print("=" * 60)
