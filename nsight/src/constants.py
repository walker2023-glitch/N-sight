# ── Segment 1: Farm ───────────────────────────────────────────────────────────
# Pacific Northwest / Idaho Hard Red Winter Wheat regional calibration
DEFAULT_YIELD_POTENTIAL_BU_ACRE   = 72.0    # Target regional yield potential (bu/ac)
DEFAULT_PRECIPITATION_INDEX       = 1.0     # unitless multiplier (1.0 = normal)
DEFAULT_SOM_N_LBS_ACRE            = 30.0    # lbs N/acre from soil organic matter
DEFAULT_SOIL_TEST_N_LBS_ACRE      = 20.0    # lbs N/acre from soil test
LEGUME_N_CREDIT_LBS_ACRE          = 35.0    # added when toggle ON
HIGH_CARBON_N_DEBIT_LBS_ACRE      = 15.0    # subtracted when toggle ON
GRAIN_N_CONTENT_PCT               = 2.2     # % N in harvested grain (hard red winter wheat)
LBS_N_PER_BU_WHEAT                = 2.625   # Derived requirement multiplier (189 lbs N / 72 bu)
DEFAULT_FARM_FERTILIZER_APPLIED   = 104.0   # Baseline regional fertilizer rate (lbs N/ac)
FARM_NUE_OPTIMAL_LOW              = 70.0    # %
FARM_NUE_OPTIMAL_HIGH             = 90.0    # %

# ── Segment 2: Mill ───────────────────────────────────────────────────────────
DEFAULT_EXTRACTION_RATE_PCT       = 76.54   # Updated white flour milling extraction rate (%)
BRAN_BYPRODUCT_RATE_PCT           = 23.46   # Milling fraction remainder (100 - 76.54)
WHOLEMEAL_EXTRACTION_RATE_PCT     = 100.0   # % — upper bound
# Mill nitrogen retention formulas (implemented in math_engine.py, not here):
#   flour_N = grain_N_in * (extraction_rate_pct / 100)
#   bran_N  = grain_N_in - flour_N

# ── Segment 3: Bakery & Retail ─────────────────────────────────────────────────
PRODUCT_VARIANTS = {
    "Baguette":               {"moisture_loss_pct": 25.0, "waste_factor": 1.10},
    "Whole Meal Sliced Loaf": {"moisture_loss_pct": 15.0, "waste_factor": 1.05},
}
DEFAULT_SPOILAGE_WASTE_PCT        = 5.0     # % processing/distribution loss
REFERENCE_LOAF_MASS_KG            = 1.0

# ── Protein Conversion ─────────────────────────────────────────────────────────
N_TO_PROTEIN_FACTOR               = 5.7     # g protein = g N × 5.7 (wheat Kjeldahl — kept for reference)
BREAD_PROTEIN_PER_100G            = 12.3    # g protein per 100 g bread (PNW hard red winter wheat)
N_GRAMS_PER_G_PROTEIN             = 0.175   # g pure N per g protein  (1 / 5.7143 ≈ 0.175)
# Reference loaf benchmark (1 kg loaf):
#   protein_g  = BREAD_PROTEIN_PER_100G × 10     = 123.0 g
#   final_n_g  = 123.0 × N_GRAMS_PER_G_PROTEIN   = 21.525 g

# ── Economic Optimization ──────────────────────────────────────────────────────
DEFAULT_WHEAT_PRICE_PER_BU        = 7.50    # Default wheat market price ($/bu)
DEFAULT_FERTILIZER_PRICE_PER_TON  = 600.0   # Default urea fertilizer market cost ($/ton)
# Economic engine uses 46% N content for standard urea:
#   cost_per_lb_N = (cost_per_ton / 2000) / 0.46

# ── Track 2: Audit Scoring ─────────────────────────────────────────────────────
AUDIT_HIGH_SCORE     = 5    # IoT / farm-level ledger
AUDIT_MED_SCORE      = 3    # Regional / cooperative DB
AUDIT_LOW_SCORE      = 1    # Stale industry rules-of-thumb
AUDIT_RISK_THRESHOLD = 2    # Scores ≤ this value trigger red heatmap cell

# ── Precipitation Lookup ───────────────────────────────────────────────────────
METEOSTAT_LOOKBACK_YEARS  = 10    # rolling average period
PRECIP_INDEX_BASELINE_MM  = 450   # mm/year baseline for index = 1.0

