"""
test_math_engine.py — Unit tests for src/math_engine.py

Coverage:
  - Normal baseline operations using authoritative defaults from constants.py
  - All three validate_farm_nue guardrail bands (critical, optimal, warning)
  - Edge case: NUE exactly at band boundaries (70, 90, 100)
  - Zero-division protection for calc_farm_nue and calc_system_nue
  - calc_mill_output with default and whole-meal extraction rates
  - calc_bakery_output for both product variants
  - calc_loaves_per_acre derivation
  - build_pipeline_df schema integrity
"""

import math
import pytest
import polars as pl

from src.constants import (
    DEFAULT_YIELD_POTENTIAL_BU_ACRE,
    DEFAULT_PRECIPITATION_INDEX,
    DEFAULT_SOM_N_LBS_ACRE,
    DEFAULT_SOIL_TEST_N_LBS_ACRE,
    LEGUME_N_CREDIT_LBS_ACRE,
    HIGH_CARBON_N_DEBIT_LBS_ACRE,
    LBS_N_PER_BU_WHEAT,
    DEFAULT_FARM_FERTILIZER_APPLIED,
    FARM_NUE_OPTIMAL_LOW,
    FARM_NUE_OPTIMAL_HIGH,
    DEFAULT_EXTRACTION_RATE_PCT,
    WHOLEMEAL_EXTRACTION_RATE_PCT,
    DEFAULT_SPOILAGE_WASTE_PCT,
    N_TO_PROTEIN_FACTOR,
    N_GRAMS_PER_G_PROTEIN,
    BREAD_PROTEIN_PER_100G,
    REFERENCE_LOAF_MASS_KG,
    AUDIT_MED_SCORE,
    DEFAULT_WHEAT_PRICE_PER_BU,
    DEFAULT_FERTILIZER_PRICE_PER_TON,
)
from src.math_engine import (
    calc_n_application,
    calc_grain_n_uptake,
    calc_farm_nue,
    validate_farm_nue,
    calc_mill_output,
    calc_bakery_output,
    calc_system_nue,
    calc_economic_return,
    calc_loaves_per_acre,
    build_pipeline_df,
    _G_PER_LB,
    _UREA_N_FRACTION,
    _LBS_PER_TON,
)
from src.models import PIPELINE_SCHEMA


# ── Helpers ───────────────────────────────────────────────────────────────────

def approx(value, rel=1e-6):
    return pytest.approx(value, rel=rel)


# Pre-compute baseline values using updated PNW regional constants.
# DEFAULT_YIELD_POTENTIAL_BU_ACRE = 72.0,  LBS_N_PER_BU_WHEAT = 2.625
# _BASELINE_N_APP  = (72 × 1.0) − (30 + 20)  = 22.0 lbs/acre
# _BASELINE_UPTAKE = 72 × 2.625              = 189.0 lbs/acre
# _BASELINE_NUE    = (189 / 22) × 100        ≈ 859.09 %
_BASELINE_N_APP  = (DEFAULT_YIELD_POTENTIAL_BU_ACRE * DEFAULT_PRECIPITATION_INDEX) \
                   - (DEFAULT_SOM_N_LBS_ACRE + DEFAULT_SOIL_TEST_N_LBS_ACRE)
