# N-SIGHT — Cursor Project Specification
### Precision Agriculture & Supply Chain NUE Decision Engine
### IFA Nutrient Use Efficiency Hackathon — Phase One (Tracks 1 & 2)

---

> **FOR CURSOR:** This is the single source of truth. Every variable name, formula, validation rule, file path, and UI constraint here is authoritative. Do not deviate unless explicitly instructed. Build in the sequence defined in §8.

---

## 1. Project Identity & Mandate

**N-SIGHT** is a Streamlit application that mathematically traces every gram of Nitrogen through a bread supply chain — from soil fertilizer application through milling and retail — for a **1 kg bread reference product**. It simultaneously audits data source quality to expose industry data gaps.

**Dual-Track Scope:**
- **Track 1 (Trace the Loaf):** Quantitative nitrogen mass-balance across three supply chain segments.
- **Track 2 (The Nitrogen Audit):** Data reliability scoring and a heatmap dashboard exposing low-confidence inputs.

---

## 2. Tech Stack — Strict Constraints

| Layer | Library | Notes |
|---|---|---|
| UI / App | `streamlit` | No Flask, no FastAPI, no JS frameworks |
| Data / Math | `polars` | All DataFrames and pipeline calculations must use Polars, not Pandas |
| Charts | `plotly.express` + `plotly.graph_objects` | All visualizations |
| Geo / Weather | `geopy`, `meteostat` | Precipitation index auto-lookup |
| No others | — | Do not introduce numpy, scipy, or pandas unless a Polars gap forces it |

---

## 3. File & Folder Structure

```
nsight/
├── app.py                  # Streamlit entrypoint — layout skeleton only
├── requirements.txt
├── .streamlit/
│   └── config.toml         # Theme config
├── src/
│   ├── __init__.py
│   ├── constants.py        # All magic numbers and defaults (§4)
│   ├── models.py           # Polars schema definitions and typed dataclasses
│   ├── math_engine.py      # All segment calculations (pure functions, no Streamlit)
│   ├── weather.py          # Geopy + Meteostat precipitation index lookup
│   ├── audit.py            # Track 2 scoring and heatmap logic
│   └── charts.py           # All Plotly figure constructors
├── tests/
│   └── test_math_engine.py # Unit tests for every formula in §5
└── README.md
```

**Rule:** `app.py` must import from `src/` only. No business logic in `app.py`.

---

## 4. Constants (`src/constants.py`)

Define every value below exactly as written. These are the only authoritative defaults.

```python
# ── Segment 1: Farm ───────────────────────────────────────────────────────────
DEFAULT_YIELD_POTENTIAL_BU_ACRE   = 60.0    # bushels/acre
DEFAULT_PRECIPITATION_INDEX       = 1.0     # unitless multiplier (1.0 = normal)
DEFAULT_SOM_N_LBS_ACRE            = 30.0    # lbs N/acre from soil organic matter
DEFAULT_SOIL_TEST_N_LBS_ACRE      = 20.0    # lbs N/acre from soil test
LEGUME_N_CREDIT_LBS_ACRE          = 35.0    # added when toggle ON
HIGH_CARBON_N_DEBIT_LBS_ACRE      = 15.0    # subtracted when toggle ON
GRAIN_N_CONTENT_PCT               = 2.2     # % N in harvested grain (hard red winter wheat)
LBS_N_PER_BU_WHEAT                = 0.35    # lbs N per bushel of wheat
FARM_NUE_OPTIMAL_LOW              = 70.0    # %
FARM_NUE_OPTIMAL_HIGH             = 90.0    # %

# ── Segment 2: Mill ───────────────────────────────────────────────────────────
DEFAULT_EXTRACTION_RATE_PCT       = 75.0    # % — white flour default
WHOLEMEAL_EXTRACTION_RATE_PCT     = 100.0   # % — upper bound
# Mill nitrogen retention formulas (implemented in math_engine.py, not here):
#   flour_N = grain_N_in * (extraction_rate_pct / 100)
#   bran_N  = grain_N_in - flour_N

# ── Segment 3: Bakery & Retail ─────────────────────────────────────────────────
PRODUCT_VARIANTS = {
    "Baguette":              {"moisture_loss_pct": 25.0, "waste_factor": 1.10},
    "Whole Meal Sliced Loaf":{"moisture_loss_pct": 15.0, "waste_factor": 1.05},
}
DEFAULT_SPOILAGE_WASTE_PCT        = 5.0     # % processing/distribution loss
REFERENCE_LOAF_MASS_KG            = 1.0

# ── Protein Conversion ─────────────────────────────────────────────────────────
N_TO_PROTEIN_FACTOR               = 5.7    # g protein = g N × 5.7 (wheat standard)

# ── Track 2: Audit Scoring ─────────────────────────────────────────────────────
AUDIT_HIGH_SCORE   = 5    # IoT / farm-level ledger
AUDIT_MED_SCORE    = 3    # Regional / cooperative DB
AUDIT_LOW_SCORE    = 1    # Stale industry rules-of-thumb
AUDIT_RISK_THRESHOLD = 2  # Scores ≤ this value trigger red heatmap cell

# ── Precipitation Lookup ───────────────────────────────────────────────────────
METEOSTAT_LOOKBACK_YEARS  = 10   # rolling average period
PRECIP_INDEX_BASELINE_MM  = 450  # mm/year baseline for index = 1.0
```

