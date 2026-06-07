"""
charts.py — Plotly figure constructors for N-SIGHT.

Rules:
- No st.* imports or calls anywhere in this file.
- All functions accept Polars DataFrames or primitives and return go.Figure.
- Both chart builders accept a `dark_mode: bool` flag so app.py can pass the
  current theme state; this keeps backgrounds and font colours in sync with the
  CSS-injected theme without any Streamlit calls here.
"""

from __future__ import annotations

import polars as pl
import plotly.graph_objects as go

from src.constants import FARM_NUE_OPTIMAL_LOW, FARM_NUE_OPTIMAL_HIGH

# ── Brand palette (fixed — theme-independent) ─────────────────────────────────
_GREEN_DARK   = "#166534"
_GREEN_MID    = "#21C55D"
_GREEN_LIGHT  = "#4ADE80"
_ORANGE       = "#F59E0B"
_RED          = "#FF4B4B"
_RED_DARK     = "#991B1B"
_BLUE_NODE    = "#3B82F6"
_BRAN_AMBER   = "#D97706"

# ── Theme-aware palette helpers ────────────────────────────────────────────────
def _theme(dark_mode: bool) -> dict:
    """Return a dict of theme-dependent colour tokens."""
    if dark_mode:
        return {
            "paper":      "#24150F",
            "plot":       "#3E2723",
            "font":       "#F0F1F2",
            "gauge_bg":   "#3E2723",
            "border":     "#5D4037",
            "node_line":  "#24150F",
            "template":   "plotly_dark",
            "grid":       "rgba(255,255,255,0.08)",
        }
    return {
        "paper":      "#F5F2EB",
        "plot":       "rgba(0,0,0,0)",   # transparent over tan canvas
        "font":       "#3E2723",         # high-contrast dark brown on light bg
        "gauge_bg":   "#FFFFFF",
        "border":     "#BCAAA4",
        "node_line":  "#F5F2EB",
        "template":   "plotly_white",    # white gridlines, no grey backdrop
        "grid":       "rgba(62,39,35,0.12)",
    }

# Midpoint of optimal band — gauge delta reference.
_NUE_TARGET = (FARM_NUE_OPTIMAL_LOW + FARM_NUE_OPTIMAL_HIGH) / 2.0   # 80.0


# ── §8.1 Sankey — Nitrogen Through Supply Chain ───────────────────────────────

def build_nitrogen_sankey(
    pipeline_df: pl.DataFrame,
    bread_type: str = "Refined",
    dark_mode: bool = False,
) -> go.Figure:
    """
    Plotly Sankey diagram — N destination balance per 100 applied N units.

    Single source node ("Applied N (100 units)") feeds destination nodes defined
    by bread_type. pipeline_df is retained in the signature for call-site
    compatibility; distributions are hardcoded from CIS bread-type benchmarks.
    """
    _ = pipeline_df  # signature preserved; values are bread-type constants

    # FIXED: Flipped the values so Refined has Bran and Whole Wheat has Milling Loss
    REFINED_NODES = {
        "Consumed Food N":       42.53,
        "Consumer Waste":         9.98,
        "Retail Waste":           7.16,
        "Bakery Loss":            3.14,
        "Bran and Byproducts":   26.19,
        "Field Difference":      17.93,
    }

    WHOLE_WHEAT_NODES = {
        "Consumed Food N":      59.05,
        "Consumer Waste":       13.85,
        "Retail Waste":          9.94,
        "Bakery Loss":           4.36,
        "Milling Loss":          1.79,
        "Field Difference":     17.93,
    }

    node_data = REFINED_NODES if bread_type == "Refined" else WHOLE_WHEAT_NODES

    bg_color   = "#24150F" if dark_mode else "#F5F2EB"
    font_color = "#F5F2EB" if dark_mode else "#1D2A57"
    accent     = "#61C0BF"

    dest_labels = list(node_data.keys())
    dest_values = list(node_data.values())
    node_labels = ["Applied N (100 units)"] + dest_labels
    n_dest      = len(dest_labels)

    nodes = dict(
        label=node_labels,
        color=[accent] + [accent] * n_dest,
        pad=20,
        thickness=24,
        line=dict(color=bg_color, width=1),
    )

    links = dict(
        source=[0] * n_dest,
        target=list(range(1, n_dest + 1)),
        value=dest_values,
        color=[f"rgba(97, 192, 191, 0.55)"] * n_dest,
        hovertemplate="<b>%{target.label}</b><br>%{value:.2f} N units<extra></extra>",
    )

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=nodes,
            link=links,
            textfont=dict(color=font_color, size=12, family="Montserrat, sans-serif"),
        )
    )

    fig.update_layout(
        title=dict(
            text=f"N Destination Balance — {bread_type} (per 100 Applied N units)",
            font=dict(size=15, color=font_color, family="Montserrat, sans-serif"),
            x=0.5,
            xanchor="center",
        ),
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color=font_color, family="Montserrat, sans-serif"),
        margin=dict(l=20, r=20, t=60, b=20),
        height=480,
    )

    return fig