_BASELINE_UPTAKE = DEFAULT_YIELD_POTENTIAL_BU_ACRE * LBS_N_PER_BU_WHEAT
_BASELINE_NUE    = (_BASELINE_UPTAKE / _BASELINE_N_APP) * 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# §5.1  SEGMENT 1 — FARM
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalcNApplication:
    def test_baseline_defaults(self):
        result = calc_n_application(
            yield_potential_bu_acre=DEFAULT_YIELD_POTENTIAL_BU_ACRE,
            precip_index=DEFAULT_PRECIPITATION_INDEX,
            som_n=DEFAULT_SOM_N_LBS_ACRE,
            soil_test_n=DEFAULT_SOIL_TEST_N_LBS_ACRE,
            legume_credit=False,
            high_carbon_debit=False,
        )
        # (72 × 1.0) − (30 + 20) = 22.0 lbs/acre
        assert result == approx(22.0)

    def test_legume_credit_adds_to_n(self):
        base = calc_n_application(60.0, 1.0, 30.0, 20.0, False, False)
        with_legume = calc_n_application(60.0, 1.0, 30.0, 20.0, True, False)
        assert with_legume == approx(base + LEGUME_N_CREDIT_LBS_ACRE)

    def test_high_carbon_debit_subtracts_from_n(self):
        base = calc_n_application(60.0, 1.0, 30.0, 20.0, False, False)
        with_debit = calc_n_application(60.0, 1.0, 30.0, 20.0, False, True)
        assert with_debit == approx(base - HIGH_CARBON_N_DEBIT_LBS_ACRE)

    def test_both_toggles_applied(self):
        # Use explicit values (not defaults) so this test is stable across constant changes
        result = calc_n_application(60.0, 1.0, 30.0, 20.0, True, True)
        # (60×1.0 - 50) + 35 - 15 = 10 + 35 - 15 = 30.0
        assert result == approx(30.0)

    def test_precip_index_scales_yield(self):
        low_rain  = calc_n_application(60.0, 0.5, 0.0, 0.0, False, False)
        high_rain = calc_n_application(60.0, 2.0, 0.0, 0.0, False, False)
        assert high_rain == approx(4.0 * low_rain)

    def test_negative_result_when_credits_exceed_demand(self):
        result = calc_n_application(60.0, 1.0, 50.0, 30.0, False, False)
        assert result < 0.0


class TestCalcGrainNUptake:
    def test_baseline(self):
        result = calc_grain_n_uptake(DEFAULT_YIELD_POTENTIAL_BU_ACRE)
        assert result == approx(DEFAULT_YIELD_POTENTIAL_BU_ACRE * LBS_N_PER_BU_WHEAT)

    def test_proportional_to_yield(self):
        assert calc_grain_n_uptake(120.0) == approx(2.0 * calc_grain_n_uptake(60.0))

    def test_zero_yield(self):
        assert calc_grain_n_uptake(0.0) == approx(0.0)


class TestCalcFarmNue:
    def test_baseline_nue_is_critical(self):
        # 189 lbs uptake / 22 lbs applied × 100 ≈ 859.09 % → always in "critical" band
        result = calc_farm_nue(_BASELINE_UPTAKE, _BASELINE_N_APP)
        assert result == approx(_BASELINE_NUE)
        assert result > 100.0   # confirms soil-mining status with PNW constants

    def test_optimal_band_example(self):
        # 80% NUE: uptake = 80, applied = 100
        assert calc_farm_nue(80.0, 100.0) == approx(80.0)

    def test_zero_application_raises(self):
        with pytest.raises(ZeroDivisionError):
            calc_farm_nue(_BASELINE_UPTAKE, 0.0)

    def test_result_is_percentage(self):
        # uptake == applied → NUE == 100%
        assert calc_farm_nue(50.0, 50.0) == approx(100.0)


class TestValidateFarmNue:
    """Three guardrail bands + exact boundary values."""

    # --- CRITICAL (soil mining): nue > 100 ---
    def test_soil_mining_above_100(self):
        result = validate_farm_nue(210.0)
        assert result["status"] == "critical"
        assert result["color"] == "#FF4B4B"
        assert "Soil Mining" in result["message"]

    def test_soil_mining_just_above_100(self):
        result = validate_farm_nue(100.01)
        assert result["status"] == "critical"

    # --- OPTIMAL: 70 ≤ nue ≤ 90 ---
    def test_optimal_mid_band(self):
        result = validate_farm_nue(80.0)
        assert result["status"] == "optimal"
        assert result["color"] == "#21C55D"
        assert "Optimal" in result["message"]

    def test_optimal_lower_boundary(self):
        result = validate_farm_nue(FARM_NUE_OPTIMAL_LOW)   # exactly 70
        assert result["status"] == "optimal"

    def test_optimal_upper_boundary(self):
        result = validate_farm_nue(FARM_NUE_OPTIMAL_HIGH)  # exactly 90
        assert result["status"] == "optimal"

    # --- WARNING: everything else (<70 and 90 < nue ≤ 100) ---
    def test_warning_below_70(self):
        result = validate_farm_nue(50.0)
        assert result["status"] == "warning"
        assert result["color"] == "#F59E0B"
        assert "leaching" in result["message"].lower() or "volatilization" in result["message"].lower()

    def test_warning_just_below_70(self):
        result = validate_farm_nue(69.99)
        assert result["status"] == "warning"

    def test_warning_between_90_and_100(self):
        # 90 < nue ≤ 100 is outside the optimal band but not critical
        result = validate_farm_nue(95.0)
        assert result["status"] == "warning"

    def test_exactly_100_is_warning_not_critical(self):
        result = validate_farm_nue(100.0)
        assert result["status"] == "warning"

    def test_return_dict_has_required_keys(self):
        for nue in (50.0, 80.0, 150.0):
            result = validate_farm_nue(nue)
            assert {"status", "message", "color"} == set(result.keys())