---

## 5. Math Engine (`src/math_engine.py`)

All functions must accept and return Polars DataFrames or Python primitives. No global state. No `st.*` calls.

### 5.1 Segment 1 — Farm

```python
def calc_n_application(
    yield_potential_bu_acre: float,
    precip_index: float,
    som_n: float,
    soil_test_n: float,
    legume_credit: bool,
    high_carbon_debit: bool,
) -> float:
    """
    N_application = (yield_potential × precip_index) - (som_n + soil_test_n)
                    + (LEGUME_N_CREDIT if legume_credit else 0)
                    - (HIGH_CARBON_N_DEBIT if high_carbon_debit else 0)
    Units: lbs N / acre
    """

def calc_grain_n_uptake(yield_potential_bu_acre: float) -> float:
    """grain_n_uptake = yield_potential × LBS_N_PER_BU_WHEAT"""

def calc_farm_nue(grain_n_uptake: float, n_application: float) -> float:
    """
    farm_nue = (grain_n_uptake / n_application) × 100
    Returns: float (percentage)
    Raises: ZeroDivisionError if n_application == 0
    """

def validate_farm_nue(nue: float) -> dict:
    """
    Returns: {
        "status": "critical" | "optimal" | "warning",
        "message": str,
        "color": "#hex"
    }
    Rules:
      nue > 100  → status="critical",
                   message="CRITICAL WARNING: Soil Mining Detected! Crop is
                   extracting more nutrients than are being replenished,
                   putting long-term soil health at risk.",
                   color="#FF4B4B"
      70 ≤ nue ≤ 90 → status="optimal",
                      message="Optimal Efficiency Target Band Achieved.",
                      color="#21C55D"
      nue < 70   → status="warning",
                   message="Environmental Loss Risk: High probability of
                   nitrogen leaching or gaseous volatilization.",
                   color="#F59E0B"
    """
```

### 5.2 Segment 2 — Mill

```python
def calc_mill_output(
    grain_n_lbs_acre: float,
    extraction_rate_pct: float,
) -> dict:
    """
    flour_n = grain_n × (extraction_rate / 100)
    bran_n  = grain_n - flour_n
    Returns: {"flour_n": float, "bran_n": float, "mill_nue": float}
    mill_nue = (flour_n / grain_n) × 100  — same as extraction_rate numerically
    """
```

### 5.3 Segment 3 — Bakery & Retail

```python
def calc_bakery_output(
    flour_n_g: float,
    product_variant: str,          # key into PRODUCT_VARIANTS
    spoilage_waste_pct: float,
) -> dict:
    """
    Step 1: Apply moisture loss from PRODUCT_VARIANTS[product_variant]["moisture_loss_pct"]
    Step 2: Apply waste_factor from PRODUCT_VARIANTS[product_variant]["waste_factor"]
    Step 3: Apply spoilage_waste_pct
    Step 4: Normalize to 1 kg reference loaf

    final_n_g     = flour_n_g × (1 - moisture_loss/100) × (1 - spoilage/100) / waste_factor
    protein_g     = final_n_g × N_TO_PROTEIN_FACTOR
    bakery_nue    = (final_n_g / flour_n_g) × 100

    Returns: {
        "final_n_g": float,
        "protein_g": float,
        "bakery_nue": float,
        "protein_pct_dw": float   # protein_g / 1000 × 100
    }
    """
```

