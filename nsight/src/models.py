from dataclasses import dataclass
import polars as pl

# ── Polars Pipeline Schema ─────────────────────────────────────────────────────
# Every segment calculation writes one row to a DataFrame conforming to this schema.
# Column names are authoritative — do not rename.
PIPELINE_SCHEMA: dict[str, type] = {
    "segment":    pl.Utf8,
    "n_in_g":     pl.Float64,
    "n_out_g":    pl.Float64,
    "n_loss_g":   pl.Float64,
    "nue_pct":    pl.Float64,
    "data_score": pl.Int32,
    "data_label": pl.Utf8,
}


def empty_pipeline_df() -> pl.DataFrame:
    """Return an empty DataFrame with the canonical PIPELINE_SCHEMA columns and dtypes."""
    return pl.DataFrame(
        {col: pl.Series(col, [], dtype=dtype) for col, dtype in PIPELINE_SCHEMA.items()}
    )


# ── Segment result dataclasses ─────────────────────────────────────────────────

@dataclass
class FarmResult:
    n_application_lbs_acre: float
    grain_n_uptake_lbs_acre: float
    farm_nue_pct: float
    validation: dict          # keys: status, message, color


@dataclass
class MillResult:
    flour_n: float            # lbs N (same units as grain input)
    bran_n: float
    mill_nue: float           # % — numerically equals extraction_rate_pct


@dataclass
class BakeryResult:
    final_n_g: float          # g N per 1 kg reference loaf
    protein_g: float
    bakery_nue: float         # %
    protein_pct_dw: float     # protein_g / 1000 × 100


@dataclass
class PipelineRow:
    """Typed representation of a single row in PIPELINE_SCHEMA."""
    segment: str
    n_in_g: float
    n_out_g: float
    n_loss_g: float
    nue_pct: float
    data_score: int
    data_label: str

    def to_dict(self) -> dict:
        return {
            "segment":    self.segment,
            "n_in_g":     self.n_in_g,
            "n_out_g":    self.n_out_g,
            "n_loss_g":   self.n_loss_g,
            "nue_pct":    self.nue_pct,
            "data_score": self.data_score,
            "data_label": self.data_label,
        }