# ═══════════════════════════════════════════════════════════════════════════════
# §5.2  SEGMENT 2 — MILL
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalcMillOutput:
    def test_baseline_extraction(self):
        # DEFAULT_EXTRACTION_RATE_PCT = 76.54, _BASELINE_UPTAKE = 189.0
        result = calc_mill_output(_BASELINE_UPTAKE, DEFAULT_EXTRACTION_RATE_PCT)
        expected_flour = _BASELINE_UPTAKE * (DEFAULT_EXTRACTION_RATE_PCT / 100.0)
        expected_bran  = _BASELINE_UPTAKE - expected_flour
        assert result["flour_n"]  == approx(expected_flour)
        assert result["bran_n"]   == approx(expected_bran)
        assert result["mill_nue"] == approx(DEFAULT_EXTRACTION_RATE_PCT)

    def test_wholemeal_100_pct_extraction(self):
        result = calc_mill_output(100.0, WHOLEMEAL_EXTRACTION_RATE_PCT)
        assert result["flour_n"]  == approx(100.0)
        assert result["bran_n"]   == approx(0.0)
        assert result["mill_nue"] == approx(100.0)

    def test_flour_plus_bran_equals_grain(self):
        grain_n = 50.0
        for rate in (60.0, 75.0, 85.0, 100.0):
            r = calc_mill_output(grain_n, rate)
            assert r["flour_n"] + r["bran_n"] == approx(grain_n)

    def test_mill_nue_equals_extraction_rate(self):
        for rate in (60.0, 75.0, 85.0, 100.0):
            r = calc_mill_output(1000.0, rate)
            assert r["mill_nue"] == approx(rate)

    def test_returns_required_keys(self):
        result = calc_mill_output(21.0, 75.0)
        assert {"flour_n", "bran_n", "mill_nue"} == set(result.keys())