### 5.4 System NUE (End-to-End)

```python
def calc_system_nue(
    n_applied_lbs_acre: float,
    final_n_g_per_kg_loaf: float,
    yield_bu_acre: float,
    loaves_per_acre: float,        # derived: yield → flour → loaves
) -> float:
    """
    system_nue = (final_n_g × loaves_per_acre) / (n_applied_lbs_acre × 453.592) × 100
    Units: lbs → grams conversion factor = 453.592
    """
```

### 5.5 Polars Pipeline

Build a single `polars.DataFrame` called `PIPELINE_DF` that logs every segment:

```python
import polars as pl

PIPELINE_SCHEMA = {
    "segment":        pl.Utf8,
    "n_in_g":         pl.Float64,
    "n_out_g":        pl.Float64,
    "n_loss_g":       pl.Float64,
    "nue_pct":        pl.Float64,
    "data_score":     pl.Int32,
    "data_label":     pl.Utf8,
}
```

---

## 6. Weather Module (`src/weather.py`)

```python
def get_precipitation_index(location_str: str) -> dict:
    """
    1. Use geopy.geocoders.Nominatim to resolve location_str → (lat, lon).
    2. Use meteostat.Point(lat, lon) + meteostat.Monthly data for
       METEOSTAT_LOOKBACK_YEARS years to compute mean annual precipitation (mm).
    3. precip_index = mean_annual_precip_mm / PRECIP_INDEX_BASELINE_MM
    4. Return:
       {
         "precip_index": float,
         "mean_annual_mm": float,
         "station_name": str,
         "lat": float,
         "lon": float,
         "years_used": int,
         "error": None | str   # surface any API/geo failures gracefully
       }
    5. On any failure, return precip_index=1.0 and error=<message>.
       Never raise; always return a dict.
    """
```

---

## 7. Audit Module (`src/audit.py`)

```python
AUDIT_SEGMENTS = ["Farm", "Mill", "Bakery & Retail"]
AUDIT_DIMENSIONS = ["Input Data", "Process Data", "Output Verification"]

def build_audit_matrix(scores: dict[str, dict[str, int]]) -> pl.DataFrame:
    """
    scores format: {"Farm": {"Input Data": 5, "Process Data": 3, ...}, ...}
    Returns a Polars DataFrame (3 segments × 3 dimensions) with:
      - segment, dimension, score, risk_flag (bool: score <= AUDIT_RISK_THRESHOLD)
    """

def score_to_label(score: int) -> str:
    """5→'High (Direct Measurement)', 3→'Medium (Aggregated DB)', 1→'Low (Rules of Thumb)'"""

def get_heatmap_figure(audit_df: pl.DataFrame) -> go.Figure:
    """
    Returns a Plotly heatmap:
    - x-axis: AUDIT_DIMENSIONS
    - y-axis: AUDIT_SEGMENTS
    - color scale: Red (#FF4B4B) at 1, Yellow (#F59E0B) at 3, Green (#21C55D) at 5
    - annotate each cell with score and label
    - title: "Data Quality Risk Matrix — N-SIGHT Audit (Track 2)"
    """
```

---

## 8. Charts Module (`src/charts.py`)

### 8.1 Sankey / Flow Chart — Nitrogen Through Supply Chain

```python
def build_nitrogen_sankey(pipeline_df: pl.DataFrame) -> go.Figure:
    """
    Plotly Sankey diagram showing N flow:
    [Total Applied N] → [Grain Uptake] → [Flour N] → [Final Loaf N]
                     ↘ [Farm Losses]  ↘ [Bran N]  ↘ [Bake/Waste Loss]
    Node colors: greens for retained N, reds/oranges for losses.
    """
```

### 8.2 NUE Gauge Charts

```python
def build_nue_gauge(nue_value: float, label: str) -> go.Figure:
    """
    Plotly Indicator gauge (mode='gauge+number+delta'):
    - Range 0–110%
    - Threshold line at 70 and 90
    - Color bands: <70 red, 70–90 green, >90 orange/red
    - title: f"{label} NUE"
    """
```

### 8.3 Protein Output Card (not a chart — Streamlit metric)

