"""
math_engine.py — Pure calculation functions for N-SIGHT.

Rules:
- No st.* imports or calls anywhere in this file.
- All functions accept and return Python primitives or Polars DataFrames.
- No global mutable state.
"""

import polars as pl

from src.constants import (
    LEGUME_N_CREDIT_LBS_ACRE,
    HIGH_CARBON_N_DEBIT_LBS_ACRE,
    LBS_N_PER_BU_WHEAT,
    FARM_NUE_OPTIMAL_LOW,
    FARM_NUE_OPTIMAL_HIGH,
    N_TO_PROTEIN_FACTOR,
    N_GRAMS_PER_G_PROTEIN,
    BREAD_PROTEIN_PER_100G,
    PRODUCT_VARIANTS,
    REFERENCE_LOAF_MASS_KG,
    AUDIT_HIGH_SCORE,
    AUDIT_MED_SCORE,
    AUDIT_LOW_SCORE,
    # University of Idaho CIS 453 tables
    UI_PRECIP_ZONES,
    UI_SOM_N_CREDIT_TABLE,
    UI_SOIL_TEST_PPM_TO_LBS,
    UI_CEREAL_RESIDUE_LBS_N_PER_TON,
)
from src.models import PIPELINE_SCHEMA, PipelineRow

# Wheat-specific physical constant: standard bushel weight.
# Not in constants.py (which holds agronomic defaults only).
# Source: USDA standard — 1 bushel hard red winter wheat = 60 lbs.
_LBS_GRAIN_PER_BU_WHEAT: float = 60.0

# Grams per pound (exact SI conversion).
_G_PER_LB: float = 453.592