# ═══════════════════════════════════════════════════════════════════════════════
# §5.3  SEGMENT 3 — BAKERY & RETAIL
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalcBakeryOutput:
    # Use a round input to make manual verification easy.
    FLOUR_N_G = 100.0

    def _baguette(self, flour_n_g=None, spoilage=DEFAULT_SPOILAGE_WASTE_PCT):
        return calc_bakery_output(
            flour_n_g=flour_n_g or self.FLOUR_N_G,
            product_variant="Baguette",
            spoilage_waste_pct=spoilage,
        )

    def _wholemeal(self, flour_n_g=None, spoilage=DEFAULT_SPOILAGE_WASTE_PCT):
        return calc_bakery_output(
            flour_n_g=flour_n_g or self.FLOUR_N_G,
            product_variant="Whole Meal Sliced Loaf",
            spoilage_waste_pct=spoilage,
        )

    def test_baguette_formula(self):
        result = self._baguette()
        # final_n_g = 100 × (1-0.25) × (1-0.05) / 1.10
        expected_final = 100.0 * 0.75 * 0.95 / 1.10
        assert result["final_n_g"] == approx(expected_final)

    def test_wholemeal_formula(self):
        result = self._wholemeal()
        # final_n_g = 100 × (1-0.15) × (1-0.05) / 1.05
        expected_final = 100.0 * 0.85 * 0.95 / 1.05
        assert result["final_n_g"] == approx(expected_final)

    def test_protein_g_uses_n_grams_per_g_protein(self):
        # Updated formula: protein_g = final_n_g / N_GRAMS_PER_G_PROTEIN  (0.175)
        result = self._baguette()
        assert result["protein_g"] == approx(result["final_n_g"] / N_GRAMS_PER_G_PROTEIN)

    def test_bakery_nue_is_ratio_of_n_out_to_n_in(self):
        result = self._baguette()
        expected_nue = (result["final_n_g"] / self.FLOUR_N_G) * 100.0
        assert result["bakery_nue"] == approx(expected_nue)

    def test_protein_pct_dw_formula(self):
        result = self._baguette()
        expected_pct = (result["protein_g"] / (REFERENCE_LOAF_MASS_KG * 1000.0)) * 100.0
        assert result["protein_pct_dw"] == approx(expected_pct)

    def test_higher_spoilage_reduces_final_n(self):
        low  = self._baguette(spoilage=0.0)
        high = self._baguette(spoilage=20.0)
        assert high["final_n_g"] < low["final_n_g"]

    def test_wholemeal_higher_retention_than_baguette(self):
        baguette  = self._baguette()
        wholemeal = self._wholemeal()
        # Wholemeal has lower moisture loss (15%) and lower waste factor (1.05) vs Baguette (25%, 1.10)
        assert wholemeal["final_n_g"] > baguette["final_n_g"]

    def test_invalid_variant_raises(self):
        with pytest.raises(ValueError, match="Unknown product_variant"):
            calc_bakery_output(100.0, "Focaccia", 5.0)

    def test_returns_required_keys(self):
        result = self._baguette()
        assert {"final_n_g", "protein_g", "bakery_nue", "protein_pct_dw",
                "reference_n_g", "reference_protein_g"} == set(result.keys())


# ═══════════════════════════════════════════════════════════════════════════════
# §5.4  SYSTEM NUE
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalcSystemNue:
    def test_perfect_efficiency(self):
        # If all applied N ends up in every loaf, system NUE = 100%
        n_applied_lbs = 10.0
        n_applied_g = n_applied_lbs * _G_PER_LB   # 4535.92 g/acre
        loaves = 100.0
        final_n_per_loaf = n_applied_g / loaves   # 45.3592 g/loaf
        result = calc_system_nue(n_applied_lbs, final_n_per_loaf, 60.0, loaves)
        assert result == approx(100.0)

    def test_zero_n_applied_raises(self):
        with pytest.raises(ZeroDivisionError):
            calc_system_nue(0.0, 10.0, 60.0, 500.0)

    def test_higher_final_n_gives_higher_system_nue(self):
        base = calc_system_nue(10.0, 5.0, 60.0, 500.0)
        higher = calc_system_nue(10.0, 10.0, 60.0, 500.0)
        assert higher > base

    def test_lbs_to_grams_conversion(self):
        # 1 lb applied, 453.592 g/loaf final, 1 loaf/acre → 100%
        result = calc_system_nue(1.0, _G_PER_LB, 60.0, 1.0)
        assert result == approx(100.0)


# ═══════════════════════════════════════════════════════════════════════════════
# LOAVES PER ACRE
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalcLoavesPerAcre:
    def test_returns_positive_value(self):
        result = calc_loaves_per_acre(60.0, 75.0, "Baguette", 5.0)
        assert result > 0.0

    def test_higher_yield_gives_more_loaves(self):
        low  = calc_loaves_per_acre(60.0, 75.0, "Baguette", 5.0)
        high = calc_loaves_per_acre(120.0, 75.0, "Baguette", 5.0)
        assert high == approx(2.0 * low)

    def test_higher_extraction_gives_more_loaves(self):
        white     = calc_loaves_per_acre(60.0, 75.0,  "Baguette", 5.0)
        wholemeal = calc_loaves_per_acre(60.0, 100.0, "Baguette", 5.0)
        assert wholemeal > white

    def test_invalid_variant_raises(self):
        with pytest.raises(ValueError):
            calc_loaves_per_acre(60.0, 75.0, "Ciabatta", 5.0)