Render via `st.metric()` in `app.py`. Do not build a Plotly figure for this.

---

## 9. Streamlit UI Layout (`app.py`)

### 9.1 Page Config

```python
st.set_page_config(
    page_title="N-SIGHT | NUE Decision Engine",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)
```

### 9.2 Session State Keys

Initialize all keys at top of `app.py`:

```python
DEFAULTS = {
    "yield_potential":    DEFAULT_YIELD_POTENTIAL_BU_ACRE,
    "precip_index":       DEFAULT_PRECIPITATION_INDEX,
    "som_n":              DEFAULT_SOM_N_LBS_ACRE,
    "soil_test_n":        DEFAULT_SOIL_TEST_N_LBS_ACRE,
    "legume_credit":      False,
    "high_carbon_debit":  False,
    "extraction_rate":    DEFAULT_EXTRACTION_RATE_PCT,
    "product_variant":    "Baguette",
    "spoilage_waste_pct": DEFAULT_SPOILAGE_WASTE_PCT,
    "location_str":       "Rexburg, ID",
    "precip_lookup_done": False,
    # Pre-initialize all audit scores to Medium (3) so radio buttons always have a valid state.
    # Do NOT leave this as {}; Cursor will fail to render the sidebar audit widgets without it.
    "audit_scores": {
        seg: {dim: 3 for dim in ["Input Data", "Process Data", "Output Verification"]}
        for seg in ["Farm", "Mill", "Bakery & Retail"]
    },
}
```

### 9.3 Sidebar — All Inputs

Structure the sidebar in three expanders, one per segment:

```
📍 Location & Precipitation
  └─ st.text_input("Location", key="location_str")
  └─ st.button("Lookup Precipitation Index")
       # On click, call weather.get_precipitation_index(st.session_state["location_str"])
       # Then ALWAYS assign directly to session state — do not rely on the slider to update itself:
       #   result = weather.get_precipitation_index(st.session_state["location_str"])
       #   st.session_state["precip_index"] = result["precip_index"]  # safely 1.0 on failure
       #   st.session_state["precip_lookup_done"] = True
       # Direct assignment is required; without it a failed lookup leaves the slider stale.
  └─ st.info() showing result["station_name"], result["mean_annual_mm"], result["years_used"]
  └─ On error: st.warning(result["error"]) — slider remains usable at fallback value 1.0

🌾 Segment 1: Farm Inputs
  └─ st.slider("Yield Potential (bu/acre)", 20, 150, key="yield_potential")
  └─ st.slider("Precipitation Index", 0.5, 2.0, step=0.05, key="precip_index")
  └─ st.number_input("Mineralizable SOM N (lbs/acre)", key="som_n")
  └─ st.number_input("Soil Test N (lbs/acre)", key="soil_test_n")
  └─ st.toggle("Legume Credit (+35 lbs N/acre)", key="legume_credit")
  └─ st.toggle("High-Carbon Residue Debit (-15 lbs N/acre)", key="high_carbon_debit")
  └─ ── AUDIT ──
     st.radio("Input Data Source", ["High (5)", "Medium (3)", "Low (1)"])
     st.radio("Process Data Source", [...])
     st.radio("Output Verification", [...])

🏭 Segment 2: Mill Inputs
  └─ st.slider("Extraction Rate %", 60, 100, key="extraction_rate")
  └─ st.caption("75% = white flour | 100% = whole meal")
  └─ ── AUDIT ──  (same three radio buttons)

🥖 Segment 3: Bakery & Retail
  └─ st.selectbox("Product Variant", list(PRODUCT_VARIANTS.keys()), key="product_variant")
  └─ st.slider("Spoilage/Waste %", 0, 25, key="spoilage_waste_pct")
  └─ ── AUDIT ──  (same three radio buttons)
```

### 9.4 Main Area — Dashboard Tabs

```python
tab1, tab2, tab3 = st.tabs(["🌾 Nitrogen Flow", "📊 NUE Dashboard", "🔬 Data Audit"])
```

**Tab 1 — Nitrogen Flow:**
- Full-width Sankey diagram (`build_nitrogen_sankey`)
- Below: `st.dataframe(pipeline_df)` with Polars-rendered segment table