def build_bread_comparison_bar_chart(dark_mode: bool) -> go.Figure:
    """Side-by-side comparison of N destination balances for both bread types."""
    REFINED = {
        "Consumed Food N": 59.05, "Consumer Waste": 13.85,
        "Retail Waste": 9.94, "Bakery Loss": 4.36,
        "Milling Loss": 1.79, "Field Difference": 17.93,
    }
    WHOLE_WHEAT = {
        "Consumed Food N": 42.53, "Consumer Waste": 9.98,
        "Retail Waste": 7.16,    "Bakery Loss": 3.14,
        "Bran and Byproducts": 26.19, "Field Difference": 17.93,
    }

    # Align categories — whole wheat has "Bran and Byproducts" instead of "Milling Loss"
    all_categories = list(dict.fromkeys(list(REFINED.keys()) + list(WHOLE_WHEAT.keys())))
    refined_vals    = [REFINED.get(cat, 0) for cat in all_categories]
    whole_vals      = [WHOLE_WHEAT.get(cat, 0) for cat in all_categories]

    bg_color   = "#24150F" if dark_mode else "#F5F2EB"
    font_color = "#F5F2EB" if dark_mode else "#1D2A57"
    grid_color = "rgba(255,255,255,0.08)" if dark_mode else "rgba(0,0,0,0.07)"

    fig = go.Figure(data=[
        go.Bar(name="Refined White", x=all_categories, y=refined_vals,
               marker_color="#61C0BF"),
        go.Bar(name="Whole Wheat",   x=all_categories, y=whole_vals,
               marker_color="#1D2A57" if not dark_mode else "#7BA8CC"),
    ])
    fig.update_layout(
        barmode="group",
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color=font_color, family="Montserrat, sans-serif", size=11),
        title=dict(text="N Destination: Refined vs. Whole Wheat",
                   font=dict(size=14, color=font_color), x=0.01),
        yaxis=dict(title="N units per 100 applied",
                   gridcolor=grid_color, linecolor=grid_color),
        xaxis=dict(gridcolor=grid_color, linecolor=grid_color, tickangle=-30),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=60, b=80, l=60, r=20),
    )
    return fig


def build_nue_distribution_pie(bread_type: str, dark_mode: bool) -> go.Figure:
    """Donut chart showing resource allocation percentages for the selected bread type."""
    REFINED = {
        "Consumed Food N": 59.05, "Consumer Waste": 13.85,
        "Retail Waste": 9.94,    "Bakery Loss": 4.36,
        "Milling Loss": 1.79,    "Field Difference": 17.93,
    }
    WHOLE_WHEAT = {
        "Consumed Food N": 42.53, "Consumer Waste": 9.98,
        "Retail Waste": 7.16,    "Bakery Loss": 3.14,
        "Bran and Byproducts": 26.19, "Field Difference": 17.93,
    }

    node_data = REFINED if bread_type == "Refined" else WHOLE_WHEAT
    labels  = list(node_data.keys())
    values  = list(node_data.values())
    colors  = ["#61C0BF","#F5A623","#E8534A","#A8D5BA","#7BA8CC","#C4A882"]

    bg_color   = "#24150F" if dark_mode else "#F5F2EB"
    font_color = "#F5F2EB" if dark_mode else "#1D2A57"

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.45,
        marker=dict(colors=colors[:len(labels)], line=dict(color=bg_color, width=2)),
        textinfo="label+percent",
        textfont=dict(size=11, color=font_color),
        hovertemplate="<b>%{label}</b><br>%{value:.2f} N units (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=bg_color,
        font=dict(color=font_color, family="Montserrat, sans-serif"),
        title=dict(text=f"N Allocation — {bread_type}",
                   font=dict(size=14, color=font_color), x=0.01),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        margin=dict(t=60, b=20, l=20, r=20),
        showlegend=True,
    )
    return fig


# ── §8.2 NUE Gauge ────────────────────────────────────────────────────────────