# ═══════════════════════════════════════════════════════════════════════════════
# BUILD PIPELINE DF — schema integrity
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildPipelineDF:
    """Verify that build_pipeline_df returns a correctly-shaped, typed DataFrame."""

    @pytest.fixture()
    def pipeline_df(self):
        mill_out    = calc_mill_output(_BASELINE_UPTAKE, DEFAULT_EXTRACTION_RATE_PCT)
        loaves      = calc_loaves_per_acre(
            DEFAULT_YIELD_POTENTIAL_BU_ACRE,
            DEFAULT_EXTRACTION_RATE_PCT,
            "Baguette",
            DEFAULT_SPOILAGE_WASTE_PCT,
        )
        flour_n_g   = mill_out["flour_n"] * _G_PER_LB / loaves
        bakery_out  = calc_bakery_output(flour_n_g, "Baguette", DEFAULT_SPOILAGE_WASTE_PCT)

        return build_pipeline_df(
            n_application_lbs_acre=_BASELINE_N_APP,
            grain_n_uptake_lbs_acre=_BASELINE_UPTAKE,
            farm_nue_pct=_BASELINE_NUE,
            farm_data_score=AUDIT_MED_SCORE,
            flour_n_lbs_acre=mill_out["flour_n"],
            bran_n_lbs_acre=mill_out["bran_n"],
            mill_nue_pct=mill_out["mill_nue"],
            mill_data_score=AUDIT_MED_SCORE,
            flour_n_g_per_loaf=flour_n_g,
            bakery_result=bakery_out,
            bakery_data_score=AUDIT_MED_SCORE,
            loaves_per_acre=loaves,
        )

    def test_returns_polars_dataframe(self, pipeline_df):
        assert isinstance(pipeline_df, pl.DataFrame)

    def test_has_exactly_three_rows(self, pipeline_df):
        assert pipeline_df.shape[0] == 3

    def test_has_all_required_columns(self, pipeline_df):
        assert set(pipeline_df.columns) == set(PIPELINE_SCHEMA.keys())

    def test_column_dtypes_match_schema(self, pipeline_df):
        for col, expected_dtype in PIPELINE_SCHEMA.items():
            assert pipeline_df[col].dtype == expected_dtype, (
                f"Column '{col}': expected {expected_dtype}, got {pipeline_df[col].dtype}"
            )

    def test_segment_names_are_correct(self, pipeline_df):
        assert pipeline_df["segment"].to_list() == ["Farm", "Mill", "Bakery & Retail"]

    def test_n_loss_equals_n_in_minus_n_out(self, pipeline_df):
        for row in pipeline_df.iter_rows(named=True):
            computed_loss = row["n_in_g"] - row["n_out_g"]
            assert math.isclose(row["n_loss_g"], computed_loss, rel_tol=1e-9), (
                f"n_loss mismatch in segment '{row['segment']}'"
            )

    def test_nue_values_are_positive(self, pipeline_df):
        for nue in pipeline_df["nue_pct"].to_list():
            assert nue > 0.0

    def test_data_labels_are_nonempty_strings(self, pipeline_df):
        for label in pipeline_df["data_label"].to_list():
            assert isinstance(label, str) and len(label) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# ECONOMIC ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalcEconomicReturn:
    """Tests for the calc_economic_return economic optimization function."""

    def _default_result(self):
        return calc_economic_return(
            yield_bu=DEFAULT_YIELD_POTENTIAL_BU_ACRE,
            price_per_bu=DEFAULT_WHEAT_PRICE_PER_BU,
            n_applied_lbs=DEFAULT_FARM_FERTILIZER_APPLIED,
            cost_per_ton_fertilizer=DEFAULT_FERTILIZER_PRICE_PER_TON,
        )

    def test_returns_required_keys(self):
        result = self._default_result()
        assert {"gross_revenue", "fertilizer_cost", "net_margin", "cost_per_lb_n"} == set(result.keys())

    def test_gross_revenue_formula(self):
        result = self._default_result()
        expected = DEFAULT_YIELD_POTENTIAL_BU_ACRE * DEFAULT_WHEAT_PRICE_PER_BU
        assert result["gross_revenue"] == approx(expected)

    def test_cost_per_lb_n_conversion(self):
        # (cost_per_ton / 2000) / 0.46
        result = self._default_result()
        expected_cost_per_lb = (DEFAULT_FERTILIZER_PRICE_PER_TON / _LBS_PER_TON) / _UREA_N_FRACTION
        assert result["cost_per_lb_n"] == approx(expected_cost_per_lb)

    def test_fertilizer_cost_formula(self):
        result = self._default_result()
        expected_cost_per_lb = (DEFAULT_FERTILIZER_PRICE_PER_TON / _LBS_PER_TON) / _UREA_N_FRACTION
        expected = DEFAULT_FARM_FERTILIZER_APPLIED * expected_cost_per_lb
        assert result["fertilizer_cost"] == approx(expected)

    def test_net_margin_is_revenue_minus_cost(self):
        result = self._default_result()
        assert result["net_margin"] == approx(result["gross_revenue"] - result["fertilizer_cost"])

    def test_default_scenario_values(self):
        # 72 bu × $7.50/bu = $540.00 gross
        # ($600/2000)/0.46 ≈ $0.6522/lb N  →  104 × $0.6522 ≈ $67.83 fert cost
        # net ≈ $472.17
        result = self._default_result()
        assert result["gross_revenue"]   == approx(540.0)
        assert result["fertilizer_cost"] == approx(104.0 * (600.0 / 2000.0) / 0.46)
        assert result["net_margin"]      > 0.0

    def test_higher_price_increases_margin(self):
        low  = calc_economic_return(72.0, 5.0,  104.0, 600.0)
        high = calc_economic_return(72.0, 10.0, 104.0, 600.0)
        assert high["net_margin"] > low["net_margin"]

    def test_higher_fertilizer_cost_reduces_margin(self):
        cheap = calc_economic_return(72.0, 7.50, 104.0, 400.0)
        dear  = calc_economic_return(72.0, 7.50, 104.0, 900.0)
        assert cheap["net_margin"] > dear["net_margin"]

    def test_zero_yield_gives_zero_gross_revenue(self):
        result = calc_economic_return(0.0, 7.50, 104.0, 600.0)
        assert result["gross_revenue"] == approx(0.0)


