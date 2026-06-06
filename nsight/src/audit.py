"""
audit.py — Track 2 data quality scoring and heatmap for N-SIGHT.

Rules:
- No st.* imports or calls anywhere in this file.
- All DataFrame operations use Polars.
- Plotly graph_objects is used for the heatmap figure.
"""

from __future__ import annotations

import polars as pl
import plotly.graph_objects as go

from src.constants import (
    AUDIT_HIGH_SCORE,
    AUDIT_MED_SCORE,
    AUDIT_LOW_SCORE,
    AUDIT_RISK_THRESHOLD,
)

# Authoritative axis labels (§7).
AUDIT_SEGMENTS   = ["Farm", "Mill", "Bakery & Retail"]
AUDIT_DIMENSIONS = ["Input Data", "Process Data", "Output Verification"]

# Brand palette (matches §5.1 / §12 theme).
_COLOR_HIGH   = "#21C55D"   # score = 5 — verified / direct measurement
_COLOR_MEDIUM = "#F59E0B"   # score = 3 — aggregated DB
_COLOR_LOW    = "#FF4B4B"   # score = 1 — rules of thumb / high risk

# Plotly colorscale: (normalised position 0–1, hex color)
# Scores range 1–5, so normalise: 1→0.0, 3→0.5, 5→1.0
_COLORSCALE = [
    [0.0, _COLOR_LOW],
    [0.5, _COLOR_MEDIUM],
    [1.0, _COLOR_HIGH],
]


# ── §7 Functions ──────────────────────────────────────────────────────────────

def score_to_label(score: int) -> str:
    """
    Map an audit score integer to its descriptive label.

    5 → "High (Direct Measurement)"
    3 → "Medium (Aggregated DB)"
    1 → "Low (Rules of Thumb)"
    Any other value → "Unknown"
    """
    mapping = {
        AUDIT_HIGH_SCORE: "High (Direct Measurement)",
        AUDIT_MED_SCORE:  "Medium (Aggregated DB)",
        AUDIT_LOW_SCORE:  "Low (Rules of Thumb)",
    }
    return mapping.get(score, "Unknown")


def build_audit_matrix(scores: dict[str, dict[str, int]]) -> pl.DataFrame:
    """
    Convert the nested audit scores dict from session state into a tidy Polars DataFrame.

    Input format:
      {
        "Farm":            {"Input Data": 5, "Process Data": 3, "Output Verification": 1},
        "Mill":            {...},
        "Bakery & Retail": {...},
      }

    Returns a DataFrame with columns:
      segment    (Utf8)
      dimension  (Utf8)
      score      (Int32)
      risk_flag  (Boolean) — True when score <= AUDIT_RISK_THRESHOLD
    """
    rows: list[dict] = []
    for segment in AUDIT_SEGMENTS:
        segment_scores = scores.get(segment, {})
        for dimension in AUDIT_DIMENSIONS:
            score = int(segment_scores.get(dimension, AUDIT_MED_SCORE))
            rows.append(
                {
                    "segment":   segment,
                    "dimension": dimension,
                    "score":     score,
                    "risk_flag": score <= AUDIT_RISK_THRESHOLD,
                }
            )

    return pl.DataFrame(
        rows,
        schema={
            "segment":   pl.Utf8,
            "dimension": pl.Utf8,
            "score":     pl.Int32,
            "risk_flag": pl.Boolean,
        },
    )


def get_heatmap_figure(
    audit_df: pl.DataFrame,
    dark_mode: bool = True,
) -> go.Figure:
    """
    Build a Plotly heatmap visualising data quality risk across segments and dimensions.

    Layout:
      x-axis: AUDIT_DIMENSIONS  (Input Data | Process Data | Output Verification)
      y-axis: AUDIT_SEGMENTS    (Farm | Mill | Bakery & Retail)
      color:  Red(1) → Yellow(3) → Green(5) using brand palette
      cells:  annotated with score integer + label text

    `dark_mode` drives paper/plot backgrounds and axis font colours so the
    chart stays readable in both dark (earth brown) and light (tan paper) themes.

    Title: "Data Quality Risk Matrix — N-SIGHT Audit (Track 2)"
    """
    if dark_mode:
        paper_bg   = "#24150F"
        plot_bg    = "#3E2723"
        font_color = "#F0F1F2"
    else:
        paper_bg   = "#F5F2EB"
        plot_bg    = "#FFFFFF"
        font_color = "#3E2723"
    # Pivot to a 2-D grid: rows = segments, cols = dimensions.
    # Shape: (len(AUDIT_SEGMENTS), len(AUDIT_DIMENSIONS))
    z: list[list[int]]   = []
    text: list[list[str]] = []

    for segment in AUDIT_SEGMENTS:
        row_z:    list[int] = []
        row_text: list[str] = []
        seg_rows = audit_df.filter(pl.col("segment") == segment)
        for dimension in AUDIT_DIMENSIONS:
            cell = seg_rows.filter(pl.col("dimension") == dimension)
            score = int(cell["score"][0]) if cell.height > 0 else AUDIT_MED_SCORE
            label = score_to_label(score)
            row_z.append(score)
            row_text.append(f"<b>{score}</b><br><span style='font-size:10px'>{label}</span>")
        z.append(row_z)
        text.append(row_text)

    heatmap = go.Heatmap(
        z=z,
        x=AUDIT_DIMENSIONS,
        y=AUDIT_SEGMENTS,
        text=text,
        texttemplate="%{text}",
        colorscale=_COLORSCALE,
        zmin=1,
        zmax=5,
        showscale=True,
        colorbar=dict(
            title=dict(text="Data Quality Score", side="right"),
            tickvals=[1, 3, 5],
            ticktext=["1 – Low", "3 – Medium", "5 – High"],
            thickness=16,
            outlinewidth=0,
        ),
        hovertemplate=(
            "<b>%{y}</b> › %{x}<br>"
            "Score: %{z}<br>"
            "<extra></extra>"
        ),
    )

    fig = go.Figure(data=heatmap)

    fig.update_layout(
        title=dict(
            text="Data Quality Risk Matrix — N-SIGHT Audit (Track 2)",
            font=dict(size=16, color=font_color, family="Montserrat, monospace"),
            x=0.5,
            xanchor="center",
        ),
        xaxis=dict(
            title=dict(text="Supply Chain Dimension",
                       font=dict(color=font_color, family="Montserrat, monospace")),
            side="bottom",
            tickfont=dict(color=font_color, size=12, family="Montserrat, monospace"),
        ),
        yaxis=dict(
            title=dict(text="Supply Chain Segment",
                       font=dict(color=font_color, family="Montserrat, monospace")),
            tickfont=dict(color=font_color, size=12, family="Montserrat, monospace"),
            autorange="reversed",
        ),
        paper_bgcolor=paper_bg,
        plot_bgcolor=plot_bg,
        font=dict(color=font_color, family="Montserrat, monospace"),
        margin=dict(l=140, r=80, t=70, b=60),
        height=380,
    )

    return fig