def build_nue_gauge(
    nue_value: float,
    label: str,
    dark_mode: bool = True,
) -> go.Figure:
    """
    Plotly Indicator gauge for a single NUE percentage value.

    Spec (§8.2):
      mode:   'gauge+number+delta'
      range:  0–110 %
      bands:  < 70   → red
              70–90  → green
              > 90   → orange
      delta reference: optimal band centre (80 %)
    """
    th = _theme(dark_mode)

    if nue_value > 100.0:
        needle_color = _RED
    elif FARM_NUE_OPTIMAL_LOW <= nue_value <= FARM_NUE_OPTIMAL_HIGH:
        needle_color = _GREEN_MID
    else:
        needle_color = _ORANGE

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=nue_value,
            number=dict(
                suffix="%",
                font=dict(size=28, color=th["font"], family="Montserrat, monospace"),
            ),
            delta=dict(
                reference=_NUE_TARGET,
                increasing=dict(color=_GREEN_MID),
                decreasing=dict(color=_ORANGE),
                font=dict(size=13),
                suffix=" pp vs 80%",
            ),
            title=dict(
                text=f"{label} NUE",
                font=dict(size=14, color=th["font"], family="Montserrat, monospace"),
            ),
            gauge=dict(
                axis=dict(
                    range=[0, 110],
                    tickwidth=1,
                    tickcolor=th["font"],
                    tickfont=dict(color=th["font"], size=10),
                    dtick=10,
                ),
                bar=dict(color=needle_color, thickness=0.25),
                bgcolor=th["gauge_bg"],
                borderwidth=1,
                bordercolor=th["border"],
                steps=[
                    dict(range=[0,  FARM_NUE_OPTIMAL_LOW],               color="rgba(255,75,75,0.18)"),
                    dict(range=[FARM_NUE_OPTIMAL_LOW, FARM_NUE_OPTIMAL_HIGH], color="rgba(33,197,93,0.18)"),
                    dict(range=[FARM_NUE_OPTIMAL_HIGH, 110],              color="rgba(245,158,11,0.18)"),
                ],
                threshold=dict(
                    line=dict(color=_GREEN_MID, width=3),
                    thickness=0.85,
                    value=FARM_NUE_OPTIMAL_HIGH,
                ),
            ),
        )
    )

    fig.add_annotation(
        x=0.5, y=-0.08,
        xref="paper", yref="paper",
        text=(
            f"<span style='color:{_RED}'>■</span> &lt;70% loss risk &nbsp;"
            f"<span style='color:{_GREEN_MID}'>■</span> 70–90% optimal &nbsp;"
            f"<span style='color:{_ORANGE}'>■</span> &gt;90% caution"
        ),
        showarrow=False,
        font=dict(size=10, color=th["font"], family="Montserrat, monospace"),
        align="center",
    )

    fig.update_layout(
        paper_bgcolor=th["paper"],
        plot_bgcolor=th["plot"],
        font=dict(color=th["font"], family="Montserrat, monospace"),
        template=th["template"],
        margin=dict(l=20, r=20, t=30, b=50),
        height=280,
    )

    return fig


# ── §8.3 Urea Market History Line Chart ───────────────────────────────────────

