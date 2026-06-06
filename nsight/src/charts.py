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
    dark_mode: bool = True,
) -> go.Figure:
    """
    Plotly Sankey diagram showing nitrogen flow from field to consumer.

    Node layout:
      0  Total Applied N        (source — blue)
      1  Grain Uptake           (retained — green)
      2  Farm Losses            (loss — red)
      3  Flour N                (retained — green)
      4  Bran N                 (by-product — amber)
      5  Final Loaf N           (retained — bright green)
      6  Bake / Waste Loss      (loss — red)

    Negative n_loss values (soil-mining edge case) are clamped to 0.
    """
    th = _theme(dark_mode)

    def _get(segment: str, col: str) -> float:
        rows = pipeline_df.filter(pl.col("segment") == segment)
        if rows.is_empty():
            return 0.0
        return max(float(rows[col][0]), 0.0)

    farm_n_in    = _get("Farm",            "n_in_g")
    farm_n_out   = _get("Farm",            "n_out_g")
    farm_loss    = _get("Farm",            "n_loss_g")
    mill_n_out   = _get("Mill",            "n_out_g")
    mill_loss    = _get("Mill",            "n_loss_g")
    bakery_n_out = _get("Bakery & Retail", "n_out_g")
    bakery_loss  = _get("Bakery & Retail", "n_loss_g")

    if farm_n_in == 0.0:
        fig = go.Figure()
        fig.update_layout(
            title=dict(text="No pipeline data to display.", font=dict(color=th["font"])),
            paper_bgcolor=th["paper"], plot_bgcolor=th["plot"],
        )
        return fig

    nodes = dict(
        label=[
            "Total Applied N", "Grain Uptake", "Farm Losses",
            "Flour N", "Bran N", "Final Loaf N", "Bake / Waste Loss",
        ],
        color=[
            _BLUE_NODE, _GREEN_MID, _RED,
            _GREEN_LIGHT, _BRAN_AMBER, _GREEN_MID, _RED_DARK,
        ],
        pad=20,
        thickness=24,
        line=dict(color=th["node_line"], width=1),
    )

    links = dict(
        source=[0, 0, 1, 1, 3, 3],
        target=[1, 2, 3, 4, 5, 6],
        value=[farm_n_out, farm_loss, mill_n_out, mill_loss, bakery_n_out, bakery_loss],
        color=[
            "rgba(33, 197, 93, 0.45)",
            "rgba(255, 75, 75, 0.45)",
            "rgba(74, 222, 128, 0.45)",
            "rgba(217, 119, 6, 0.45)",
            "rgba(33, 197, 93, 0.55)",
            "rgba(153, 27, 27, 0.50)",
        ],
        customdata=[
            [f"{farm_n_out:.2f} g",    "Grain Uptake"],
            [f"{farm_loss:.2f} g",     "Farm Losses (leaching / volatilisation)"],
            [f"{mill_n_out:.2f} g",    "Flour N"],
            [f"{mill_loss:.2f} g",     "Bran N (by-product)"],
            [f"{bakery_n_out:.2f} g",  "Final Loaf N"],
            [f"{bakery_loss:.2f} g",   "Bake / Waste Loss"],
        ],
        hovertemplate="%{customdata[0]} — %{customdata[1]}<extra></extra>",
    )

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=nodes,
            link=links,
            textfont=dict(color=th["font"], size=12, family="Montserrat, monospace"),
        )
    )

    fig.update_layout(
        title=dict(
            text="Nitrogen Flow Through the Bread Supply Chain (g N per 1 kg Reference Loaf)",
            font=dict(size=15, color=th["font"], family="Montserrat, monospace"),
            x=0.5,
            xanchor="center",
        ),
        paper_bgcolor=th["paper"],
        plot_bgcolor=th["plot"],
        font=dict(color=th["font"], family="Montserrat, monospace"),
        template=th["template"],
        margin=dict(l=20, r=20, t=60, b=20),
        height=480,
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