# ═══════════════════════════════════════════════════════════════════════════════
# University of Idaho Extension — CIS 453 Winter Wheat Nitrogen Guide
# Source: UI Extension, College of Agricultural & Life Sciences, CIS 453
# ═══════════════════════════════════════════════════════════════════════════════

# ── Table 1: Annual Precipitation Zone → N Demand Factor (lbs N / bu yield) ──
# Tuple: (lower_inches_inclusive, upper_inches_exclusive, lbs_N_per_bu)
UI_PRECIP_ZONES: list[tuple[float, float, float]] = [
    (0.0,  18.0, 2.4),   # dry zone
    (18.0, 21.0, 2.5),   # low-intermediate
    (21.0, 24.0, 2.7),   # intermediate
    (24.0, 28.0, 2.9),   # high-intermediate
    (28.0, float("inf"), 3.1),  # high-rainfall zone
]

# Default annual precipitation for PNW dryland zones (Rexburg/SE Idaho ≈ 13 in)
DEFAULT_ANNUAL_PRECIP_IN: float = 13.0

# ── Table 2: Soil Organic Matter (SOM) N Mineralization Credits (lbs N/acre) ─
# Source: University of Idaho Extension CIS 453, Table 2 (exact published values)
# Format: (som_low_inclusive, som_high_exclusive, conventional_lbs, reduced_lbs)
# Ranges are 0.2% SOM increments; the last row covers 3.0%+ (open upper bound).
UI_SOM_N_CREDIT_TABLE: list[tuple[float, float, float, float]] = [
    (0.0,  1.0,         20.0, 17.0),   # SOM < 1.0%
    (1.0,  1.2,         22.0, 19.0),   # 1.0–1.1%
    (1.2,  1.4,         26.0, 22.0),   # 1.2–1.3%
    (1.4,  1.6,         30.0, 26.0),   # 1.4–1.5%
    (1.6,  1.8,         34.0, 29.0),   # 1.6–1.7%
    (1.8,  2.0,         38.0, 32.0),   # 1.8–1.9%
    (2.0,  2.2,         42.0, 36.0),   # 2.0–2.1%
    (2.2,  2.4,         46.0, 39.0),   # 2.2–2.3%
    (2.4,  2.6,         50.0, 43.0),   # 2.4–2.5% ← PNW baseline (conv=50, red=43)
    (2.6,  2.8,         54.0, 46.0),   # 2.6–2.7%
    (2.8,  3.0,         58.0, 48.0),   # 2.8–2.9%
    (3.0,  float("inf"), 60.0, 51.0),  # 3.0%+
]

# Legacy dicts retained for any external callers — derived from the step table above.
UI_SOM_N_CREDIT_CONV:    dict[float, float] = {lo: cv for lo, _, cv, _ in UI_SOM_N_CREDIT_TABLE if lo > 0}
UI_SOM_N_CREDIT_REDUCED: dict[float, float] = {lo: rv for lo, _, _, rv in UI_SOM_N_CREDIT_TABLE if lo > 0}

# ── Soil Test Nitrate Conversion ───────────────────────────────────────────────
# ppm NO₃-N in soil profile × 3.5 = lbs N/acre
# Source: UI CIS 453 (accounts for standard 12-inch profile soil sample depth)
UI_SOIL_TEST_PPM_TO_LBS: float = 3.5

# Default soil test value (ppm) — equivalent to old 20 lbs/acre ÷ 3.5 ≈ 5.7 ppm
DEFAULT_SOIL_TEST_NO3_PPM: float = 5.7

# ── Residue Nitrogen Immobilization ───────────────────────────────────────────
# Cereal straw left in field immobilizes N as microbes decompose high-C residue
# Source: UI CIS 453 — 15 lbs N debit per ton of dry cereal straw per acre
UI_CEREAL_RESIDUE_LBS_N_PER_TON: float = 15.0

# ── Table 5: Legume Cover Crop N Credit (lbs N/acre) ─────────────────────────
# Estimated plant-available N from previous season legume residue
# Source: UI Extension Table 5 representative values
UI_LEGUME_N_CREDITS: dict[str, float] = {
    "None":                 0.0,
    "Field Peas":          50.0,
    "Lentils":             40.0,
    "Austrian Winter Peas": 60.0,
    "Sweet Clover":       120.0,
    "Red Clover":         100.0,
    "Alfalfa (1 yr)":      80.0,
    "Hairy Vetch":         90.0,
}

# Default SOM% for Rexburg / SE Idaho dryland (2.4% yields 48 lbs N/acre conv)
DEFAULT_SOM_PCT: float = 2.4