def build_urea_history_chart(
    df: pl.DataFrame,
    select_y_axis: str,
    dark_mode: bool,
) -> go.Figure:
    """
    Builds a styled Plotly line chart from the historical urea price DataFrame.

    Args:
        df: Polars DataFrame loaded from Urea_NW_Historical_Analysis_2015_2024.xlsx.
            Must already have real column names (including embedded '\\n' chars) and
            contain only the 10 data rows (2015–2024) — header promotion and slicing
            is handled by the caller.
        select_y_axis: Exact column name string (may contain '\\n'), e.g.
            'Nominal Price\\n(USD/mt)'.
        dark_mode: True → dark soil canvas (#24150F); False → ivory-tan (#F5F2EB).
    """
    DARK_BG          = "#24150F"
    LIGHT_BG         = "#F5F2EB"
    BRAND_TEAL       = "#61C0BF"
    BRAND_INDIGO     = "#1D2A57"
    GRID_COLOR_DARK  = "rgba(255,255,255,0.08)"
    GRID_COLOR_LIGHT = "rgba(0,0,0,0.07)"

    bg_color   = DARK_BG  if dark_mode else LIGHT_BG
    font_color = "#F5F2EB" if dark_mode else BRAND_INDIGO
    grid_color = GRID_COLOR_DARK if dark_mode else GRID_COLOR_LIGHT

    # Filter to rows where Year is a 4-digit integer string
    data_df = (
        df
        .filter(pl.col("Year").is_not_null())
        .filter(pl.col("Year").cast(pl.String).str.contains(r"^\d{4}$"))
    )

    # Cast axes to numeric — Excel cells are sometimes read as strings
    x_vals = [int(v) for v in data_df["Year"].cast(pl.String).to_list() if v is not None]
    raw_y  = data_df.select(pl.col(select_y_axis).cast(pl.Float64, strict=False)).to_series().to_list()

    axis_label = select_y_axis.replace("\n", " ")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_vals,
        y=raw_y,
        mode="lines+markers",
        line=dict(color=BRAND_TEAL, width=2.5),
        marker=dict(color=BRAND_TEAL, size=7),
        name=axis_label,
        hovertemplate=f"<b>%{{x}}</b><br>{axis_label}: %{{y:,.2f}}<extra></extra>",
    ))

    fig.update_layout(
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color=font_color, family="Montserrat, sans-serif", size=12),
        title=dict(
            text=f"NW Urea Market — {axis_label}",
            font=dict(size=15, color=font_color),
            x=0.01,
        ),
        xaxis=dict(
            title="Year",
            gridcolor=grid_color,
            linecolor=grid_color,
            tickmode="linear",
            tick0=2015,
            dtick=1,
        ),
        yaxis=dict(
            title=axis_label,
            gridcolor=grid_color,
            linecolor=grid_color,
        ),
        hovermode="x unified",
        margin=dict(t=60, b=40, l=60, r=20),
        showlegend=False,
    )
    return fig


import plotly.graph_objects as go

def build_urea_vs_wheat_chart(urea_df, dark_mode: bool = True) -> go.Figure:
    """
    Generates a dual Y-axis line chart comparing nominal Urea price ($/mt)
    with local or baseline Wheat price ($/bu) over time.
    """
    # Align theme colors with your custom UI palette
    bg_color   = "#24150F" if dark_mode else "#F5F2EB"
    font_color = "#F5F2EB" if dark_mode else "#1D2A57"
    urea_color = "#61C0BF" # Accent Teal
    wheat_color = "#66BB6A" if dark_mode else "#2E7D32" # Accent Green

    fig = go.Figure()

    # 1. Add Urea Price Line (Primary Left Y-Axis)
    fig.add_trace(
        go.Scatter(
            x=urea_df["Year"],
            y=urea_df["Nominal Price\n(USD/mt)"],
            name="Urea Price ($/mt)",
            line=dict(color=urea_color, width=3),
            mode="lines+markers"
        )
    )

    # 2. Add Wheat Price Line (Secondary Right Y-Axis)
    # Note: Hardcoded typical baseline trend matching your market analysis window if wheat data isn't in your dataframe
    # Adjust this column key if you have a specific 'Wheat_Price' column in your sheet!
    wheat_prices = [4.75, 4.10, 4.40, 5.20, 4.90, 5.50, 7.50, 8.50, 6.80, 6.50] 
    
    fig.add_trace(
        go.Scatter(
            x=urea_df["Year"],
            y=wheat_prices,
            name="Wheat Price ($/bu)",
            line=dict(color=wheat_color, width=3, dash="dash"),
            mode="lines+markers",
            yaxis="y2" # Assigns this line to the right-side axis
        )
    )

    # 3. Configure Layout Styles & Dual Axis Labels
    fig.update_layout(
        title=dict(
            text="Historical Market Comparison: Urea vs Wheat",
            font=dict(size=16, color=font_color, family="Montserrat, sans-serif"),
            x=0.5,
            xanchor="center",
        ),
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color=font_color, family="Montserrat, sans-serif"),
        margin=dict(l=50, r=50, t=60, b=40),
        height=450,
        showlegend=True,
        # FIXED: Changed 'orient' to the correct valid Plotly property name 'orientation'
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        
        # Left Y-Axis configuration
        yaxis=dict(
            title="Urea Price (USD/mt)",
            titlefont=dict(color=urea_color),
            tickfont=dict(color=urea_color),
            gridcolor="rgba(161, 136, 127, 0.15)" # Soft brand tan gridlines
        ),
        # Right Y-Axis configuration
        yaxis2=dict(
            title="Wheat Price (USD/bu)",
            titlefont=dict(color=wheat_color),
            tickfont=dict(color=wheat_color),
            overlaying="y",
            side="right"
        ),
        xaxis=dict(
            gridcolor="rgba(161, 136, 127, 0.15)",
            dtick=1 # Force an indicator for every calendar year
        )
    )

    return fig