**Tab 2 — NUE Dashboard:**
- Three columns: `[col1, col2, col3] = st.columns(3)`
  - `col1`: Farm NUE gauge + validation banner (`st.error` / `st.success` / `st.warning`)
  - `col2`: Mill NUE gauge
  - `col3`: Bakery NUE gauge
- Below gauges: full-width System NUE gauge
- Below System NUE:
  ```
  [col_a, col_b] = st.columns(2)
  col_a: st.metric("Final N in 1 kg Loaf", f"{final_n_g:.2f} g")
  col_b: st.metric("Consumer Protein Content", f"{protein_g:.1f} g  ({protein_pct:.1f}%)")
  ```

**Tab 3 — Data Audit:**
- Full-width heatmap (`get_heatmap_figure`)
- Below: narrative warning block if any cell ≤ `AUDIT_RISK_THRESHOLD`:
  ```python
  st.error(
      "⚠️ DATA INTEGRITY ALERT: One or more supply chain segments are scored "
      "≤2 (Low Reliability). Policy or corporate ESG decisions built on these "
      "inputs carry high epistemic risk. See red cells above."
  )
  ```

---

## 10. Validation Rules (All Segments)

| Rule | Condition | UI Rendering |
|---|---|---|
| Soil Mining | Farm NUE > 100% | `st.error(message)` — block tab 2 render with this prominently |
| Optimal Range | 70% ≤ Farm NUE ≤ 90% | `st.success(message)` |
| Leaching Risk | Farm NUE < 70% | `st.warning(message)` |
| Zero Division | N application = 0 | `st.error("N application cannot be zero. Check inputs.")` |
| Data Gap | Any audit score ≤ 2 | Red heatmap cell + `st.error` in Tab 3 |
| Extraction Range | Must be 60–100% | Slider enforces bounds; no extra validation needed |
| Precip Lookup Fail | Geopy/Meteostat error | `st.warning(error_message)` + fallback index = 1.0 |

---

## 11. `requirements.txt`

```
streamlit>=1.35.0
polars>=0.20.0
plotly>=5.20.0
geopy>=2.4.0
meteostat>=1.6.8
```

---

## 12. `.streamlit/config.toml`

```toml
[theme]
base = "dark"
primaryColor = "#21C55D"
backgroundColor = "#0F1117"
secondaryBackgroundColor = "#1A1D27"
textColor = "#E8EAF0"
font = "monospace"
```

---

## 13. Build Sequence for Cursor

**Follow this order exactly. Complete and test each step before moving on.**

1. `src/constants.py` — paste all constants from §4.
2. `src/models.py` — define `PIPELINE_SCHEMA` and any `@dataclass` types.
3. `src/math_engine.py` — implement all functions from §5, fully unit-testable.
4. `tests/test_math_engine.py` — write tests covering normal, boundary (NUE=100), and zero-division cases.
5. `src/weather.py` — implement `get_precipitation_index` with graceful fallback.
6. `src/audit.py` — implement `build_audit_matrix`, `score_to_label`, `get_heatmap_figure`.
7. `src/charts.py` — implement `build_nitrogen_sankey`, `build_nue_gauge`.
8. `app.py` — wire all src modules into Streamlit UI per §9 layout.
9. `.streamlit/config.toml` — apply theme.
10. Final pass: ensure all `st.*` calls are ONLY in `app.py`. Verify with `grep -r "import streamlit" src/`.

---

## 14. Naming Conventions

- Python files: `snake_case`
- Polars column names: `snake_case` matching `PIPELINE_SCHEMA` exactly
- Streamlit `key=` values: match `DEFAULTS` dict keys exactly
- Constants: `UPPER_SNAKE_CASE`
- Functions: `verb_noun` pattern (e.g., `calc_farm_nue`, `build_audit_matrix`)

---

## 15. Output Reference Example

For a baseline run (all defaults, no toggles, Rexburg ID, Baguette):

| Segment | N In (g) | N Out (g) | Loss (g) | NUE % |
|---|---|---|---|---|
| Farm | ~210.0 | ~145.0 | ~65.0 | ~69% |
| Mill | ~145.0 | ~108.8 | ~36.2 | 75% |
| Bakery | ~108.8 | ~72.1 | ~36.7 | ~66% |
| **System** | **~210.0** | **~72.1** | **~137.9** | **~34%** |

*(These are approximate. The math engine's output is canonical.)*

---

*End of N-SIGHT Cursor Specification — v1.0*