# ═══════════════════════════════════════════════════════════════════════════════
# BAKERY REFERENCE BENCHMARK (new fields added to calc_bakery_output)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBakeryReferenceBenchmark:
    """Verify the PNW reference benchmark values included in bakery output."""

    def test_reference_protein_g_is_123(self):
        result = calc_bakery_output(100.0, "Baguette", DEFAULT_SPOILAGE_WASTE_PCT)
        # BREAD_PROTEIN_PER_100G × 10 = 12.3 × 10 = 123.0
        assert result["reference_protein_g"] == approx(BREAD_PROTEIN_PER_100G * 10.0)

    def test_reference_n_g_is_21_525(self):
        result = calc_bakery_output(100.0, "Baguette", DEFAULT_SPOILAGE_WASTE_PCT)
        # 123.0 × 0.175 = 21.525
        expected = BREAD_PROTEIN_PER_100G * 10.0 * N_GRAMS_PER_G_PROTEIN
        assert result["reference_n_g"] == approx(expected)

    def test_reference_values_constant_across_variants(self):
        baguette  = calc_bakery_output(100.0, "Baguette",               DEFAULT_SPOILAGE_WASTE_PCT)
        wholemeal = calc_bakery_output(100.0, "Whole Meal Sliced Loaf", DEFAULT_SPOILAGE_WASTE_PCT)
        assert baguette["reference_n_g"]       == approx(wholemeal["reference_n_g"])
        assert baguette["reference_protein_g"] == approx(wholemeal["reference_protein_g"])
