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
    "Baguette":               {"moisture_loss_pct": 25.0, "waste_factor": 1.10},
    "Whole Meal Sliced Loaf": {"moisture_loss_pct": 15.0, "waste_factor": 1.05},
}
DEFAULT_SPOILAGE_WASTE_PCT        = 5.0     # % processing/distribution loss
REFERENCE_LOAF_MASS_KG            = 1.0

# ── Protein Conversion ─────────────────────────────────────────────────────────
N_TO_PROTEIN_FACTOR               = 5.7    # g protein = g N × 5.7 (wheat standard)

# ── Track 2: Audit Scoring ─────────────────────────────────────────────────────
AUDIT_HIGH_SCORE     = 5    # IoT / farm-level ledger
AUDIT_MED_SCORE      = 3    # Regional / cooperative DB
AUDIT_LOW_SCORE      = 1    # Stale industry rules-of-thumb
AUDIT_RISK_THRESHOLD = 2    # Scores ≤ this value trigger red heatmap cell

# ── Precipitation Lookup ───────────────────────────────────────────────────────
METEOSTAT_LOOKBACK_YEARS  = 10    # rolling average period
PRECIP_INDEX_BASELINE_MM  = 450   # mm/year baseline for index = 1.0
