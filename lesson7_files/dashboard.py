"""
E-commerce Analytics Dashboard
"""

import math
import warnings

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from business_metrics import categorize_delivery_speed
from data_loader import load_and_process_data

warnings.filterwarnings("ignore")

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="E-commerce Analytics",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ─────────────────────────────────────────────────────────────────

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}

CHART_H     = 360
CHART_MARGIN = dict(t=48, b=40, l=55, r=20)
PLOT_BG     = "white"
GRID_CLR    = "#e8e8e8"
BLUE_LINE   = "#1565C0"
BLUE_PREV   = "#90CAF9"
GREEN       = "#16a34a"
RED         = "#dc2626"
NEUTRAL     = "#94a3b8"

# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
  /* Remove default Streamlit top padding */
  .block-container { padding-top: 1.5rem; }

  /* ── KPI cards (uniform height per row) ── */
  .kpi-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    height: 115px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  }
  .kpi-label {
    font-size: 0.72rem;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0;
  }
  .kpi-value {
    font-size: 1.85rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0;
    line-height: 1;
  }
  .kpi-trend { font-size: 0.77rem; margin: 0; }

  /* ── Bottom cards (uniform height per row) ── */
  .btm-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    height: 155px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  }
  .btm-label {
    font-size: 0.72rem;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0;
  }
  .btm-value {
    font-size: 2.2rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0;
    line-height: 1;
  }
  .btm-stars { font-size: 1.2rem; color: #f59e0b; letter-spacing: 3px; margin: 0; }
  .btm-sub   { font-size: 0.78rem; color: #64748b; margin: 0; }

  /* ── Trend colours ── */
  .t-pos { color: #16a34a; }
  .t-neg { color: #dc2626; }
  .t-neu { color: #94a3b8; }
</style>
""", unsafe_allow_html=True)

# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data
def load_data():
    return load_and_process_data("ecommerce_data/")


# ── Formatting helpers ────────────────────────────────────────────────────────

def fmt_currency(v: float) -> str:
    """Format a dollar value with K / M suffix."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "N/A"
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:.0f}"


def trend_span(current, previous, invert: bool = False) -> str:
    """
    Return an HTML <span> showing percentage change with colour and direction.
    invert=True marks a decrease as positive (e.g. lower delivery time = good).
    """
    if previous is None or previous == 0:
        return '<span class="t-neu">— vs prior year</span>'
    try:
        if math.isnan(current) or math.isnan(previous):
            return '<span class="t-neu">— vs prior year</span>'
    except TypeError:
        pass

    pct = (current - previous) / abs(previous) * 100
    is_good = (pct < 0) if invert else (pct > 0)
    css   = "t-pos" if is_good else "t-neg"
    arrow = "▲" if pct > 0 else "▼"
    sign  = "+" if pct > 0 else ""
    return f'<span class="{css}">{arrow} {sign}{pct:.2f}% vs prior year</span>'


def make_currency_ticks(max_val: float, n_ticks: int = 5):
    """
    Return (tickvals, ticktext) lists for a Plotly axis with $K / $M labels.
    """
    if max_val <= 0:
        return [0], ["$0"]

    if max_val >= 1_000_000:
        scale, suffix, decimals = 1_000_000, "M", 1
    elif max_val >= 10_000:
        scale, suffix, decimals = 1_000, "K", 0
    else:
        scale, suffix, decimals = 1, "", 0

    scaled_max = max_val / scale
    raw_step   = scaled_max / n_ticks
    if raw_step <= 0:
        return None, None

    magnitude  = 10 ** math.floor(math.log10(raw_step))
    nice_step  = math.ceil(raw_step / magnitude) * magnitude
    n          = math.ceil(scaled_max / nice_step)

    tickvals = [i * nice_step * scale for i in range(n + 1)]
    ticktext = [f"${v / scale:.{decimals}f}{suffix}" for v in tickvals]
    return tickvals, ticktext


# ── Chart builders ────────────────────────────────────────────────────────────

def chart_revenue_trend(current: pd.DataFrame, previous, year: int, prev_year: int):
    """
    Monthly revenue line chart.
      - Solid line  = selected year
      - Dashed line = prior year
    Falls back to a bar comparison when a single month is selected.
    """
    fig = go.Figure()
    multi_month = current["purchase_month"].nunique() > 1

    if multi_month:
        curr_m = current.groupby("purchase_month")["price"].sum().reset_index()
        curr_m.columns = ["month", "revenue"]

        fig.add_trace(go.Scatter(
            x=curr_m["month"], y=curr_m["revenue"],
            mode="lines+markers",
            name=str(year),
            line=dict(color=BLUE_LINE, width=2.5),
            marker=dict(size=7, color=BLUE_LINE),
            hovertemplate="Month %{x} — %{text}<extra></extra>",
            text=[fmt_currency(v) for v in curr_m["revenue"]],
        ))

        all_vals = list(curr_m["revenue"])

        if previous is not None and not previous.empty:
            prev_m = previous.groupby("purchase_month")["price"].sum().reset_index()
            prev_m.columns = ["month", "revenue"]
            all_vals += list(prev_m["revenue"])
            fig.add_trace(go.Scatter(
                x=prev_m["month"], y=prev_m["revenue"],
                mode="lines+markers",
                name=str(prev_year),
                line=dict(color=BLUE_PREV, width=2, dash="dash"),
                marker=dict(size=6, color=BLUE_PREV),
                hovertemplate="Month %{x} — %{text}<extra></extra>",
                text=[fmt_currency(v) for v in prev_m["revenue"]],
            ))

        tickvals, ticktext = make_currency_ticks(max(all_vals))
        fig.update_layout(
            xaxis=dict(
                title="Month", showgrid=True, gridcolor=GRID_CLR,
                tickmode="linear", dtick=1,
            ),
            yaxis=dict(
                title="Revenue", showgrid=True, gridcolor=GRID_CLR,
                tickvals=tickvals, ticktext=ticktext,
                range=[0, max(all_vals) * 1.12],
            ),
        )
    else:
        # Single month → year-over-year bar comparison
        curr_rev = current["price"].sum()
        prev_rev = previous["price"].sum() if (previous is not None and not previous.empty) else 0

        x_vals  = [str(year), str(prev_year)]
        y_vals  = [curr_rev, prev_rev]
        colors  = [BLUE_LINE, BLUE_PREV]

        fig.add_trace(go.Bar(
            x=x_vals, y=y_vals,
            marker_color=colors,
            text=[fmt_currency(v) for v in y_vals],
            textposition="outside",
            hovertemplate="%{x}: %{text}<extra></extra>",
        ))

        tickvals, ticktext = make_currency_ticks(max(y_vals) * 1.1)
        fig.update_layout(
            xaxis=dict(title="Year", showgrid=False),
            yaxis=dict(
                title="Revenue", showgrid=True, gridcolor=GRID_CLR,
                tickvals=tickvals, ticktext=ticktext,
            ),
        )

    fig.update_layout(
        title=dict(text="Monthly Revenue Trend", font=dict(size=14, color="#1e293b")),
        plot_bgcolor=PLOT_BG, paper_bgcolor=PLOT_BG,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        height=CHART_H, margin=CHART_MARGIN,
    )
    return fig


def chart_categories(sales_data: pd.DataFrame):
    """
    Horizontal bar chart of top 10 product categories by revenue.
    Sorted descending (highest at top). Blue gradient — darker = higher revenue.
    """
    if "product_category_name" not in sales_data.columns:
        fig = go.Figure()
        fig.add_annotation(text="Product category data not available",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    cat_rev = (
        sales_data.groupby("product_category_name")["price"]
        .sum()
        .nlargest(10)
        .sort_values(ascending=True)   # ascending → highest bar at top in plotly hbar
    )
    labels = [c.replace("_", " ").title() for c in cat_rev.index]
    values = cat_rev.values.tolist()

    tickvals, ticktext = make_currency_ticks(max(values) * 1.15)

    fig = go.Figure(go.Bar(
        y=labels,
        x=values,
        orientation="h",
        marker=dict(
            color=values,
            colorscale="Blues",
            cmin=min(values) * 0.4,
            cmax=max(values),
            showscale=False,
        ),
        text=[fmt_currency(v) for v in values],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br>Revenue: %{text}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text="Top 10 Product Categories by Revenue", font=dict(size=14, color="#1e293b")),
        plot_bgcolor=PLOT_BG, paper_bgcolor=PLOT_BG,
        xaxis=dict(
            showgrid=True, gridcolor=GRID_CLR,
            tickvals=tickvals, ticktext=ticktext,
        ),
        yaxis=dict(showgrid=False),
        height=CHART_H,
        margin=dict(t=48, b=40, l=165, r=85),
    )
    return fig


def chart_state_map(sales_data: pd.DataFrame, year: int):
    """US choropleth of revenue by state. Blue gradient."""
    if "customer_state" not in sales_data.columns:
        fig = go.Figure()
        fig.add_annotation(text="Geographic data not available",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    state_rev = (
        sales_data.groupby("customer_state")["price"]
        .sum()
        .reset_index()
        .rename(columns={"customer_state": "state", "price": "revenue"})
    )

    fig = go.Figure(go.Choropleth(
        locations=state_rev["state"],
        z=state_rev["revenue"],
        locationmode="USA-states",
        colorscale="Blues",
        colorbar=dict(
            title=dict(text="Revenue", font=dict(size=11)),
            tickformat="$,.0f",
            len=0.75,
        ),
        hovertemplate="%{location}<br>Revenue: $%{z:,.0f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text=f"Revenue by State — {year}", font=dict(size=14, color="#1e293b")),
        geo_scope="usa",
        geo=dict(showframe=False, showcoastlines=True, bgcolor=PLOT_BG),
        height=CHART_H,
        margin=dict(t=48, b=10, l=10, r=10),
    )
    return fig


def chart_delivery_satisfaction(sales_data: pd.DataFrame):
    """Bar chart: average review score by delivery speed category."""
    required = {"delivery_days", "review_score", "order_id"}
    if not required.issubset(sales_data.columns):
        fig = go.Figure()
        fig.add_annotation(text="Delivery or review data not available",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    order_data = (
        sales_data
        .drop_duplicates("order_id")
        .dropna(subset=["delivery_days", "review_score"])
        .assign(delivery_category=lambda df: df["delivery_days"].apply(categorize_delivery_speed))
    )

    CATEGORY_ORDER = ["1-3 days", "4-7 days", "8+ days"]
    delivery_sat = (
        order_data[order_data["delivery_category"].isin(CATEGORY_ORDER)]
        .groupby("delivery_category")["review_score"]
        .mean()
        .reindex(CATEGORY_ORDER)
        .dropna()
        .reset_index()
        .rename(columns={"review_score": "avg_score"})
    )

    if delivery_sat.empty:
        fig = go.Figure()
        fig.add_annotation(text="Insufficient data for delivery satisfaction chart",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    fig = go.Figure(go.Bar(
        x=delivery_sat["delivery_category"],
        y=delivery_sat["avg_score"],
        marker_color=BLUE_LINE,
        text=[f"{v:.2f}" for v in delivery_sat["avg_score"]],
        textposition="outside",
        width=0.45,
        hovertemplate="%{x}<br>Avg Score: %{text}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(text="Customer Satisfaction by Delivery Speed", font=dict(size=14, color="#1e293b")),
        plot_bgcolor=PLOT_BG, paper_bgcolor=PLOT_BG,
        xaxis=dict(title="Delivery Speed", showgrid=False),
        yaxis=dict(
            title="Average Review Score",
            showgrid=True, gridcolor=GRID_CLR,
            range=[0, 5], dtick=1,
        ),
        height=CHART_H, margin=CHART_MARGIN,
    )
    return fig


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    loader, processed_data = load_data()
    if loader is None:
        st.error("Failed to load data. Check that ecommerce_data/ is present.")
        return

    orders_df      = processed_data["orders"]
    available_years = sorted(
        orders_df["purchase_year"].dropna().unique().astype(int), reverse=True
    )

    # ── Header: title left, filters right ────────────────────────────────────
    left, right = st.columns([3, 2])

    with left:
        st.title("E-commerce Analytics Dashboard")

    with right:
        yr_col, mo_col = st.columns(2)

        with yr_col:
            default_idx = available_years.index(2023) if 2023 in available_years else 0
            selected_year = st.selectbox(
                "Year",
                options=available_years,
                index=default_idx,
                key="year_filter",
            )

        with mo_col:
            month_keys   = [0] + list(MONTH_NAMES.keys())
            month_labels = {0: "All Months", **MONTH_NAMES}
            selected_month_key = st.selectbox(
                "Month",
                options=month_keys,
                format_func=lambda k: month_labels[k],
                index=0,
                key="month_filter",
            )
            selected_month = None if selected_month_key == 0 else selected_month_key

    st.divider()

    # ── Load filtered datasets ────────────────────────────────────────────────
    previous_year = selected_year - 1
    has_prev = previous_year in available_years

    current_data = loader.create_sales_dataset(
        year_filter=selected_year,
        month_filter=selected_month,
        status_filter="delivered",
    )

    previous_data = (
        loader.create_sales_dataset(
            year_filter=previous_year,
            month_filter=selected_month,
            status_filter="delivered",
        )
        if has_prev else None
    )
    has_prev_data = has_prev and previous_data is not None and not previous_data.empty

    # ── KPI calculations ──────────────────────────────────────────────────────
    total_revenue = current_data["price"].sum()
    total_orders  = current_data["order_id"].nunique()
    avg_ov = (
        current_data.groupby("order_id")["price"].sum().mean()
        if total_orders > 0 else 0.0
    )

    prev_revenue = previous_data["price"].sum() if has_prev_data else None
    prev_orders  = previous_data["order_id"].nunique() if has_prev_data else None
    prev_aov     = (
        previous_data.groupby("order_id")["price"].sum().mean()
        if has_prev_data else None
    )

    # Monthly growth: average MoM % change within selected year
    mo_series = current_data.groupby("purchase_month")["price"].sum()
    if len(mo_series) > 1:
        monthly_growth = mo_series.pct_change().mean() * 100
    else:
        monthly_growth = None  # Single month — no MoM trend available

    # ── KPI row ───────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        st.markdown(f"""
        <div class="kpi-card">
          <p class="kpi-label">Total Revenue</p>
          <p class="kpi-value">{fmt_currency(total_revenue)}</p>
          <p class="kpi-trend">{trend_span(total_revenue, prev_revenue)}</p>
        </div>""", unsafe_allow_html=True)

    with k2:
        if monthly_growth is not None:
            sign  = "+" if monthly_growth >= 0 else ""
            css   = "t-pos" if monthly_growth >= 0 else "t-neg"
            arrow = "▲" if monthly_growth >= 0 else "▼"
            val   = f"{sign}{monthly_growth:.2f}%"
            sub   = f'<span class="{css}">{arrow} Avg month-over-month</span>'
        else:
            val = "N/A"
            sub = '<span class="t-neu">Select full year for trend</span>'

        st.markdown(f"""
        <div class="kpi-card">
          <p class="kpi-label">Monthly Growth</p>
          <p class="kpi-value">{val}</p>
          <p class="kpi-trend">{sub}</p>
        </div>""", unsafe_allow_html=True)

    with k3:
        st.markdown(f"""
        <div class="kpi-card">
          <p class="kpi-label">Avg Order Value</p>
          <p class="kpi-value">{fmt_currency(avg_ov)}</p>
          <p class="kpi-trend">{trend_span(avg_ov, prev_aov)}</p>
        </div>""", unsafe_allow_html=True)

    with k4:
        st.markdown(f"""
        <div class="kpi-card">
          <p class="kpi-label">Total Orders</p>
          <p class="kpi-value">{total_orders:,}</p>
          <p class="kpi-trend">{trend_span(total_orders, prev_orders)}</p>
        </div>""", unsafe_allow_html=True)

    st.write("")  # vertical spacer

    # ── Charts 2 × 2 ─────────────────────────────────────────────────────────
    r1c1, r1c2 = st.columns(2)
    r2c1, r2c2 = st.columns(2)

    with r1c1:
        st.plotly_chart(
            chart_revenue_trend(current_data, previous_data, selected_year, previous_year),
            use_container_width=True,
        )
    with r1c2:
        st.plotly_chart(
            chart_categories(current_data),
            use_container_width=True,
        )
    with r2c1:
        st.plotly_chart(
            chart_state_map(current_data, selected_year),
            use_container_width=True,
        )
    with r2c2:
        st.plotly_chart(
            chart_delivery_satisfaction(current_data),
            use_container_width=True,
        )

    st.divider()

    # ── Bottom row ────────────────────────────────────────────────────────────
    b1, b2 = st.columns(2)

    with b1:
        order_del = (
            current_data.drop_duplicates("order_id")
            .dropna(subset=["delivery_days"])
        )
        avg_del = order_del["delivery_days"].mean() if len(order_del) > 0 else None

        if has_prev_data:
            prev_del = (
                previous_data.drop_duplicates("order_id")
                .dropna(subset=["delivery_days"])
            )
            prev_del_avg = prev_del["delivery_days"].mean() if len(prev_del) > 0 else None
        else:
            prev_del_avg = None

        val_str   = f"{avg_del:.1f} days" if avg_del is not None else "N/A"
        trend_str = trend_span(avg_del, prev_del_avg, invert=True) if avg_del else '<span class="t-neu">No data</span>'

        st.markdown(f"""
        <div class="btm-card">
          <p class="btm-label">Average Delivery Time</p>
          <p class="btm-value">{val_str}</p>
          <p class="btm-sub">{trend_str}</p>
        </div>""", unsafe_allow_html=True)

    with b2:
        order_rev = (
            current_data.drop_duplicates("order_id")
            .dropna(subset=["review_score"])
        )
        avg_review = order_rev["review_score"].mean() if len(order_rev) > 0 else None

        if avg_review is not None:
            full   = int(round(avg_review))
            stars  = "★" * full + "☆" * (5 - full)
            val_r  = f"{avg_review:.2f} / 5"
        else:
            stars = "☆☆☆☆☆"
            val_r = "N/A"

        st.markdown(f"""
        <div class="btm-card">
          <p class="btm-label">Review Score</p>
          <p class="btm-value">{val_r}</p>
          <p class="btm-stars">{stars}</p>
          <p class="btm-sub">Average Review Score</p>
        </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