# ── §5.1 Segment 1: Farm ──────────────────────────────────────────────────────

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
    Returns: lbs N / acre (may be negative when soil credits exceed demand)
    """
    n = (yield_potential_bu_acre * precip_index) - (som_n + soil_test_n)
    if legume_credit:
        n += LEGUME_N_CREDIT_LBS_ACRE
    if high_carbon_debit:
        n -= HIGH_CARBON_N_DEBIT_LBS_ACRE
    return n


def calc_grain_n_uptake(yield_potential_bu_acre: float) -> float:
    """
    grain_n_uptake = yield_potential × LBS_N_PER_BU_WHEAT
    Returns: lbs N / acre
    """
    return yield_potential_bu_acre * LBS_N_PER_BU_WHEAT


def calc_farm_nue(grain_n_uptake: float, n_application: float) -> float:
    """
    farm_nue = (grain_n_uptake / n_application) × 100
    Returns: float (percentage)
    Raises: ZeroDivisionError if n_application == 0
    """
    if n_application == 0:
        raise ZeroDivisionError("N application cannot be zero — check farm input credits.")
    return (grain_n_uptake / n_application) * 100.0


def validate_farm_nue(nue: float) -> dict:
    """
    Classify Farm NUE into one of three status bands.

    Returns: {"status": str, "message": str, "color": str}

    Bands (from §5.1):
      nue > 100       → "critical"   #FF4B4B
      70 ≤ nue ≤ 90  → "optimal"    #21C55D
      all others      → "warning"    #F59E0B  (covers nue < 70 AND 90 < nue ≤ 100)
    """
    if nue > 100.0:
        return {
            "status": "critical",
            "message": (
                "CRITICAL WARNING: Soil Mining Detected! Crop is extracting more "
                "nutrients than are being replenished, putting long-term soil health at risk."
            ),
            "color": "#FF4B4B",
        }
    if FARM_NUE_OPTIMAL_LOW <= nue <= FARM_NUE_OPTIMAL_HIGH:
        return {
            "status": "optimal",
            "message": "Optimal Efficiency Target Band Achieved.",
            "color": "#21C55D",
        }
    return {
        "status": "warning",
        "message": (
            "Environmental Loss Risk: High probability of nitrogen leaching "
            "or gaseous volatilization."
        ),
        "color": "#F59E0B",
    }


# ── §5.2 Segment 2: Mill ──────────────────────────────────────────────────────

def calc_mill_output(
    grain_n_lbs_acre: float,
    extraction_rate_pct: float,
) -> dict:
    """
    flour_n = grain_n × (extraction_rate / 100)
    bran_n  = grain_n - flour_n
    mill_nue = (flour_n / grain_n) × 100  — numerically equals extraction_rate_pct

    Returns: {"flour_n": float, "bran_n": float, "mill_nue": float}
    Units: same as grain_n_lbs_acre input (lbs N / acre)
    """
    flour_n = grain_n_lbs_acre * (extraction_rate_pct / 100.0)
    bran_n = grain_n_lbs_acre - flour_n
    mill_nue = (flour_n / grain_n_lbs_acre) * 100.0 if grain_n_lbs_acre != 0 else 0.0
    return {"flour_n": flour_n, "bran_n": bran_n, "mill_nue": mill_nue}


# ── §5.3 Segment 3: Bakery & Retail ──────────────────────────────────────────

def calc_bakery_output(
    flour_n_g: float,
    product_variant: str,
    spoilage_waste_pct: float,
) -> dict:
    """
    Step 1: Apply moisture loss  (PRODUCT_VARIANTS[variant]["moisture_loss_pct"])
    Step 2: Apply waste_factor   (PRODUCT_VARIANTS[variant]["waste_factor"])
    Step 3: Apply spoilage_waste_pct
    Step 4: Normalize to 1 kg reference loaf (already expressed per-loaf by caller)

    final_n_g     = flour_n_g × (1 - moisture_loss/100) × (1 - spoilage/100) / waste_factor
    protein_g     = final_n_g × N_TO_PROTEIN_FACTOR
    bakery_nue    = (final_n_g / flour_n_g) × 100
    protein_pct_dw = protein_g / 1000 × 100

    Returns: {"final_n_g": float, "protein_g": float, "bakery_nue": float, "protein_pct_dw": float}
    """
    if product_variant not in PRODUCT_VARIANTS:
        raise ValueError(
            f"Unknown product_variant '{product_variant}'. "
            f"Valid options: {list(PRODUCT_VARIANTS.keys())}"
        )
    variant = PRODUCT_VARIANTS[product_variant]
    moisture_loss_pct = variant["moisture_loss_pct"]
    waste_factor = variant["waste_factor"]

    final_n_g = (
        flour_n_g
        * (1.0 - moisture_loss_pct / 100.0)
        * (1.0 - spoilage_waste_pct / 100.0)
        / waste_factor
    )
    # Protein conversion uses the PNW regional scalar (0.175 g N / g protein).
    # Equivalent to Kjeldahl factor 1/0.175 = 5.7143 — supersedes the generic 5.7.
    protein_g = final_n_g / N_GRAMS_PER_G_PROTEIN
    bakery_nue = (final_n_g / flour_n_g) * 100.0 if flour_n_g != 0 else 0.0
    protein_pct_dw = (protein_g / (REFERENCE_LOAF_MASS_KG * 1000.0)) * 100.0

    # Reference benchmark for a 1 kg shelf loaf (PNW hard red winter wheat):
    #   reference_protein_g = BREAD_PROTEIN_PER_100G × 10  = 123.0 g
    #   reference_n_g       = 123.0 × N_GRAMS_PER_G_PROTEIN = 21.525 g
    reference_protein_g = BREAD_PROTEIN_PER_100G * 10.0
    reference_n_g       = reference_protein_g * N_GRAMS_PER_G_PROTEIN

    return {
        "final_n_g":          final_n_g,
        "protein_g":          protein_g,
        "bakery_nue":         bakery_nue,
        "protein_pct_dw":     protein_pct_dw,
        "reference_n_g":      reference_n_g,       # 21.525 g — calibration target
        "reference_protein_g": reference_protein_g, # 123.0 g — calibration target
    }


# ── §5.4 System NUE (End-to-End) ──────────────────────────────────────────────

def calc_system_nue(
    n_applied_lbs_acre: float,
    final_n_g_per_kg_loaf: float,
    yield_bu_acre: float,
    loaves_per_acre: float,
) -> float:
    """
    system_nue = (final_n_g × loaves_per_acre) / (n_applied_lbs_acre × 453.592) × 100
    Units: lbs → grams conversion factor = 453.592
    Returns: float (percentage)
    """
    n_applied_g_acre = n_applied_lbs_acre * _G_PER_LB
    if n_applied_g_acre == 0:
        raise ZeroDivisionError("N applied per acre cannot be zero for system NUE.")
    return (final_n_g_per_kg_loaf * loaves_per_acre) / n_applied_g_acre * 100.0


# ── Economic Engine ───────────────────────────────────────────────────────────

# Urea (standard fertilizer) N-content fraction used for cost conversion.
_UREA_N_FRACTION: float = 0.46   # 46% N by mass (industry standard)
_LBS_PER_TON: float     = 2000.0


def calc_economic_return(
    yield_bu: float,
    price_per_bu: float,
    n_applied_lbs: float,
    cost_per_ton_fertilizer: float,
) -> dict:
    """
    Compute per-acre economic margin for a fertilizer application scenario.

    Steps:
      1. Convert fertilizer cost from $/ton → $/lb of N:
           cost_per_lb_N = (cost_per_ton / 2000) / 0.46
         (assumes standard urea at 46% N content)
      2. Gross Revenue   = yield_bu × price_per_bu
      3. Fertilizer Cost = n_applied_lbs × cost_per_lb_N
      4. Net Margin      = Gross Revenue − Fertilizer Cost

    Returns:
      {
        "gross_revenue":    float,   # $ / acre
        "fertilizer_cost":  float,   # $ / acre
        "net_margin":       float,   # $ / acre
        "cost_per_lb_n":    float,   # $/lb N (derived)
      }
    """
    cost_per_lb_n  = (cost_per_ton_fertilizer / _LBS_PER_TON) / _UREA_N_FRACTION
    gross_revenue  = yield_bu * price_per_bu
    fertilizer_cost = n_applied_lbs * cost_per_lb_n
    net_margin     = gross_revenue - fertilizer_cost
    return {
        "gross_revenue":   gross_revenue,
        "fertilizer_cost": fertilizer_cost,
        "net_margin":      net_margin,
        "cost_per_lb_n":   cost_per_lb_n,
    }


# ── §5.5 Polars Pipeline Assembly ─────────────────────────────────────────────

def calc_loaves_per_acre(
    yield_bu_acre: float,
    extraction_rate_pct: float,
    product_variant: str,
    spoilage_waste_pct: float,
) -> float:
    """
    Derive the number of reference 1 kg loaves produced per acre.

    Chain:
      grain_g_acre  = yield_bu_acre × _LBS_GRAIN_PER_BU_WHEAT × _G_PER_LB
      flour_g_acre  = grain_g_acre × (extraction_rate_pct / 100)
      final_g_acre  = flour_g_acre
                      × (1 - moisture_loss/100)
                      × (1 - spoilage/100)
                      / waste_factor
      loaves_per_acre = final_g_acre / (REFERENCE_LOAF_MASS_KG × 1000)
    """
    if product_variant not in PRODUCT_VARIANTS:
        raise ValueError(f"Unknown product_variant '{product_variant}'.")
    variant = PRODUCT_VARIANTS[product_variant]

    grain_g_acre = yield_bu_acre * _LBS_GRAIN_PER_BU_WHEAT * _G_PER_LB
    flour_g_acre = grain_g_acre * (extraction_rate_pct / 100.0)
    final_g_acre = (
        flour_g_acre
        * (1.0 - variant["moisture_loss_pct"] / 100.0)
        * (1.0 - spoilage_waste_pct / 100.0)
        / variant["waste_factor"]
    )
    return final_g_acre / (REFERENCE_LOAF_MASS_KG * 1000.0)


def build_pipeline_df(
    # Farm
    n_application_lbs_acre: float,
    grain_n_uptake_lbs_acre: float,
    farm_nue_pct: float,
    farm_data_score: int,
    # Mill
    flour_n_lbs_acre: float,
    bran_n_lbs_acre: float,
    mill_nue_pct: float,
    mill_data_score: int,
    # Bakery
    flour_n_g_per_loaf: float,
    bakery_result: dict,
    bakery_data_score: int,
    # Conversion
    loaves_per_acre: float,
) -> pl.DataFrame:
    """
    Assemble a Polars DataFrame conforming to PIPELINE_SCHEMA.

    All per-acre lbs values are converted to per-loaf grams using:
      g_per_loaf = lbs_per_acre × _G_PER_LB / loaves_per_acre

    One row per segment: Farm, Mill, Bakery & Retail.
    """
    def _score_label(score: int) -> str:
        if score >= AUDIT_HIGH_SCORE:
            return "High (Direct Measurement)"
        if score >= AUDIT_MED_SCORE:
            return "Medium (Aggregated DB)"
        return "Low (Rules of Thumb)"

    def _to_g_per_loaf(lbs_per_acre: float) -> float:
        return lbs_per_acre * _G_PER_LB / loaves_per_acre if loaves_per_acre else 0.0

    farm_n_in  = _to_g_per_loaf(n_application_lbs_acre)
    farm_n_out = _to_g_per_loaf(grain_n_uptake_lbs_acre)

    mill_n_in  = _to_g_per_loaf(grain_n_uptake_lbs_acre)
    mill_n_out = _to_g_per_loaf(flour_n_lbs_acre)

    bakery_n_in  = flour_n_g_per_loaf
    bakery_n_out = bakery_result["final_n_g"]

    rows = [
        PipelineRow(
            segment="Farm",
            n_in_g=farm_n_in,
            n_out_g=farm_n_out,
            n_loss_g=farm_n_in - farm_n_out,
            nue_pct=farm_nue_pct,
            data_score=farm_data_score,
            data_label=_score_label(farm_data_score),
        ),
        PipelineRow(
            segment="Mill",
            n_in_g=mill_n_in,
            n_out_g=mill_n_out,
            n_loss_g=mill_n_in - mill_n_out,
            nue_pct=mill_nue_pct,
            data_score=mill_data_score,
            data_label=_score_label(mill_data_score),
        ),
        PipelineRow(
            segment="Bakery & Retail",
            n_in_g=bakery_n_in,
            n_out_g=bakery_n_out,
            n_loss_g=bakery_n_in - bakery_n_out,
            nue_pct=bakery_result["bakery_nue"],
            data_score=bakery_data_score,
            data_label=_score_label(bakery_data_score),
        ),
    ]

    return pl.DataFrame(
        [row.to_dict() for row in rows],
        schema=PIPELINE_SCHEMA,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# University of Idaho Extension — CIS 453 Precision N Engine
# Replaces the simplified precip_index × yield formula with the full
# zone-based demand model, SOM table lookup, ppm soil test conversion,
# and residue immobilization as specified in UI Extension CIS 453.
# ═══════════════════════════════════════════════════════════════════════════════

def get_n_demand_factor(annual_precip_in: float) -> float:
    """
    Look up lbs N / bu yield potential from the UI CIS 453 precipitation zone table.

    Zones (annual precip, inches):
      <  18 in → 2.4 lbs N/bu
      18–21 in → 2.5 lbs N/bu
      21–24 in → 2.7 lbs N/bu
      24–28 in → 2.9 lbs N/bu
      >  28 in → 3.1 lbs N/bu
    """
    for low, high, factor in UI_PRECIP_ZONES:
        if low <= annual_precip_in < high:
            return factor
    return UI_PRECIP_ZONES[-1][2]   # fallback: highest zone


def get_som_n_credit(som_pct: float, tillage: str) -> float:
    """
    Look up SOM N mineralization credit from UI CIS 453 Table 2 (step function).

    som_pct  — soil organic matter percentage (e.g. 2.4)
    tillage  — "conventional" | "reduced" (any capitalisation, prefix matched)

    Returns lbs N/acre/year available from SOM mineralisation.

    Table 2 — exact CIS 453 published values (0.2 % SOM steps):
      SOM < 1.0%  → Conv 20 / Reduced 17
      1.0–1.1%    → Conv 22 / Reduced 19
      1.2–1.3%    → Conv 26 / Reduced 22
      1.4–1.5%    → Conv 30 / Reduced 26
      1.6–1.7%    → Conv 34 / Reduced 29
      1.8–1.9%    → Conv 38 / Reduced 32
      2.0–2.1%    → Conv 42 / Reduced 36
      2.2–2.3%    → Conv 46 / Reduced 39
      2.4–2.5%    → Conv 50 / Reduced 43   ← PNW dryland baseline
      2.6–2.7%    → Conv 54 / Reduced 46
      2.8–2.9%    → Conv 58 / Reduced 48
      ≥ 3.0%      → Conv 60 / Reduced 51
    """
    use_conv = tillage.lower().startswith("conv")
    for lo, hi, conv_val, red_val in UI_SOM_N_CREDIT_TABLE:
        if lo <= som_pct < hi:
            return conv_val if use_conv else red_val
    # Fallback: clamp to highest tier
    return UI_SOM_N_CREDIT_TABLE[-1][2] if use_conv else UI_SOM_N_CREDIT_TABLE[-1][3]


def calc_n_application_idaho(
    yield_potential_bu: float,
    annual_precip_in:   float,
    som_pct:            float,
    tillage:            str,    # "conventional" | "reduced"
    soil_test_no3_ppm:  float,
    straw_tons_acre:    float,
    legume_n_credit_lbs: float,
) -> float:
    """
    University of Idaho CIS 453 Net Nitrogen Recommendation.

    Formula:
        N_app = (yield × zone_factor)
                - SOM_credit(som_pct, tillage)
                - soil_test_no3_ppm × 3.5
                - legume_n_credit_lbs
                + straw_tons_acre × 15

    All terms in lbs N / acre.
    Returns max(result, 0) — negative recommendation means no commercial N needed.

    Parameters
    ----------
    yield_potential_bu   : expected yield (bu/acre)
    annual_precip_in     : mean annual precipitation (inches) for zone selection
    som_pct              : soil organic matter %
    tillage              : "conventional" or "reduced"
    soil_test_no3_ppm    : soil nitrate from lab analysis (ppm NO₃-N, 12-inch profile)
    straw_tons_acre      : cereal straw remaining in field (dry tons/acre)
    legume_n_credit_lbs  : N credit from previous legume crop (lbs N/acre, 0 if none)
    """
    zone_factor   = get_n_demand_factor(annual_precip_in)
    total_demand  = yield_potential_bu * zone_factor

    som_credit    = get_som_n_credit(som_pct, tillage)
    soil_credit   = soil_test_no3_ppm * UI_SOIL_TEST_PPM_TO_LBS
    straw_debit   = straw_tons_acre * UI_CEREAL_RESIDUE_LBS_N_PER_TON

    n_app = total_demand - som_credit - soil_credit - legume_n_credit_lbs + straw_debit
    return max(n_app, 0.0)


# ── Urea Market Economic Calculator ───────────────────────────────────────────
# Separate from the existing calc_economic_return (which uses cost_per_ton_fertilizer
# / price_per_bu signature for the main NUE dashboard). This version accepts the
# urea-market-specific parameter names used by the Urea Market Trend tab.

def calc_urea_economic_return(
    n_applied_lbs: float,
    yield_bu: float,
    market_wheat_price: float,
    urea_price_per_ton: float,
) -> dict:
    """
    Calculates economic return for a nitrogen application scenario.
    Urea contains exactly 46% active nitrogen by weight.

    Returns:
      {
        "urea_needed_lbs":      float,  # lbs of urea required (N ÷ 0.46)
        "gross_revenue":        float,  # yield_bu × market_wheat_price
        "fertilizer_cost":      float,  # cost of urea needed
        "net_operating_margin": float,  # gross_revenue − fertilizer_cost
      }
    """
    _UREA_N_FRACTION = 0.46
    _LBS_PER_TON     = 2000.0

    urea_needed_lbs     = n_applied_lbs / _UREA_N_FRACTION
    urea_total_cost     = (urea_needed_lbs / _LBS_PER_TON) * urea_price_per_ton
    gross_revenue       = yield_bu * market_wheat_price
    net_operating_margin = gross_revenue - urea_total_cost

    return {
        "urea_needed_lbs":      round(urea_needed_lbs,      2),
        "gross_revenue":        round(gross_revenue,        2),
        "fertilizer_cost":      round(urea_total_cost,      2),
        "net_operating_margin": round(net_operating_margin, 2),
    }


# ── NitrogenCal2 helper functions (do not rename or edit these) ──────────

def CalPrecipitation(rainfall_inch: float) -> float:
    """Converts annual rainfall (inches) to N uptake factor."""
    try:
        inches = float(rainfall_inch)
        if inches < 18:
            return 2.4
        elif 18 <= inches < 21:
            return 2.5
        elif 21 <= inches < 24:
            return 2.7
        elif 24 <= inches < 28:
            return 2.9
        else:
            return 3.1
    except (ValueError, TypeError):
        return 2.4


def calMineralisable(organic_matter: float) -> float:
    """
    Returns N credit (lbs/acre) from soil organic matter %.
    Negative value = N already available, reduces fertilizer need.
    Note: every 0.1% OM above 1.0% adds -2 lbs N credit.
    """
    om = round(float(organic_matter), 1)
    if om <= 1.0:
        return -20
    elif om >= 3.0:
        return -60
    else:
        return -20 - int((om - 1.0) * 20) * 2


def determinePreviousCereal(cereal_residue: float) -> float:
    """
    Returns positive N adjustment for cereal crop residue (tons/acre).
    Positive = need MORE N because straw ties up nitrogen.
    """
    mapping = {0: 0, 0.5: 7.5, 1: 15, 2: 30, 2.5: 37.5, 3: 45, 3.5: 50}
    return mapping.get(cereal_residue, 0)


def determinePreviousLegumes(legume_residue: float) -> float:
    """
    Returns negative N adjustment for legume crop residue (tons/acre).
    Negative = need LESS N because legumes fix nitrogen.
    """
    mapping = {0: 0, 1: -8, 1.5: -23, 2: -30, 3: -45, 3.5: -60}
    return mapping.get(legume_residue, 0)


def run_collaborative_calculation_engine(
    yield_potential:    float,
    precip_index:       float,
    som_pct:            float,
    soil_test_ppm:      float,
    tillage_selection:  str,
    legume_toggle:      bool,
    residue_toggle:     bool,
    user_urea_price:    float,
    ppm_0_12:           float = 5.0,
    ppm_12_24:          float = 3.0,
    ppm_24_36:          float = 2.0,
    residue_level:      float = 2.0,
) -> dict:
    """
    Agronomic N recommendation engine based on NitrogenCal2 methodology.

    Parameters (original — unchanged)
    ──────────────────────────────────
    yield_potential   : Expected crop yield in bu/acre
    precip_index      : Annual rainfall in inches (12–35 typical NW range)
    som_pct           : Soil organic matter percentage (0.5–5.0)
    soil_test_ppm     : Legacy field — not used when depth readings are passed
    tillage_selection : Tillage type string — reserved for future use
    legume_toggle     : True = previous crop was a legume
    residue_toggle    : True = cereal residue is present (only used when legume_toggle is False)
    user_urea_price   : Urea price in USD/ton

    New optional parameters (existing app.py calls still work via defaults)
    ────────────────────────────────────────────────────────────────────────
    ppm_0_12          : Soil nitrate PPM, 0–12 inch depth  (default 5.0)
    ppm_12_24         : Soil nitrate PPM, 12–24 inch depth (default 3.0)
    ppm_24_36         : Soil nitrate PPM, 24–36 inch depth (default 2.0)
    residue_level     : Residue amount in tons/acre for lookup tables (default 2.0)
    """

    # ══════════════════════════════════════════════════════════════
    # ►► NitrogenCal2 CALCULATION ENGINE                          ◄◄
    # ══════════════════════════════════════════════════════════════

    # Step 1 — Precipitation factor from annual rainfall
    precipitation_factor = CalPrecipitation(precip_index)

    # Step 2 — Base Nitrogen Requirement (BLR)
    BLR = yield_potential * precipitation_factor

    # Step 3 — Soil Organic Matter credit (negative = N already available)
    mini_credit = calMineralisable(som_pct)

    # Step 4 — Soil Nitrate credit
    # Multiply each 12-inch depth reading by 3.5 (PPM → lbs/acre conversion)
    SN_credit = (ppm_0_12 + ppm_12_24 + ppm_24_36) * 3.5

    # Step 5 — Previous crop residue credit
    if legume_toggle:
        residue_credit = determinePreviousLegumes(residue_level)
    else:
        residue_credit = determinePreviousCereal(residue_level) if residue_toggle else 0

    # Step 6 — Final N requirement
    # mini_credit and legume residue_credit are negative numbers (they reduce N need)
    # SN_credit is positive and subtracted separately
    nitrogen_required = BLR + float(mini_credit) + float(residue_credit) - SN_credit
    nitrogen_required = max(0.0, nitrogen_required)

    # ══════════════════════════════════════════════════════════════
    # ►► END OF CALCULATION ENGINE                                ◄◄
    # ══════════════════════════════════════════════════════════════

    # Downstream economics (do not modify)
    UREA_N_FRACTION = 0.46
    LBS_PER_TON     = 2000.0
    bulk_urea_needed     = nitrogen_required / UREA_N_FRACTION
    calculated_urea_cost = (bulk_urea_needed / LBS_PER_TON) * user_urea_price

    # Standardized output payload — do NOT rename these keys
    return {
        "nitrogen_required":    round(nitrogen_required, 2),
        "bulk_urea_needed":     round(bulk_urea_needed, 2),
        "calculated_urea_cost": round(calculated_urea_cost, 2),
        "gross_n_demand":       round(BLR, 2),
        "available_n_sources":  round(SN_credit + abs(mini_credit), 2),
        "calculation_breakdown": {
            "base_n_requirement_blr": round(BLR, 2),
            "precipitation_factor":   round(precipitation_factor, 2),
            "om_credit":              round(mini_credit, 2),
            "soil_nitrate_credit":    round(SN_credit, 2),
            "residue_credit":         round(float(residue_credit), 2),
        },
        "inputs_used": {
            "yield_potential":   yield_potential,
            "precip_index":      precip_index,
            "som_pct":           som_pct,
            "soil_test_ppm":     soil_test_ppm,
            "tillage_selection": tillage_selection,
            "legume_toggle":     legume_toggle,
            "residue_toggle":    residue_toggle,
            "user_urea_price":   user_urea_price,
            "ppm_0_12":          ppm_0_12,
            "ppm_12_24":         ppm_12_24,
            "ppm_24_36":         ppm_24_36,
            "residue_level":     residue_level,
        },
    }
