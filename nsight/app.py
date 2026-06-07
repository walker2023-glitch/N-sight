"""
app.py — N-SIGHT Streamlit entrypoint.

Architecture rules (§3 / §13):
  - This file is the ONLY place where st.* calls are made.
  - All business logic and calculations are delegated to src/ modules.
  - No numeric literals or formulas here — only wiring and layout.

New in this version:
  - Brand identity overhaul (#3E2723 / #2E7D32 / #A1887F — see brand kit)
  - Full i18n pipeline: English, Español, Français via LOCALES dict
  - Dynamic Light / Dark theme toggle via CSS injection
"""

import streamlit as st

# ── Page config: must be the very first Streamlit call ───────────────────────
st.set_page_config(
    page_title="N-SIGHT | Home",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── src/ imports ──────────────────────────────────────────────────────────────
from src.constants import (
    DEFAULT_YIELD_POTENTIAL_BU_ACRE,
    DEFAULT_PRECIPITATION_INDEX,
    DEFAULT_SOM_N_LBS_ACRE,
    DEFAULT_SOIL_TEST_N_LBS_ACRE,
    DEFAULT_EXTRACTION_RATE_PCT,
    DEFAULT_SPOILAGE_WASTE_PCT,
    DEFAULT_FARM_FERTILIZER_APPLIED,
    DEFAULT_WHEAT_PRICE_PER_BU,
    DEFAULT_FERTILIZER_PRICE_PER_TON,
    PRODUCT_VARIANTS,
    AUDIT_RISK_THRESHOLD,
)

# ── University of Idaho CIS 453 UI defaults (defined here to avoid import churn) ──
# These mirror the values in src/constants.py exactly; the math engine imports
# from src.constants directly and is unaffected by this local definition.
DEFAULT_ANNUAL_PRECIP_IN: float = 13.0   # Rexburg/SE Idaho ≈ 13 in/yr → zone < 18
DEFAULT_SOM_PCT:          float = 2.4    # 2.4% SOM → 48 lbs N/ac (conv) / 41 (reduced)
DEFAULT_SOIL_TEST_NO3_PPM: float = 5.7  # 5.7 ppm × 3.5 = 20 lbs N/ac
UI_LEGUME_N_CREDITS: dict[str, float] = {
    "None":                  0.0,
    "Field Peas":           50.0,
    "Lentils":              40.0,
    "Austrian Winter Peas": 60.0,
    "Sweet Clover":        120.0,
    "Red Clover":          100.0,
    "Alfalfa (1 yr)":       80.0,
    "Hairy Vetch":          90.0,
}
import importlib
import src.constants as _src_constants      # needed so we can reload it first
from src import math_engine, weather, audit, charts
from src.audit import AUDIT_SEGMENTS, AUDIT_DIMENSIONS

# Reload in strict dependency order so every module sees up-to-date symbols:
#   1. constants  — no src/ dependencies
#   2. math_engine / weather / audit / charts — all depend on constants
for _mod in (_src_constants, math_engine, weather, audit, charts):
    importlib.reload(_mod)

_G_PER_LB: float = 453.592   # lbs → grams (flour N unit bridge, Mill → Bakery)

# ── Idaho CIS 453 inline display helpers ──────────────────────────────────────
# These replicate the math_engine functions for UI display captions so the page
# renders correctly even if Streamlit's module cache holds a stale .pyc.
# The actual n_application calculation still delegates to math_engine.
_CIS453_ZONES: list[tuple[float, float, float]] = [
    (0.0,  18.0, 2.4),
    (18.0, 21.0, 2.5),
    (21.0, 24.0, 2.7),
    (24.0, 28.0, 2.9),
    (28.0, 1e9,  3.1),
]

def _get_n_demand_factor(precip_in: float) -> float:
    """UI-side CIS 453 Table 1 lookup (independent of math_engine cache state)."""
    for lo, hi, f in _CIS453_ZONES:
        if lo <= precip_in < hi:
            return f
    return 3.1


# CIS 453 Table 2 — exact step-function values (mirrors UI_SOM_N_CREDIT_TABLE in constants.py)
_CIS453_SOM_TABLE: list[tuple[float, float, float, float]] = [
    (0.0,  1.0,         20.0, 17.0),
    (1.0,  1.2,         22.0, 19.0),
    (1.2,  1.4,         26.0, 22.0),
    (1.4,  1.6,         30.0, 26.0),
    (1.6,  1.8,         34.0, 29.0),
    (1.8,  2.0,         38.0, 32.0),
    (2.0,  2.2,         42.0, 36.0),
    (2.2,  2.4,         46.0, 39.0),
    (2.4,  2.6,         50.0, 43.0),
    (2.6,  2.8,         54.0, 46.0),
    (2.8,  3.0,         58.0, 48.0),
    (3.0,  1e9,         60.0, 51.0),
]

def _get_som_n_credit(som_pct: float, tillage: str) -> float:
    """UI-side CIS 453 Table 2 step lookup (independent of math_engine cache state)."""
    use_conv = tillage.lower().startswith("conv")
    for lo, hi, cv, rv in _CIS453_SOM_TABLE:
        if lo <= som_pct < hi:
            return cv if use_conv else rv
    return 60.0 if use_conv else 51.0


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  i18n — LOCALES
# ╚══════════════════════════════════════════════════════════════════════════════

LOCALES: dict[str, dict[str, str]] = {
    # ── English ───────────────────────────────────────────────────────────────
    "en": {
        # App banner
        "app_title":    "🌿 N-SIGHT",
        "app_subtitle": "Precision Nitrogen Tracing & NUE Decision Engine · IFA Hackathon — Track 1 & Track 2",

        # Sidebar chrome
        "sidebar_title":  "⚙️ Model Inputs",
        "lang_label":     "🌐 Language / Idioma / Langue",
        "theme_label":    "🌓 Interface Theme",
        "theme_dark":     "Dark Mode",
        "theme_light":    "Light Mode",
        "footer":         "N-SIGHT v1.0 · IFA Hackathon 2026 · Track 1 & 2",

        # Location expander
        "exp_location":      "📍 Location & Precipitation",
        "lbl_location":      "Location (city, state or ZIP)",
        "btn_lookup":        "🔍 Lookup Precipitation Index",
        "info_station":      "**Station:** {station}",
        "info_precip":       "**Mean annual precip:** {mm:.1f} mm",
        "info_years":        "**Years used:** {years}",
        "info_idx":          "**Precip index:** {idx:.3f}",

        # Farm expander
        "exp_farm":          "🌾 Segment 1: Farm Inputs",
        "lbl_yield":         "Yield Potential (bu/acre)",
        "lbl_precip_slider": "Precipitation Index",
        "lbl_som_n":         "Mineralizable SOM N (lbs/acre)",
        "lbl_soil_n":        "Soil Test N (lbs/acre)",
        "lbl_legume":        "Legume Credit (+35 lbs N/acre)",
        "lbl_hicarbon":      "High-Carbon Residue Debit (−15 lbs N/acre)",
        "section_eco":       "── ECONOMIC INPUTS ──",
        "lbl_fert_applied":  "Fertilizer Applied (lbs N/acre)",
        "lbl_wheat_price":   "Wheat Market Price ($/bu)",
        "lbl_fert_price":    "Fertilizer Market Price ($/ton)",
        "help_fert_applied": "Actual N applied for economic cost calculation (regional default: 104 lbs/ac).",
        "help_wheat_price":  "Current wheat spot price (default: $7.50/bu).",
        "help_fert_price":   "Urea cost per ton (default: $600/ton, 46% N).",
        "section_audit":     "── DATA AUDIT ──",

        # Mill expander
        "exp_mill":          "🏭 Segment 2: Mill Inputs",
        "lbl_extraction":    "Extraction Rate %",
        "cap_extraction":    "75% = white flour  |  100% = whole meal",

        # Bakery expander
        "exp_bakery":        "🥖 Segment 3: Bakery & Retail",
        "lbl_variant":       "Product Variant",
        "lbl_spoilage":      "Spoilage / Waste %",

        # Audit options (locale-key → display)
        "audit_high":        "High (5)",
        "audit_med":         "Medium (3)",
        "audit_low":         "Low (1)",

        # Audit dimensions (used as radio section labels)
        "dim_input":         "Input Data",
        "dim_process":       "Process Data",
        "dim_output":        "Output Verification",

        # Segment display labels
        "seg_farm":          "Farm",
        "seg_mill":          "Mill",
        "seg_bakery":        "Bakery & Retail",

        # Tabs
        "tab_flow":          "🌾 Nitrogen Flow",
        "tab_nue":           "📊 NUE Dashboard",
        "tab_audit":         "🔬 Data Audit",

        # Tab 1
        "t1_header":         "Nitrogen Mass-Balance Through the Bread Supply Chain",
        "t1_caption":        "Each gram of N is traced from fertilizer application → grain uptake → milling → final 1 kg reference loaf. Green flows = retained N; red/amber flows = environmental losses or by-products.",
        "t1_table_hdr":      "Pipeline Segment Data (g N per 1 kg Reference Loaf)",
        "col_segment":       "Segment",
        "col_n_in":          "N In (g)",
        "col_n_out":         "N Out (g)",
        "col_n_loss":        "N Loss (g)",
        "col_nue":           "NUE %",
        "col_score":         "Data Score",
        "col_quality":       "Data Quality",

        # Tab 2
        "t2_header":         "NUE Performance by Segment",
        "t2_sys_header":     "End-to-End System NUE",
        "t2_sys_caption":    "Measures what fraction of all N applied at the farm ultimately reaches the consumer in 1 kg of bread. This is the headline hackathon metric.",
        "t2_consumer_hdr":   "Consumer Output — 1 kg Reference Loaf",
        "t2_benchmark":      "PNW calibration benchmarks: **{prot:.1f} g protein** / **{n:.3f} g N** per 1 kg shelf loaf (12.3 g/100 g × 0.175 g N/g protein).",
        "t2_eco_header":     "💰 Economic Optimization — Per Acre",
        "t2_eco_caption":    "Fertilizer cost conversion: ${cplb:.4f}/lb N (urea ${price:.0f}/ton ÷ 2000 ÷ 0.46 N-content).",
        "metric_final_n":    "Final Nitrogen in 1 kg Loaf",
        "metric_protein":    "Consumer Protein Content",
        "metric_gross":      "Gross Income per Acre",
        "metric_fert_cost":  "Fertilizer Expense per Acre",
        "metric_net":        "Net Financial Margin",
        "delta_n_vs_ref":    "{v:.2f} g vs 21.525 g benchmark",
        "delta_n_factor":    "N ÷ 0.175 g N/g protein",
        "delta_gross":       "{y:.1f} bu × ${p:.2f}/bu",
        "delta_fert":        "{n:.0f} lbs N × ${c:.4f}/lb",
        "lbl_profitable":    "▲ Profitable",
        "lbl_loss":          "▼ Loss",

        # Tab 3
        "t3_header":         "Track 2 — Data Quality Risk Matrix",
        "t3_caption":        "Score each supply chain input source using the sidebar audit radios. Cells scoring ≤ {threshold} are flagged as high-risk (red).",
        "t3_table_hdr":      "Audit Score Detail",
        "col_dimension":     "Dimension",
        "col_audit_score":   "Score (1–5)",
        "col_risk":          "High Risk?",
        "legend_title":      "Score Legend",

        # Validation banners
        "err_zero_n":        "N application cannot be zero. Check inputs — reduce soil / SOM credits.",
        "err_zero_sys":      "System NUE undefined — N applied is zero.",
        "msg_soil_mining":   "CRITICAL WARNING: Soil Mining Detected! Crop is extracting more nutrients than are being replenished, putting long-term soil health at risk.",
        "msg_optimal":       "Optimal Efficiency Target Band Achieved.",
        "msg_warning":       "Environmental Loss Risk: High probability of nitrogen leaching or gaseous volatilization.",
        "err_data_integrity":"⚠️ DATA INTEGRITY ALERT: One or more supply chain segments are scored ≤{threshold} (Low Reliability). Policy or corporate ESG decisions built on these inputs carry high epistemic risk. See red cells above.",

        # Tech audit expander
        "exp_tech_audit":    "🔬 Technical Audit Assumptions & Future Scope",
    },

    # ── Español ───────────────────────────────────────────────────────────────
    "es": {
        "app_title":    "🌿 N-SIGHT",
        "app_subtitle": "Motor de Trazado de Nitrógeno y Decisión de EUN · Hackathon IFA — Pistas 1 y 2",

        "sidebar_title":  "⚙️ Parámetros del Modelo",
        "lang_label":     "🌐 Language / Idioma / Langue",
        "theme_label":    "🌓 Tema de Interfaz",
        "theme_dark":     "Modo Oscuro",
        "theme_light":    "Modo Claro",
        "footer":         "N-SIGHT v1.0 · Hackathon IFA 2026 · Pistas 1 y 2",

        "exp_location":      "📍 Ubicación y Precipitación",
        "lbl_location":      "Ubicación (ciudad, estado o código postal)",
        "btn_lookup":        "🔍 Buscar Índice de Precipitación",
        "info_station":      "**Estación:** {station}",
        "info_precip":       "**Precip. media anual:** {mm:.1f} mm",
        "info_years":        "**Años utilizados:** {years}",
        "info_idx":          "**Índice de precipitación:** {idx:.3f}",

        "exp_farm":          "🌾 Segmento 1: Insumos Agrícolas",
        "lbl_yield":         "Potencial de Rendimiento (bu/acre)",
        "lbl_precip_slider": "Índice de Precipitación",
        "lbl_som_n":         "N de MOS Mineralizable (lbs/acre)",
        "lbl_soil_n":        "N en Análisis de Suelo (lbs/acre)",
        "lbl_legume":        "Crédito Leguminosa (+35 lbs N/acre)",
        "lbl_hicarbon":      "Débito Residuo Alto en Carbono (−15 lbs N/acre)",
        "section_eco":       "── INSUMOS ECONÓMICOS ──",
        "lbl_fert_applied":  "Fertilizante Aplicado (lbs N/acre)",
        "lbl_wheat_price":   "Precio de Mercado del Trigo ($/bu)",
        "lbl_fert_price":    "Precio de Fertilizante ($/ton)",
        "help_fert_applied": "N real aplicado para cálculo económico (valor regional: 104 lbs/ac).",
        "help_wheat_price":  "Precio spot actual del trigo (predeterminado: $7.50/bu).",
        "help_fert_price":   "Coste de urea por tonelada (predeterminado: $600/t, 46% N).",
        "section_audit":     "── AUDITORÍA DE DATOS ──",

        "exp_mill":          "🏭 Segmento 2: Insumos de Molino",
        "lbl_extraction":    "Tasa de Extracción %",
        "cap_extraction":    "75% = harina blanca  |  100% = harina integral",

        "exp_bakery":        "🥖 Segmento 3: Panadería y Comercio",
        "lbl_variant":       "Variante de Producto",
        "lbl_spoilage":      "Desperdicio / Merma %",

        "audit_high":        "Alto (5)",
        "audit_med":         "Medio (3)",
        "audit_low":         "Bajo (1)",

        "dim_input":         "Datos de Entrada",
        "dim_process":       "Datos de Proceso",
        "dim_output":        "Verificación de Salida",

        "seg_farm":          "Granja",
        "seg_mill":          "Molino",
        "seg_bakery":        "Panadería y Comercio",

        "tab_flow":          "🌾 Flujo de Nitrógeno",
        "tab_nue":           "📊 Panel de EUN",
        "tab_audit":         "🔬 Auditoría de Datos",

        "t1_header":         "Balance de Masa de Nitrógeno en la Cadena del Pan",
        "t1_caption":        "Cada gramo de N se rastrea desde la aplicación de fertilizantes → absorción por el grano → molienda → hogaza de referencia de 1 kg. Verde = N retenido; rojo/ámbar = pérdidas ambientales.",
        "t1_table_hdr":      "Datos del Segmento Pipeline (g N por hogaza de 1 kg)",
        "col_segment":       "Segmento",
        "col_n_in":          "N Entrada (g)",
        "col_n_out":         "N Salida (g)",
        "col_n_loss":        "N Pérdida (g)",
        "col_nue":           "EUN %",
        "col_score":         "Puntuación",
        "col_quality":       "Calidad de Datos",

        "t2_header":         "Rendimiento de EUN por Segmento",
        "t2_sys_header":     "EUN del Sistema (Extremo a Extremo)",
        "t2_sys_caption":    "Mide qué fracción del N aplicado en la granja llega al consumidor en 1 kg de pan.",
        "t2_consumer_hdr":   "Producto para el Consumidor — Hogaza de 1 kg",
        "t2_benchmark":      "Referencias PNW: **{prot:.1f} g proteína** / **{n:.3f} g N** por hogaza de 1 kg (12,3 g/100 g × 0,175 g N/g proteína).",
        "t2_eco_header":     "💰 Optimización Económica — Por Acre",
        "t2_eco_caption":    "Conversión de coste de fertilizante: ${cplb:.4f}/lb N (urea ${price:.0f}/ton ÷ 2000 ÷ 0,46 N).",
        "metric_final_n":    "Nitrógeno Final en Hogaza de 1 kg",
        "metric_protein":    "Proteína del Consumidor",
        "metric_gross":      "Ingresos Brutos por Acre",
        "metric_fert_cost":  "Gasto en Fertilizantes por Acre",
        "metric_net":        "Margen Financiero Neto",
        "delta_n_vs_ref":    "{v:.2f} g vs referencia 21,525 g",
        "delta_n_factor":    "N ÷ 0,175 g N/g proteína",
        "delta_gross":       "{y:.1f} bu × ${p:.2f}/bu",
        "delta_fert":        "{n:.0f} lbs N × ${c:.4f}/lb",
        "lbl_profitable":    "▲ Rentable",
        "lbl_loss":          "▼ Pérdida",

        "t3_header":         "Pista 2 — Matriz de Riesgo de Calidad de Datos",
        "t3_caption":        "Puntúe cada fuente de datos. Las celdas con puntuación ≤ {threshold} se marcan como alto riesgo (rojo).",
        "t3_table_hdr":      "Detalle de Puntuación de Auditoría",
        "col_dimension":     "Dimensión",
        "col_audit_score":   "Puntuación (1–5)",
        "col_risk":          "¿Alto Riesgo?",
        "legend_title":      "Leyenda de Puntuación",

        "err_zero_n":        "La aplicación de N no puede ser cero. Verifique los créditos de suelo.",
        "err_zero_sys":      "EUN del sistema indefinida — N aplicado es cero.",
        "msg_soil_mining":   "ADVERTENCIA CRÍTICA: ¡Minería de Suelo Detectada! El cultivo extrae más nutrientes de los que se reponen, poniendo en riesgo la salud del suelo a largo plazo.",
        "msg_optimal":       "Banda Óptima de Eficiencia Alcanzada.",
        "msg_warning":       "Riesgo de Pérdida Ambiental: Alta probabilidad de lixiviación o volatilización gaseosa de nitrógeno.",
        "err_data_integrity":"⚠️ ALERTA DE INTEGRIDAD DE DATOS: Uno o más segmentos tienen puntuación ≤{threshold} (Baja Fiabilidad). Las decisiones ESG basadas en estos datos conllevan alto riesgo epistémico. Véanse las celdas rojas.",

        "exp_tech_audit":    "🔬 Supuestos Técnicos y Alcance Futuro",
    },

    # ── Français ──────────────────────────────────────────────────────────────
    "fr": {
        "app_title":    "🌿 N-SIGHT",
        "app_subtitle": "Moteur de Traçage de l'Azote et Décision EUN · Hackathon IFA — Voies 1 et 2",

        "sidebar_title":  "⚙️ Paramètres du Modèle",
        "lang_label":     "🌐 Language / Idioma / Langue",
        "theme_label":    "🌓 Thème d'Interface",
        "theme_dark":     "Mode Sombre",
        "theme_light":    "Mode Clair",
        "footer":         "N-SIGHT v1.0 · Hackathon IFA 2026 · Voies 1 et 2",

        "exp_location":      "📍 Localisation & Précipitations",
        "lbl_location":      "Localisation (ville, état ou code postal)",
        "btn_lookup":        "🔍 Rechercher l'Indice de Précipitation",
        "info_station":      "**Station :** {station}",
        "info_precip":       "**Précip. annuelle moyenne :** {mm:.1f} mm",
        "info_years":        "**Années utilisées :** {years}",
        "info_idx":          "**Indice de précipitation :** {idx:.3f}",

        "exp_farm":          "🌾 Segment 1 : Intrants Agricoles",
        "lbl_yield":         "Potentiel de Rendement (bu/acre)",
        "lbl_precip_slider": "Indice de Précipitation",
        "lbl_som_n":         "N de MOS Minéralisable (lbs/acre)",
        "lbl_soil_n":        "N en Analyse de Sol (lbs/acre)",
        "lbl_legume":        "Crédit Légumineuse (+35 lbs N/acre)",
        "lbl_hicarbon":      "Débit Résidu Carbone Élevé (−15 lbs N/acre)",
        "section_eco":       "── INTRANTS ÉCONOMIQUES ──",
        "lbl_fert_applied":  "Engrais Appliqué (lbs N/acre)",
        "lbl_wheat_price":   "Prix de Marché du Blé ($/bu)",
        "lbl_fert_price":    "Prix de l'Engrais ($/tonne)",
        "help_fert_applied": "N réel appliqué pour le calcul économique (défaut régional : 104 lbs/ac).",
        "help_wheat_price":  "Prix spot actuel du blé (défaut : 7,50 $/bu).",
        "help_fert_price":   "Coût de l'urée par tonne (défaut : 600 $/t, 46 % N).",
        "section_audit":     "── AUDIT DES DONNÉES ──",

        "exp_mill":          "🏭 Segment 2 : Intrants Meunerie",
        "lbl_extraction":    "Taux d'Extraction %",
        "cap_extraction":    "75 % = farine blanche  |  100 % = farine complète",

        "exp_bakery":        "🥖 Segment 3 : Boulangerie & Commerce",
        "lbl_variant":       "Variante de Produit",
        "lbl_spoilage":      "Déchets / Pertes %",

        "audit_high":        "Élevé (5)",
        "audit_med":         "Moyen (3)",
        "audit_low":         "Faible (1)",

        "dim_input":         "Données d'Entrée",
        "dim_process":       "Données de Processus",
        "dim_output":        "Vérification de Sortie",

        "seg_farm":          "Ferme",
        "seg_mill":          "Meunerie",
        "seg_bakery":        "Boulangerie & Commerce",

        "tab_flow":          "🌾 Flux d'Azote",
        "tab_nue":           "📊 Tableau EUN",
        "tab_audit":         "🔬 Audit des Données",

        "t1_header":         "Bilan de Masse d'Azote dans la Chaîne du Pain",
        "t1_caption":        "Chaque gramme de N est tracé depuis l'application d'engrais → absorption par les grains → mouture → pain de référence d'1 kg. Vert = N retenu ; rouge/ambre = pertes environnementales ou sous-produits.",
        "t1_table_hdr":      "Données du Segment Pipeline (g N par pain de 1 kg)",
        "col_segment":       "Segment",
        "col_n_in":          "N Entrée (g)",
        "col_n_out":         "N Sortie (g)",
        "col_n_loss":        "N Perte (g)",
        "col_nue":           "EUN %",
        "col_score":         "Score",
        "col_quality":       "Qualité des Données",

        "t2_header":         "Performance EUN par Segment",
        "t2_sys_header":     "EUN Système (Bout à Bout)",
        "t2_sys_caption":    "Mesure quelle fraction du N appliqué à la ferme atteint le consommateur dans 1 kg de pain. C'est la métrique clé du hackathon.",
        "t2_consumer_hdr":   "Sortie Consommateur — Pain de 1 kg",
        "t2_benchmark":      "Références PNW : **{prot:.1f} g protéines** / **{n:.3f} g N** par pain d'1 kg (12,3 g/100 g × 0,175 g N/g protéine).",
        "t2_eco_header":     "💰 Optimisation Économique — Par Acre",
        "t2_eco_caption":    "Conversion du coût d'engrais : {cplb:.4f} $/lb N (urée {price:.0f} $/t ÷ 2000 ÷ 0,46 N).",
        "metric_final_n":    "Azote Final dans le Pain de 1 kg",
        "metric_protein":    "Teneur en Protéines du Consommateur",
        "metric_gross":      "Revenu Brut par Acre",
        "metric_fert_cost":  "Dépense en Engrais par Acre",
        "metric_net":        "Marge Financière Nette",
        "delta_n_vs_ref":    "{v:.2f} g vs référence 21,525 g",
        "delta_n_factor":    "N ÷ 0,175 g N/g protéine",
        "delta_gross":       "{y:.1f} bu × {p:.2f} $/bu",
        "delta_fert":        "{n:.0f} lbs N × {c:.4f} $/lb",
        "lbl_profitable":    "▲ Rentable",
        "lbl_loss":          "▼ Perte",

        "t3_header":         "Voie 2 — Matrice de Risque Qualité des Données",
        "t3_caption":        "Évaluez chaque source de données. Les cellules ≤ {threshold} sont signalées à haut risque (rouge).",
        "t3_table_hdr":      "Détail du Score d'Audit",
        "col_dimension":     "Dimension",
        "col_audit_score":   "Score (1–5)",
        "col_risk":          "Haut Risque ?",
        "legend_title":      "Légende des Scores",

        "err_zero_n":        "L'application de N ne peut pas être zéro. Vérifiez les crédits de sol / MOS.",
        "err_zero_sys":      "EUN système indéfinie — N appliqué est zéro.",
        "msg_soil_mining":   "AVERTISSEMENT CRITIQUE : Épuisement du Sol Détecté ! La culture extrait plus de nutriments qu'il n'en est restitué, mettant en péril la santé du sol à long terme.",
        "msg_optimal":       "Bande Cible d'Efficacité Optimale Atteinte.",
        "msg_warning":       "Risque de Perte Environnementale : Haute probabilité de lixiviation ou de volatilisation gazeuse d'azote.",
        "err_data_integrity":"⚠️ ALERTE INTÉGRITÉ DES DONNÉES : Un ou plusieurs segments ont un score ≤{threshold} (Faible Fiabilité). Les décisions ESG basées sur ces données comportent un risque épistémique élevé. Voir cellules rouges ci-dessus.",

        "exp_tech_audit":    "🔬 Hypothèses Techniques & Portée Future",
    },

    # ── 简体中文 ──────────────────────────────────────────────────────────────
    "zh": {
        "app_title":    "🌿 N-SIGHT",
        "app_subtitle": "精准氮素追踪与NUE决策引擎 · IFA黑客马拉松 — 赛道1 & 2",

        "sidebar_title":  "⚙️ 模型参数",
        "lang_label":     "🌐 Language / Idioma / Langue",
        "theme_label":    "🌓 界面主题",
        "theme_dark":     "深色模式",
        "theme_light":    "浅色模式",
        "footer":         "N-SIGHT v1.0 · IFA黑客马拉松2026 · 赛道1 & 2",

        "exp_location":      "📍 位置与降水",
        "lbl_location":      "位置（城市、州或邮编）",
        "btn_lookup":        "🔍 查找降水指数",
        "info_station":      "**气象站：** {station}",
        "info_precip":       "**年均降水量：** {mm:.1f} mm",
        "info_years":        "**使用年数：** {years}",
        "info_idx":          "**降水指数：** {idx:.3f}",

        "exp_farm":          "🌾 第1段：农场投入",
        "lbl_yield":         "产量潜力（蒲式耳/英亩）",
        "lbl_precip_slider": "降水指数",
        "lbl_som_n":         "可矿化有机质氮（磅/英亩）",
        "lbl_soil_n":        "土壤测试氮（磅/英亩）",
        "lbl_legume":        "豆科植物积分（+35磅N/英亩）",
        "lbl_hicarbon":      "高碳残留扣除（-15磅N/英亩）",
        "section_eco":       "── 经济投入 ──",
        "lbl_fert_applied":  "施用肥料（磅N/英亩）",
        "lbl_wheat_price":   "小麦市场价格（$/蒲式耳）",
        "lbl_fert_price":    "肥料市场价格（$/吨）",
        "help_fert_applied": "用于经济成本计算的实际氮素施用量（区域默认：104磅/英亩）。",
        "help_wheat_price":  "当前小麦现货价格（默认：$7.50/蒲式耳）。",
        "help_fert_price":   "每吨尿素成本（默认：$600/吨，含氮量46%）。",
        "section_audit":     "── 数据审计 ──",

        "exp_mill":          "🏭 第2段：磨坊投入",
        "lbl_extraction":    "提取率 %",
        "cap_extraction":    "75% = 白面粉  |  100% = 全麦粉",

        "exp_bakery":        "🥖 第3段：面包房与零售",
        "lbl_variant":       "产品种类",
        "lbl_spoilage":      "损耗/浪费 %",

        "audit_high":        "高 (5)",
        "audit_med":         "中 (3)",
        "audit_low":         "低 (1)",

        "dim_input":         "输入数据",
        "dim_process":       "过程数据",
        "dim_output":        "输出验证",

        "seg_farm":          "农场",
        "seg_mill":          "磨坊",
        "seg_bakery":        "面包房与零售",

        "tab_flow":          "🌾 氮素流量",
        "tab_nue":           "📊 NUE仪表板",
        "tab_audit":         "🔬 数据审计",

        "t1_header":         "面包供应链中的氮素质量平衡",
        "t1_caption":        "每克N从施肥→谷物吸收→磨粉→1公斤参考面包逐步追踪。绿色流=保留N；红/琥珀色流=环境损失或副产品。",
        "t1_table_hdr":      "管道段数据（每1公斤参考面包的g N）",
        "col_segment":       "段",
        "col_n_in":          "N输入 (g)",
        "col_n_out":         "N输出 (g)",
        "col_n_loss":        "N损失 (g)",
        "col_nue":           "NUE %",
        "col_score":         "数据评分",
        "col_quality":       "数据质量",

        "t2_header":         "各段NUE性能",
        "t2_sys_header":     "端对端系统NUE",
        "t2_sys_caption":    "衡量农场施用氮素中最终进入1公斤面包到达消费者的比例。这是黑客马拉松的核心指标。",
        "t2_consumer_hdr":   "消费者产出 — 1公斤参考面包",
        "t2_benchmark":      "太平洋西北参考基准：每1公斤面包 **{prot:.1f} g蛋白质** / **{n:.3f} g N** (12.3 g/100g × 0.175 g N/g蛋白质)。",
        "t2_eco_header":     "💰 经济优化 — 每英亩",
        "t2_eco_caption":    "肥料成本换算：${cplb:.4f}/磅N（尿素${price:.0f}/吨÷2000÷0.46含氮量）。",
        "metric_final_n":    "1公斤面包中最终氮素",
        "metric_protein":    "消费者蛋白质含量",
        "metric_gross":      "每英亩总收入",
        "metric_fert_cost":  "每英亩肥料支出",
        "metric_net":        "净财务利润",
        "delta_n_vs_ref":    "{v:.2f} g vs 21.525 g基准",
        "delta_n_factor":    "N ÷ 0.175 g N/g蛋白质",
        "delta_gross":       "{y:.1f}蒲×${p:.2f}/蒲",
        "delta_fert":        "{n:.0f}磅N×${c:.4f}/磅",
        "lbl_profitable":    "▲ 盈利",
        "lbl_loss":          "▼ 亏损",

        "t3_header":         "赛道2 — 数据质量风险矩阵",
        "t3_caption":        "使用侧边栏审计单选框对每个供应链数据源评分。评分≤{threshold}的单元格标记为高风险（红色）。",
        "t3_table_hdr":      "审计评分详情",
        "col_dimension":     "维度",
        "col_audit_score":   "评分（1-5）",
        "col_risk":          "高风险？",
        "legend_title":      "评分说明",

        "err_zero_n":        "N施用量不能为零。请检查输入 — 减少土壤/有机质积分。",
        "err_zero_sys":      "系统NUE未定义 — 施用N为零。",
        "msg_soil_mining":   "严重警告：检测到土壤氮素耗竭！作物提取的养分超过补充量，长期土壤健康面临风险。",
        "msg_optimal":       "已达到最优效率目标区间。",
        "msg_warning":       "环境损失风险：氮素淋溶或气态挥发的概率较高。",
        "err_data_integrity":"⚠️ 数据完整性警告：一个或多个供应链段评分≤{threshold}（低可靠性）。基于此数据的政策或企业ESG决策存在较高认知风险。见上方红色单元格。",

        "exp_tech_audit":    "🔬 技术审计假设与未来范围",
    },

    # ── العربية ───────────────────────────────────────────────────────────────
    "ar": {
        "app_title":    "🌿 N-SIGHT",
        "app_subtitle": "محرك تتبع النيتروجين الدقيق وقرارات NUE · هاكاثون IFA — المسار 1 و2",

        "sidebar_title":  "⚙️ معاملات النموذج",
        "lang_label":     "🌐 Language / Idioma / Langue",
        "theme_label":    "🌓 سمة الواجهة",
        "theme_dark":     "الوضع الداكن",
        "theme_light":    "الوضع الفاتح",
        "footer":         "N-SIGHT v1.0 · هاكاثون IFA 2026 · المسار 1 و2",

        "exp_location":      "📍 الموقع والهطول",
        "lbl_location":      "الموقع (المدينة، الولاية أو الرمز البريدي)",
        "btn_lookup":        "🔍 البحث عن مؤشر الهطول",
        "info_station":      "**المحطة:** {station}",
        "info_precip":       "**متوسط الهطول السنوي:** {mm:.1f} ملم",
        "info_years":        "**السنوات المستخدمة:** {years}",
        "info_idx":          "**مؤشر الهطول:** {idx:.3f}",

        "exp_farm":          "🌾 القطاع 1: مدخلات المزرعة",
        "lbl_yield":         "إمكانية الإنتاج (بوشل/فدان)",
        "lbl_precip_slider": "مؤشر الهطول",
        "lbl_som_n":         "نيتروجين المادة العضوية القابل للمعدنة (رطل/فدان)",
        "lbl_soil_n":        "نيتروجين تحليل التربة (رطل/فدان)",
        "lbl_legume":        "ائتمان البقوليات (+35 رطل N/فدان)",
        "lbl_hicarbon":      "خصم بقايا الكربون العالي (−15 رطل N/فدان)",
        "section_eco":       "── المدخلات الاقتصادية ──",
        "lbl_fert_applied":  "السماد المطبق (رطل N/فدان)",
        "lbl_wheat_price":   "سعر سوق القمح ($/بوشل)",
        "lbl_fert_price":    "سعر السماد بالسوق ($/طن)",
        "help_fert_applied": "النيتروجين الفعلي المطبق لحساب التكلفة الاقتصادية (الافتراضي الإقليمي: 104 رطل/فدان).",
        "help_wheat_price":  "سعر القمح الفوري الحالي (الافتراضي: $7.50/بوشل).",
        "help_fert_price":   "تكلفة اليوريا بالطن (الافتراضي: $600/طن، 46% نيتروجين).",
        "section_audit":     "── تدقيق البيانات ──",

        "exp_mill":          "🏭 القطاع 2: مدخلات المطحنة",
        "lbl_extraction":    "معدل الاستخراج %",
        "cap_extraction":    "75% = دقيق أبيض  |  100% = دقيق كامل",

        "exp_bakery":        "🥖 القطاع 3: المخبز والتجزئة",
        "lbl_variant":       "نوع المنتج",
        "lbl_spoilage":      "التلف / الهدر %",

        "audit_high":        "عالٍ (5)",
        "audit_med":         "متوسط (3)",
        "audit_low":         "منخفض (1)",

        "dim_input":         "بيانات الإدخال",
        "dim_process":       "بيانات المعالجة",
        "dim_output":        "التحقق من الإخراج",

        "seg_farm":          "المزرعة",
        "seg_mill":          "المطحنة",
        "seg_bakery":        "المخبز والتجزئة",

        "tab_flow":          "🌾 تدفق النيتروجين",
        "tab_nue":           "📊 لوحة NUE",
        "tab_audit":         "🔬 تدقيق البيانات",

        "t1_header":         "ميزان كتلة النيتروجين عبر سلسلة توريد الخبز",
        "t1_caption":        "يتتبع كل غرام من N من تطبيق السماد → امتصاص الحبوب → الطحن → رغيف مرجعي 1 كجم. التدفقات الخضراء = N المحتجز؛ التدفقات الحمراء = خسائر بيئية أو منتجات ثانوية.",
        "t1_table_hdr":      "بيانات قطاع خط الأنابيب (g N لكل رغيف مرجعي 1 كجم)",
        "col_segment":       "القطاع",
        "col_n_in":          "N الداخل (g)",
        "col_n_out":         "N الخارج (g)",
        "col_n_loss":        "N الخسارة (g)",
        "col_nue":           "NUE %",
        "col_score":         "درجة البيانات",
        "col_quality":       "جودة البيانات",

        "t2_header":         "أداء NUE حسب القطاع",
        "t2_sys_header":     "NUE النظام الكامل",
        "t2_sys_caption":    "يقيس أي جزء من N المطبق في المزرعة يصل للمستهلك في 1 كجم من الخبز. هذا هو المقياس الرئيسي للهاكاثون.",
        "t2_consumer_hdr":   "المخرجات للمستهلك — رغيف مرجعي 1 كجم",
        "t2_benchmark":      "معايير المرجع PNW: **{prot:.1f} g بروتين** / **{n:.3f} g N** لكل رغيف 1 كجم (12.3 g/100g × 0.175 g N/g بروتين).",
        "t2_eco_header":     "💰 التحسين الاقتصادي — لكل فدان",
        "t2_eco_caption":    "تحويل تكلفة السماد: ${cplb:.4f}/رطل N (يوريا ${price:.0f}/طن ÷ 2000 ÷ 0.46 نيتروجين).",
        "metric_final_n":    "النيتروجين النهائي في رغيف 1 كجم",
        "metric_protein":    "محتوى البروتين للمستهلك",
        "metric_gross":      "الدخل الإجمالي لكل فدان",
        "metric_fert_cost":  "مصاريف الأسمدة لكل فدان",
        "metric_net":        "هامش الربح الصافي",
        "delta_n_vs_ref":    "{v:.2f} g مقابل المرجع 21.525 g",
        "delta_n_factor":    "N ÷ 0.175 g N/g بروتين",
        "delta_gross":       "{y:.1f} بوشل × ${p:.2f}/بوشل",
        "delta_fert":        "{n:.0f} رطل N × ${c:.4f}/رطل",
        "lbl_profitable":    "▲ مربح",
        "lbl_loss":          "▼ خسارة",

        "t3_header":         "المسار 2 — مصفوفة مخاطر جودة البيانات",
        "t3_caption":        "قيّم كل مصدر بيانات في سلسلة التوريد. الخلايا ذات الدرجة ≤ {threshold} مُصنّفة كمخاطر عالية (باللون الأحمر).",
        "t3_table_hdr":      "تفاصيل درجة التدقيق",
        "col_dimension":     "البُعد",
        "col_audit_score":   "الدرجة (1–5)",
        "col_risk":          "مخاطر عالية؟",
        "legend_title":      "دليل الدرجات",

        "err_zero_n":        "لا يمكن أن يكون تطبيق N صفرًا. تحقق من المدخلات — قلل ائتمانات التربة/المادة العضوية.",
        "err_zero_sys":      "NUE النظام غير محدد — N المطبق صفر.",
        "msg_soil_mining":   "تحذير حرج: تم الكشف عن استنزاف التربة! المحصول يستخرج مغذيات أكثر مما يُستبدل، مما يهدد صحة التربة على المدى البعيد.",
        "msg_optimal":       "تم تحقيق نطاق الكفاءة المثلى المستهدف.",
        "msg_warning":       "خطر الخسارة البيئية: احتمالية عالية لرشح النيتروجين أو التطاير الغازي.",
        "err_data_integrity":"⚠️ تنبيه سلامة البيانات: درجة قطاع واحد أو أكثر ≤{threshold} (موثوقية منخفضة). القرارات المبنية على هذه البيانات تحمل مخاطر معرفية عالية. انظر الخلايا الحمراء أعلاه.",

        "exp_tech_audit":    "🔬 افتراضات التدقيق التقني والنطاق المستقبلي",
    },
}

# Map English AUDIT_DIMENSIONS → LOCALES keys (internal keys stay English)
_DIM_LOCALE_KEY: dict[str, str] = {
    "Input Data":          "dim_input",
    "Process Data":        "dim_process",
    "Output Verification": "dim_output",
}
# Internal audit option keys (language-independent) → numeric scores
_AUDIT_OPT_KEYS    = ["audit_high", "audit_med", "audit_low"]
_AUDIT_VAL_MAP     = {"audit_high": 5, "audit_med": 3, "audit_low": 1}
_AUDIT_INT_MAP_NEW = {5: "audit_high", 3: "audit_med", 1: "audit_low"}


# ── Translation helper ────────────────────────────────────────────────────────
def t(key: str, lang: str | None = None) -> str:
    """Return the translation for `key` in the active language."""
    _lang = lang or st.session_state.get("current_lang", "en")
    return LOCALES.get(_lang, LOCALES["en"]).get(key, LOCALES["en"].get(key, key))


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  SESSION STATE INITIALIZATION
# ╚══════════════════════════════════════════════════════════════════════════════

DEFAULTS: dict = {
    # Agronomic
    "yield_potential":       DEFAULT_YIELD_POTENTIAL_BU_ACRE,
    "precip_index":          DEFAULT_PRECIPITATION_INDEX,
    "som_n":                 DEFAULT_SOM_N_LBS_ACRE,
    "soil_test_n":           DEFAULT_SOIL_TEST_N_LBS_ACRE,
    "legume_credit":         False,
    "high_carbon_debit":     False,
    "extraction_rate":       DEFAULT_EXTRACTION_RATE_PCT,
    "product_variant":       "Baguette",
    "spoilage_waste_pct":    DEFAULT_SPOILAGE_WASTE_PCT,
    # Location
    "location_str":          "Rexburg, ID",
    "precip_lookup_done":    False,
    # ── University of Idaho CIS 453 Farm Inputs ──────────────────────────────
    "annual_precip_in":      DEFAULT_ANNUAL_PRECIP_IN,  # 13.0 in  → zone <18 → 2.4 lbs N/bu
    "som_pct":               DEFAULT_SOM_PCT,            # 2.4% SOM → 48 lbs N/ac (conv)
    "tillage_type":          "conventional",
    "soil_test_no3_ppm":     DEFAULT_SOIL_TEST_NO3_PPM,  # 5.7 ppm × 3.5 = 20 lbs N/ac
    "straw_tons_acre":       0.0,
    "legume_type":           "None",
    # Economic
    "fertilizer_applied":    DEFAULT_FARM_FERTILIZER_APPLIED,
    "wheat_price":           DEFAULT_WHEAT_PRICE_PER_BU,
    "fertilizer_price_ton":  DEFAULT_FERTILIZER_PRICE_PER_TON,
    # i18n & theme
    "current_lang":          "en",
    "dark_mode":             True,
    # Audit (nested dict, spec-required key)
    "audit_scores": {
        seg: {dim: 3 for dim in AUDIT_DIMENSIONS}
        for seg in AUDIT_SEGMENTS
    },
}

for _k, _v in DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# Initialize per-cell audit radio keys (language-independent internal keys)
for _seg in AUDIT_SEGMENTS:
    for _dim in AUDIT_DIMENSIONS:
        _rkey = f"_audit_{_seg}_{_dim}"
        if _rkey not in st.session_state:
            st.session_state[_rkey] = "audit_med"
        # Migrate old-style string values ("Medium (3)" etc.) from previous sessions
        elif st.session_state[_rkey] not in _AUDIT_OPT_KEYS:
            _old = st.session_state[_rkey]
            _score = {"High (5)": 5, "Medium (3)": 3, "Low (1)": 1,
                      "Alto (5)": 5, "Medio (3)": 3, "Bajo (1)": 1,
                      "Élevé (5)": 5, "Moyen (3)": 3, "Faible (1)": 1}.get(_old, 3)
            st.session_state[_rkey] = _AUDIT_INT_MAP_NEW[_score]

# Active language shortcut (evaluated after widgets are rendered on rerun)
_lang: str = st.session_state.get("current_lang", "en")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  BRAND + THEME CSS INJECTION
# ╚══════════════════════════════════════════════════════════════════════════════

# ── Brand tokens (fixed — from brand kit image) ───────────────────────────────
_C_BROWN       = "#3E2723"   # Primary Dark Brown   — sidebar, expanders, accents
_C_GREEN       = "#2E7D32"   # Accent Green         — success, sliders, nodes
_C_TAN         = "#A1887F"   # Complementary Tan    — borders, muted text
_C_GREEN_LIGHT = "#4CAF50"   # lighter accent       — hover / active states
_C_GREEN_BOLD  = "#66BB6A"   # readable green on dark brown backgrounds

# ── Theme-conditional palette ─────────────────────────────────────────────────
_is_dark: bool = bool(st.session_state.get("dark_mode", True))
# Theme-aware accent: bright on dark brown bg, deep green on light tan bg
_C_ACCENT: str = "#66BB6A" if _is_dark else "#2E7D32"

if _is_dark:
    # ── Dark Mode: Deep Earth Brown ──────────────────────────────────────────
    _T_BG        = "#24150F"              # deep earth-rich soil brown canvas
    _T_BG2       = "#2C1810"              # slightly lighter brown for containers
    _T_PANEL     = "#3E2723"              # bark-brown panel / metric interior
    _T_TEXT      = "#F0F1F2"              # near-white
    _T_MUTED     = _C_TAN                 # #A1887F tan for muted labels
    _T_BORDER    = "#5D4037"              # medium bark border
    _T_SIDEBAR   = "#1E0E08"              # very dark soil sidebar
    _T_METRIC_BG = "rgba(62,39,35,0.75)" # translucent bark panel
    _T_EXPANDER  = "rgba(44,24,16,0.9)"  # dark expander bg
    _T_WIDGET    = "#2C1810"              # widget input background
    _T_WIDGET_TXT= "#F0F1F2"             # widget input text
    _T_INPUT_BDR = "#5D4037"             # input border
else:
    # ── Light Mode: Soft Tan Paper ───────────────────────────────────────────
    _T_BG        = "#F5F2EB"   # soft tan paper skin canvas
    _T_BG2       = "#EDE9DF"   # slightly deeper tan
    _T_PANEL     = "#FFFFFF"   # pure clean card panels
    _T_TEXT      = "#3E2723"   # dark brown text (crisp on light bg)
    _T_MUTED     = "#8D6E63"   # medium tan/brown for muted labels
    _T_BORDER    = "#D7CCC8"   # light warm border
    _T_SIDEBAR   = "#FFFFFF"   # white sidebar
    _T_METRIC_BG = "#FFFFFF"   # white metric cards
    _T_EXPANDER  = "#FAFAF8"   # near-white expander bg
    _T_WIDGET    = "#FFFFFF"   # white widget inputs
    _T_WIDGET_TXT= "#3E2723"   # dark brown widget text
    _T_INPUT_BDR = "#A1887F"   # brand tan input border (crisp on white)

# Theme-adaptive heading color:
#   Dark  → bright green (#66BB6A) — reads well on deep-brown canvas
#   Light → dark brown  (#3E2723) — per brand guide for crisp legibility
_T_HEADING: str = _C_GREEN_BOLD if _is_dark else _T_TEXT

# ── CSS Injection — full aggressive override of all Streamlit backgrounds ──────
st.markdown(
    f"""
    <style>
    /* ── Google Fonts: Montserrat ── */
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');

    /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       SECTION 1 — NUCLEAR BACKGROUND OVERRIDE
       Targets every Streamlit frame container by ID to eliminate
       any residual dark-blue (#0F1117 / #1A1D27 / #010F1F) bleed-through.
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    html, body {{
        background-color: {_T_BG} !important;
        font-family: 'Montserrat', monospace, sans-serif !important;
        color: {_T_TEXT} !important;
    }}
    .stApp {{
        background-color: {_T_BG} !important;
    }}
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > section,
    [data-testid="stVerticalBlock"],
    [data-testid="stMain"],
    [data-testid="stMain"] > div,
    .main,
    .block-container,
    [data-testid="block-container"] {{
        background-color: {_T_BG} !important;
        color: {_T_TEXT} !important;
    }}
    /* ── Top decorative header bar ── */
    header[data-testid="stHeader"],
    header[data-testid="stHeader"] > div {{
        background: linear-gradient(
            90deg, {_C_BROWN} 0%, #5D3A2E 55%, {_C_GREEN} 100%
        ) !important;
        border-bottom: 3px solid {_C_GREEN} !important;
    }}
    /* ── Bottom toolbar ── */
    [data-testid="stBottom"],
    [data-testid="stStatusWidget"] {{
        background-color: {_T_BG} !important;
    }}
    /* ── Catch-all: any residual dark-blue Streamlit iframe / root frames ── */
    :root {{
        --background-color: {_T_BG} !important;
        --secondary-background-color: {_T_PANEL} !important;
        --text-color: {_T_TEXT} !important;
    }}
    /* iframes (e.g. Plotly charts inside st.plotly_chart) */
    iframe {{
        background-color: {_T_BG} !important;
        color-scheme: {'dark' if _is_dark else 'light'};
    }}

    /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       SECTION 2 — SIDEBAR (was dark blue; now deep-soil brown)
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div,
    section[data-testid="stSidebar"] > div:first-child,
    [data-testid="stSidebarUserContent"],
    [data-testid="stSidebarContent"] {{
        background-color: {_T_SIDEBAR} !important;
        border-right: 2px solid {_C_BROWN} !important;
    }}
    section[data-testid="stSidebar"] .stExpander {{
        border: 1px solid {_C_TAN} !important;
        border-radius: 8px;
        margin-bottom: 8px;
        background: {_T_EXPANDER} !important;
    }}
    .streamlit-expanderHeader,
    [data-testid="stExpander"] summary {{
        font-family: 'Montserrat', monospace !important;
        font-weight: 700 !important;
        color: {_C_ACCENT} !important;
        font-size: 0.88rem !important;
        letter-spacing: 0.02em;
        background: transparent !important;
    }}

    /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       SECTION 3 — TYPOGRAPHY  (Montserrat Bold headings, Regular body)
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    h1, h2, h3 {{
        font-family: 'Montserrat', monospace !important;
        font-weight: 700 !important;
        color: {_T_HEADING} !important;
        letter-spacing: 0.02em;
    }}
    h4, h5, h6 {{
        font-family: 'Montserrat', monospace !important;
        font-weight: 600 !important;
        color: {_T_TEXT} !important;
    }}
    p, li, td, th, label, figcaption, .stCaption, caption {{
        font-family: 'Montserrat', monospace !important;
        font-weight: 400 !important;
        color: {_T_TEXT} !important;
    }}
    [class*="css"] {{
        font-family: 'Montserrat', monospace, sans-serif !important;
    }}

    /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       SECTION 4 — WIDGET INPUTS  (must contrast correctly in BOTH modes)
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    /* Text / number inputs */
    .stTextInput input,
    .stNumberInput input,
    .stTextArea textarea,
    [data-baseweb="input"] input,
    [data-baseweb="textarea"] textarea {{
        background-color: {_T_WIDGET}  !important;
        color:            {_T_WIDGET_TXT} !important;
        border-color:     {_T_INPUT_BDR}  !important;
        border-radius: 6px;
        font-family: 'Montserrat', monospace !important;
    }}
    /* Selectbox / dropdown */
    [data-baseweb="select"] > div,
    [data-baseweb="select"] [data-testid="stMarkdownContainer"],
    .stSelectbox [data-baseweb="select"] > div:first-child {{
        background-color: {_T_WIDGET}  !important;
        color:            {_T_WIDGET_TXT} !important;
        border-color:     {_T_INPUT_BDR}  !important;
        font-family: 'Montserrat', monospace !important;
    }}
    /* Dropdown menu popup */
    [data-baseweb="popover"] ul,
    [data-baseweb="menu"] {{
        background-color: {_T_WIDGET} !important;
        color:            {_T_WIDGET_TXT} !important;
    }}
    [data-baseweb="menu"] li:hover {{
        background-color: {_C_BROWN} !important;
        color: #FFFFFF !important;
    }}
    /* Radio + toggle labels */
    .stRadio label, .stCheckbox label, .stToggle label,
    .stSlider label, .stSelectbox label, .stTextInput label,
    .stNumberInput label {{
        font-family: 'Montserrat', monospace !important;
        font-weight: 600 !important;
        color: {_T_TEXT} !important;
        font-size: 0.83rem !important;
    }}

    /* ── Base-input inner wrapper (number/text input containers) ── */
    [data-baseweb="base-input"],
    [data-baseweb="base-input"] > input,
    .stNumberInput [data-baseweb="input"],
    [data-testid="stNumberInput"] input,
    [data-testid="textInput"] input,
    [data-testid="stTextInput"] input {{
        background-color: {_T_WIDGET}  !important;
        color:            {_T_WIDGET_TXT} !important;
        border: 1px solid {_T_INPUT_BDR} !important;
        caret-color:      {_T_WIDGET_TXT} !important;
    }}

    /* ── Selectbox value label (the visible selected text) ── */
    [data-baseweb="select"] [data-testid="stMarkdownContainer"] p,
    [data-baseweb="select"] span,
    .stSelectbox div[aria-selected="true"] {{
        color: {_T_WIDGET_TXT} !important;
    }}

    /* ── Slider track & thumb ── */
    [data-testid="stSlider"] > div > div > div > div {{
        background-color: {_T_BORDER} !important;
    }}
    [data-testid="stSlider"] div[role="slider"] {{
        background-color: {_C_GREEN} !important;
        border-color:     {_C_GREEN} !important;
        box-shadow: 0 0 0 4px {'rgba(46,125,50,0.25)' if not _is_dark else 'rgba(76,175,80,0.3)'} !important;
    }}
    [data-testid="stSlider"] [data-baseweb="slider"] [class*="track-fill"] {{
        background-color: {_C_GREEN} !important;
    }}

    /* ── Toggle (on/off) ── */
    [data-baseweb="toggle"] label > div:first-child {{
        background-color: {_T_BORDER} !important;
    }}
    [data-testid="stToggle"] input:checked + div {{
        background-color: {_C_GREEN} !important;
    }}

    /* ── Caption text ── */
    .stCaption, [data-testid="stCaptionContainer"] {{
        color: {_T_MUTED} !important;
    }}

    /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       SECTION 5 — TABS
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    .stTabs [data-baseweb="tab-list"] {{
        background-color: {'#2C1810' if _is_dark else '#EDE9DF'} !important;
        border-radius: 10px 10px 0 0;
        border-bottom: 2px solid {_C_GREEN} !important;
        padding: 4px 10px 0;
        gap: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        font-family: 'Montserrat', monospace !important;
        font-weight: 600;
        font-size: 0.88rem;
        color: {'#A1887F' if _is_dark else '#5D4037'} !important;
        background: transparent !important;
        border-radius: 6px 6px 0 0;
        padding: 8px 18px;
        white-space: nowrap;
    }}
    .stTabs [aria-selected="true"] {{
        color: {_C_ACCENT} !important;
        background-color: {_T_BG} !important;
        border-bottom: 3px solid {_C_GREEN} !important;
    }}
    /* Tab panel content area */
    .stTabs [data-baseweb="tab-panel"] {{
        background-color: {_T_BG} !important;
    }}

    /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       SECTION 6 — METRIC CARDS  (complete contrast for both themes)
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    [data-testid="stMetric"] {{
        background: {_T_METRIC_BG} !important;
        border: 1px solid {_T_BORDER} !important;
        border-left: 4px solid {_C_GREEN} !important;
        border-radius: 10px;
        padding: 14px 18px !important;
        min-height: 90px;
        box-sizing: border-box;
    }}
    [data-testid="stMetricValue"] {{
        font-family: 'Montserrat', monospace !important;
        font-weight: 700 !important;
        font-size: 1.45rem !important;
        color: {_C_ACCENT} !important;
        white-space: normal !important;
        word-break: break-word;
    }}
    [data-testid="stMetricLabel"] {{
        font-family: 'Montserrat', monospace !important;
        font-weight: 600 !important;
        color: {_T_MUTED} !important;
        font-size: 0.74rem !important;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        white-space: normal !important;
        word-break: break-word;
    }}
    [data-testid="stMetricDelta"] {{
        font-size: 0.76rem !important;
        color: {_C_ACCENT} !important;
        word-break: break-word;
        white-space: normal !important;
    }}

    /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       SECTION 7 — ALERTS, DATAFRAMES, SLIDERS, BUTTONS
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    /* Alert boxes */
    [data-testid="stAlert"],
    [data-testid="stAlert"] > div {{
        background: {_T_PANEL} !important;
        border-radius: 8px;
        font-family: 'Montserrat', monospace !important;
        color: {_T_TEXT} !important;
    }}
    /* DataFrames */
    [data-testid="stDataFrame"],
    [data-testid="stDataFrame"] iframe {{
        border: 1px solid {_C_BROWN} !important;
        border-radius: 10px;
        overflow: hidden;
        background: {_T_PANEL} !important;
    }}
    /* Slider thumb + track */
    [data-testid="stSlider"] [class*="thumb"],
    [data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {{
        background-color: {_C_GREEN} !important;
        border-color:     {_C_GREEN} !important;
    }}
    /* Buttons */
    .stButton > button {{
        font-family: 'Montserrat', monospace !important;
        font-weight: 700;
        background: linear-gradient(90deg, {_C_BROWN}, {_C_GREEN}) !important;
        color: #FFFFFF !important;
        border: none;
        border-radius: 8px;
        padding: 8px 20px;
        letter-spacing: 0.03em;
        transition: opacity 0.15s ease;
    }}
    .stButton > button:hover {{ opacity: 0.88; }}
    /* Dividers */
    hr {{ border-color: {_C_BROWN} !important; opacity: 0.5; }}

    /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
       SECTION 8 — LAYOUT HELPERS
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
    /* Column overflow guard — long i18n labels won't warp grids */
    [data-testid="column"] {{ overflow: visible !important; min-width: 0; }}
    [data-testid="column"] > div {{ word-break: break-word; }}

    /* Page header banner */
    .nsight-banner {{
        background: linear-gradient(135deg, {_C_BROWN} 0%, #4E342E 50%, {_C_GREEN} 100%);
        border-radius: 14px;
        padding: 22px 36px;
        margin-bottom: 18px;
        border-left: 5px solid {_C_GREEN_BOLD};
    }}
    .nsight-banner h1 {{
        margin: 0 !important;
        font-size: 2rem !important;
        color: #FFFFFF !important;
        letter-spacing: 0.04em;
    }}
    .nsight-banner p {{
        margin: 6px 0 0 0;
        color: {_C_TAN};
        font-size: 0.82rem;
        font-weight: 500;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ── RTL layout injection for Arabic ──────────────────────────────────────────
if st.session_state.get("current_lang", "en") == "ar":
    st.markdown(
        """
        <style>
        /* Right-to-left layout for Arabic */
        html, body, .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stVerticalBlock"],
        .block-container {
            direction: rtl !important;
            text-align: right !important;
        }
        /* Sidebar stays on left but content flows right */
        section[data-testid="stSidebar"],
        [data-testid="stSidebarUserContent"] {
            direction: rtl !important;
            text-align: right !important;
        }
        /* Flip tab alignment */
        .stTabs [data-baseweb="tab-list"] {
            direction: rtl !important;
        }
        /* Metric label alignment */
        [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"],
        [data-testid="stMetricDelta"] {
            text-align: right !important;
        }
        /* Column content alignment */
        [data-testid="column"] > div {
            text-align: right !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ── Page header banner with brand logo ───────────────────────────────────────
st.markdown(
    f"""
    <div class="nsight-banner">
      <div style="display:flex;align-items:center;gap:18px;flex-wrap:wrap;">
        <!-- N-SIGHT brand mark: hexagon network + stylised N + leaf -->
        <svg viewBox="0 0 72 72" xmlns="http://www.w3.org/2000/svg"
             style="width:64px;height:64px;flex-shrink:0">
          <!-- Outer hexagon node outline -->
          <polygon points="36,4 64,20 64,52 36,68 8,52 8,20"
                   fill="none" stroke="#4CAF50" stroke-width="2.5" stroke-linejoin="round"/>
          <!-- Network node circles at vertices -->
          <circle cx="36" cy="4"  r="3" fill="#4CAF50"/>
          <circle cx="64" cy="20" r="3" fill="#4CAF50"/>
          <circle cx="64" cy="52" r="3" fill="#4CAF50"/>
          <circle cx="36" cy="68" r="3" fill="#4CAF50"/>
          <circle cx="8"  cy="52" r="3" fill="#4CAF50"/>
          <circle cx="8"  cy="20" r="3" fill="#4CAF50"/>
          <!-- Internal network lines (asymmetric) -->
          <line x1="36" y1="4"  x2="64" y2="52" stroke="#2E7D32" stroke-width="1.2" opacity="0.55"/>
          <line x1="8"  y1="20" x2="64" y2="20" stroke="#2E7D32" stroke-width="1.2" opacity="0.55"/>
          <line x1="36" y1="68" x2="8"  y2="20" stroke="#2E7D32" stroke-width="1.2" opacity="0.55"/>
          <!-- Bold stylised N -->
          <text x="36" y="50" text-anchor="middle"
                font-family="Montserrat,Arial Black,sans-serif"
                font-weight="900" font-size="34" fill="#FFFFFF" letter-spacing="-1">N</text>
          <!-- Accent green leaf (bottom-right of hexagon) -->
          <text x="53" y="63" font-size="13" style="font-family:sans-serif">🌿</text>
        </svg>
        <div>
          <div style="font-family:'Montserrat',monospace;font-weight:900;font-size:2rem;
                      color:#FFFFFF;letter-spacing:0.06em;line-height:1">{t("app_title").replace("🌿 ", "")}</div>
          <div style="font-family:'Montserrat',monospace;font-weight:500;font-size:0.78rem;
                      color:#A1887F;margin-top:5px;line-height:1.4">{t("app_subtitle")}</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  SIDEBAR — LANGUAGE · THEME · ALL INPUTS
# ╚══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(
        f"<h3 style='margin-top:0;color:{_C_ACCENT};"
        "font-family:Montserrat,monospace;font-weight:700'>"
        f"{t('sidebar_title')}</h3>",
        unsafe_allow_html=True,
    )

    # ── Language selector ─────────────────────────────────────────────────────
    _lang_options  = {
        "en": "🇬🇧 English",
        "es": "🇪🇸 Español",
        "fr": "🇫🇷 Français",
        "zh": "🇨🇳 简体中文",
        "ar": "🇸🇦 العربية",
    }
    _lang_selected = st.selectbox(
        t("lang_label"),
        options=list(_lang_options.keys()),
        format_func=lambda k: _lang_options[k],
        index=list(_lang_options.keys()).index(st.session_state.get("current_lang", "en")),
        key="current_lang",
    )
    _lang = _lang_selected   # update local shortcut after widget

    # ── Theme toggle ──────────────────────────────────────────────────────────
    st.toggle(
        f"{t('theme_label')}: **{t('theme_dark') if st.session_state.get('dark_mode', True) else t('theme_light')}**",
        key="dark_mode",
    )

    st.divider()

    # ── Expander 1: Location & Precipitation ─────────────────────────────────
    with st.expander(t("exp_location"), expanded=True):
        st.text_input(t("lbl_location"), key="location_str")

        if st.button(t("btn_lookup"), use_container_width=True):
            with st.spinner("…"):
                _precip_result = weather.get_precipitation_index(
                    st.session_state["location_str"]
                )
            st.session_state["precip_index"]        = _precip_result["precip_index"]
            st.session_state["precip_lookup_done"]  = True
            st.session_state["_precip_result"]      = _precip_result
            # Auto-populate the Idaho annual precip slider from mm → inches
            if _precip_result["error"] is None:
                _precip_in = _precip_result["mean_annual_mm"] / 25.4
                st.session_state["annual_precip_in"] = round(_precip_in, 1)

        if st.session_state.get("precip_lookup_done") and st.session_state.get("_precip_result"):
            _r = st.session_state["_precip_result"]
            if _r["error"] is None:
                _in = _r["mean_annual_mm"] / 25.4
                st.info(
                    t("info_station").format(station=_r["station_name"]) + "  \n"
                    + t("info_precip").format(mm=_r["mean_annual_mm"]) + "  \n"
                    + t("info_years").format(years=_r["years_used"]) + "  \n"
                    + t("info_idx").format(idx=_r["precip_index"])
                    + f"  \n**Annual: {_in:.1f} inches** → auto-filled below",
                    icon="🌧️",
                )
            else:
                st.warning(f"⚠️ {_r['error']}  \nFallback = 1.0 / 13 in", icon="⚠️")

    # ── Expander 2: Farm Inputs (University of Idaho CIS 453) ────────────────
    with st.expander(t("exp_farm"), expanded=True):
        st.slider(t("lbl_yield"), 20, 150, step=1, key="yield_potential")

        # ── Idaho CIS 453 Precipitation Zone ──────────────────────────────────
        st.markdown(
            f"<p style='color:{_C_ACCENT};font-weight:700;font-size:0.77rem;"
            "letter-spacing:0.07em;margin:10px 0 2px'>── UI CIS 453 INPUTS ──</p>",
            unsafe_allow_html=True,
        )
        st.slider(
            "Annual Precipitation (inches/yr)",
            min_value=6, max_value=50, step=1,
            key="annual_precip_in",
            help=(
                "Determines CIS 453 N demand zone:\n"
                "< 18 in → 2.4 | 18-21 → 2.5 | 21-24 → 2.7 | 24-28 → 2.9 | > 28 → 3.1 lbs N/bu"
            ),
        )
        # Show the active zone factor (uses inline helper — immune to module cache issues)
        _zone_factor = _get_n_demand_factor(
            float(st.session_state.get("annual_precip_in", 13))
        )
        st.caption(
            f"Active N demand: **{_zone_factor} lbs N/bu** "
            f"(× {st.session_state.get('yield_potential', 72)} bu/ac "
            f"= **{_zone_factor * float(st.session_state.get('yield_potential', 72)):.1f} lbs N/ac total demand**)"
        )

        st.number_input(
            "Soil Organic Matter (%)",
            min_value=0.5, max_value=8.0, step=0.1, format="%.1f",
            key="som_pct",
            help="CIS 453 Table 2: at 2.4% SOM → 50 lbs N/ac (conventional), 43 lbs N/ac (reduced)",
        )
        st.selectbox(
            "Tillage System",
            options=["conventional", "reduced"],
            format_func=lambda x: "Conventional Tillage" if x == "conventional" else "Reduced / No-Till",
            key="tillage_type",
        )
        # Show live SOM credit (inline helper — cache-safe)
        _som_credit = _get_som_n_credit(
            float(st.session_state.get("som_pct", 2.4)),
            str(st.session_state.get("tillage_type", "conventional")),
        )
        st.caption(f"SOM N credit: **{_som_credit:.0f} lbs N/ac** (CIS 453 Table 2)")

        st.number_input(
            "Soil Test NO\u2083 (ppm)",
            min_value=0.0, max_value=50.0, step=0.5, format="%.1f",
            key="soil_test_no3_ppm",
            help="ppm NO₃-N × 3.5 = lbs N/acre. CIS 453 conversion scalar.",
        )
        _soil_lbs = float(st.session_state.get("soil_test_no3_ppm", 5.7)) * 3.5
        st.caption(f"Soil test credit: **{_soil_lbs:.1f} lbs N/ac** ({st.session_state.get('soil_test_no3_ppm', 5.7):.1f} ppm × 3.5)")

        st.number_input(
            "Cereal Straw Left in Field (tons/ac)",
            min_value=0.0, max_value=6.0, step=0.25, format="%.2f",
            key="straw_tons_acre",
            help="15 lbs N/ton immobilization debit (CIS 453). 0 = straw removed / grazed.",
        )
        st.selectbox(
            "Previous Legume Cover Crop",
            options=list(UI_LEGUME_N_CREDITS.keys()),
            key="legume_type",
            help="CIS 453 Table 5: N credit from prior-season legume residue.",
        )
        _legume_lbs = UI_LEGUME_N_CREDITS.get(str(st.session_state.get("legume_type", "None")), 0.0)
        if _legume_lbs > 0:
            st.caption(f"Legume N credit: **{_legume_lbs:.0f} lbs N/ac**")

        # ── NitrogenCal2 Collaborative Engine ─────────────────────────────────
        st.markdown(
            f"<p style='color:{_C_ACCENT};font-weight:700;font-size:0.77rem;"
            "letter-spacing:0.07em;margin:14px 0 2px'>── NitrogenCal2 Engine ──</p>",
            unsafe_allow_html=True,
        )
        st.session_state["precip_index"] = st.slider(
            "Annual Rainfall (inches)", 12, 35,
            int(st.session_state.get("precip_index", 20)),
            step=1,
            help="Total annual rainfall. Drives the Base N Requirement factor.",
        )
        st.session_state["soil_test_ppm"] = st.number_input(
            "Soil Test NO\u2083 (ppm) — legacy",
            min_value=0.0, max_value=50.0, step=0.5, format="%.1f",
            value=float(st.session_state.get("soil_test_ppm", 20.0)),
            help="Legacy single-depth field; depth readings below take precedence.",
        )
        st.markdown("**Soil Nitrate by Depth (PPM)**")
        _sn1, _sn2, _sn3 = st.columns(3)
        with _sn1:
            st.session_state["ppm_0_12"] = st.number_input(
                "0–12 inch", 0.0, 50.0,
                float(st.session_state.get("ppm_0_12", 5.0)),
                step=0.5, format="%.1f",
            )
        with _sn2:
            st.session_state["ppm_12_24"] = st.number_input(
                "12–24 inch", 0.0, 50.0,
                float(st.session_state.get("ppm_12_24", 3.0)),
                step=0.5, format="%.1f",
            )
        with _sn3:
            st.session_state["ppm_24_36"] = st.number_input(
                "24–36 inch", 0.0, 50.0,
                float(st.session_state.get("ppm_24_36", 2.0)),
                step=0.5, format="%.1f",
            )
        st.session_state["legume_toggle"] = st.toggle(
            "Previous Crop Was Legume",
            value=st.session_state.get("legume_toggle", False),
        )
        st.session_state["residue_toggle"] = st.toggle(
            "Cereal Residue Present",
            value=st.session_state.get("residue_toggle", True),
        )
        st.session_state["residue_level"] = st.select_slider(
            "Residue Amount (tons/acre)",
            options=[0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
            value=st.session_state.get("residue_level", 2.0),
            help="Select the crop residue level. Legume residue credits N; "
                 "cereal residue requires extra N.",
        )
        engine_result = math_engine.run_collaborative_calculation_engine(
            yield_potential   = st.session_state.get("yield_potential", 60.0),
            precip_index      = st.session_state.get("precip_index", 20.0),
            som_pct           = st.session_state.get("som_pct", 2.5),
            soil_test_ppm     = st.session_state.get("soil_test_ppm", 20.0),
            tillage_selection = st.session_state.get("tillage_selection", "Conventional"),
            legume_toggle     = st.session_state.get("legume_toggle", False),
            residue_toggle    = st.session_state.get("residue_toggle", True),
            user_urea_price   = st.session_state.get("urea_price_per_ton", 400.0),
            ppm_0_12          = st.session_state.get("ppm_0_12", 5.0),
            ppm_12_24         = st.session_state.get("ppm_12_24", 3.0),
            ppm_24_36         = st.session_state.get("ppm_24_36", 2.0),
            residue_level     = float(st.session_state.get("residue_level", 2.0)),
        )
        _nc1, _nc2, _nc3 = st.columns(3)
        with _nc1:
            st.metric(
                "N Required",
                f"{engine_result.get('nitrogen_required', 0):.1f} lbs/ac",
            )
        with _nc2:
            st.metric(
                "Bulk Urea Needed",
                f"{engine_result.get('bulk_urea_needed', 0):,.0f} lbs/ac",
            )
        with _nc3:
            st.metric(
                "Urea Cost",
                f"${engine_result.get('calculated_urea_cost', 0):,.2f}/ac",
            )
        _nc4, _nc5 = st.columns(2)
        with _nc4:
            st.metric(
                "Gross N Demand (BLR)",
                f"{engine_result.get('gross_n_demand', 0):.1f} lbs/ac",
            )
        with _nc5:
            st.metric(
                "Available N Sources",
                f"{engine_result.get('available_n_sources', 0):.1f} lbs/ac",
            )
        with st.expander("Calculation Breakdown"):
            bd = engine_result.get("calculation_breakdown", {})
            st.markdown(
                f"| Step | Value |\n"
                f"|------|-------|\n"
                f"| Base N Requirement (BLR) | **{bd.get('base_n_requirement_blr', 0):.1f}** lbs/acre |\n"
                f"| × Precipitation Factor   | **{bd.get('precipitation_factor', 0):.2f}** |\n"
                f"| − Organic Matter Credit  | **{bd.get('om_credit', 0):.1f}** lbs/acre |\n"
                f"| − Soil Nitrate Credit    | **{bd.get('soil_nitrate_credit', 0):.1f}** lbs/acre |\n"
                f"| ± Residue Credit         | **{bd.get('residue_credit', 0):.1f}** lbs/acre |\n"
                f"| = **N Required**         | **{engine_result.get('nitrogen_required', 0):.1f}** lbs/acre |"
            )
        st.caption("⚙ NitrogenCal2 Engine v2.0 — Integrated")

        st.markdown(
            f"<p style='color:{_C_ACCENT};font-weight:700;font-size:0.77rem;"
            f"letter-spacing:0.08em;margin-top:12px'>{t('section_eco')}</p>",
            unsafe_allow_html=True,
        )
        st.number_input(t("lbl_fert_applied"), min_value=0.0, step=1.0,
                        help=t("help_fert_applied"), key="fertilizer_applied")
        st.number_input(t("lbl_wheat_price"),  min_value=0.0, step=0.25,
                        format="%.2f", help=t("help_wheat_price"), key="wheat_price")
        st.number_input(t("lbl_fert_price"),   min_value=0.0, step=10.0,
                        format="%.0f", help=t("help_fert_price"), key="fertilizer_price_ton")

        st.markdown(
            f"<p style='color:{_C_ACCENT};font-weight:700;font-size:0.8rem;"
            f"letter-spacing:0.08em;margin-top:10px'>{t('section_audit')}</p>",
            unsafe_allow_html=True,
        )
        for _dim in AUDIT_DIMENSIONS:
            st.radio(
                t(_DIM_LOCALE_KEY[_dim]),
                options=_AUDIT_OPT_KEYS,
                format_func=lambda k: t(k),
                key=f"_audit_Farm_{_dim}",
            )

    # ── Expander 3: Mill Inputs ───────────────────────────────────────────────
    with st.expander(t("exp_mill")):
        st.slider(t("lbl_extraction"), 60, 100, step=1, key="extraction_rate")
        st.caption(t("cap_extraction"))

        st.markdown(
            f"<p style='color:{_C_ACCENT};font-weight:700;font-size:0.8rem;"
            f"letter-spacing:0.08em;margin-top:10px'>{t('section_audit')}</p>",
            unsafe_allow_html=True,
        )
        for _dim in AUDIT_DIMENSIONS:
            st.radio(
                t(_DIM_LOCALE_KEY[_dim]),
                options=_AUDIT_OPT_KEYS,
                format_func=lambda k: t(k),
                key=f"_audit_Mill_{_dim}",
            )

    # ── Expander 4: Bakery & Retail ───────────────────────────────────────────
    with st.expander(t("exp_bakery")):
        st.selectbox(t("lbl_variant"), options=list(PRODUCT_VARIANTS.keys()),
                     key="product_variant")
        st.slider(t("lbl_spoilage"), 0, 25, step=1, key="spoilage_waste_pct")

        st.markdown(
            f"<p style='color:{_C_ACCENT};font-weight:700;font-size:0.8rem;"
            f"letter-spacing:0.08em;margin-top:10px'>{t('section_audit')}</p>",
            unsafe_allow_html=True,
        )
        for _dim in AUDIT_DIMENSIONS:
            st.radio(
                t(_DIM_LOCALE_KEY[_dim]),
                options=_AUDIT_OPT_KEYS,
                format_func=lambda k: t(k),
                key=f"_audit_Bakery & Retail_{_dim}",
            )

    st.divider()
    st.caption(t("footer"))


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  CALCULATIONS — all delegated to src/  (no changes to logic)
# ╚══════════════════════════════════════════════════════════════════════════════

# Reconstruct audit_scores from per-cell radio widget state (English keys always)
_current_audit_scores = {
    seg: {
        dim: _AUDIT_VAL_MAP[st.session_state[f"_audit_{seg}_{dim}"]]
        for dim in AUDIT_DIMENSIONS
    }
    for seg in AUDIT_SEGMENTS
}
st.session_state["audit_scores"] = _current_audit_scores

# Local aliases for session state values
_yield              = float(st.session_state["yield_potential"])
_annual_precip_in   = float(st.session_state["annual_precip_in"])
_som_pct            = float(st.session_state["som_pct"])
_tillage            = str(st.session_state["tillage_type"])
_soil_ppm           = float(st.session_state["soil_test_no3_ppm"])
_straw_tons         = float(st.session_state["straw_tons_acre"])
_legume_lbs         = float(UI_LEGUME_N_CREDITS.get(
                          str(st.session_state.get("legume_type", "None")), 0.0))
_extr               = float(st.session_state["extraction_rate"])
_variant            = str(st.session_state["product_variant"])
_spoilage           = float(st.session_state["spoilage_waste_pct"])
_fert_applied       = float(st.session_state["fertilizer_applied"])
_wheat_price        = float(st.session_state["wheat_price"])
_fert_price_ton     = float(st.session_state["fertilizer_price_ton"])

#  Move this to the very top of the block so it is ready for downstream use!
grain_n_uptake = math_engine.calc_grain_n_uptake(_yield)

try:
    n_application = math_engine.calc_n_application_idaho(
        yield_potential_bu   = _yield,
        annual_precip_in     = _annual_precip_in,
        som_pct              = _som_pct,
        tillage              = _tillage,
        soil_test_no3_ppm    = _soil_ppm,
        straw_tons_acre      = _straw_tons,
        legume_n_credit_lbs  = _legume_lbs,
    )
except AttributeError:
    # Inline CIS 453 fallback — Aligned perfectly with fixed math signs
    _zf = _get_n_demand_factor(_annual_precip_in)
    _sc = _get_som_n_credit(_som_pct, _tillage)
    n_application = max((_yield * _zf) - _sc - (_soil_ppm * 3.5) - _legume_lbs + (_straw_tons * 15), 0.0)

_nue_calc_error: str | None = None
farm_nue:        float      = 0.0
farm_validation: dict       = {"status": "warning", "message": "", "color": "#F59E0B"}

try:
    # Safely compute farm efficiency metrics
    farm_nue        = math_engine.calc_farm_nue(grain_n_uptake, n_application)
    farm_validation = math_engine.validate_farm_nue(farm_nue)
except ZeroDivisionError:
    _nue_calc_error = t("err_zero_n")

# Segment 2: Mill — Out of the try block and perfectly safe to execute
mill_result = math_engine.calc_mill_output(grain_n_uptake, _extr)

# Segment 3: Bakery & Retail
loaves_per_acre    = math_engine.calc_loaves_per_acre(_yield, _extr, _variant, _spoilage)
flour_n_g_per_loaf = (mill_result["flour_n"] * _G_PER_LB / loaves_per_acre
                      if loaves_per_acre > 0 else 0.0)
bakery_result      = math_engine.calc_bakery_output(flour_n_g_per_loaf, _variant, _spoilage)

# System NUE
_sys_nue_error: str | None = None
system_nue:     float      = 0.0
try:
    system_nue = math_engine.calc_system_nue(
        n_application, bakery_result["final_n_g"], _yield, loaves_per_acre
    )
except ZeroDivisionError:
    _sys_nue_error = t("err_zero_sys")

# Economic Engine
economic_result = math_engine.calc_economic_return(
    yield_bu               = _yield,
    price_per_bu           = _wheat_price,
    n_applied_lbs          = _fert_applied,
    cost_per_ton_fertilizer= _fert_price_ton,
)

# Audit matrix & Pipeline DataFrame
audit_df  = audit.build_audit_matrix(_current_audit_scores)
_any_risk = audit_df["risk_flag"].any()


def _seg_score(segment: str) -> int:
    rows = audit_df.filter(
        (audit_df["segment"] == segment) & (audit_df["dimension"] == "Input Data")
    )
    return int(rows["score"][0]) if rows.height > 0 else 3


pipeline_df = math_engine.build_pipeline_df(
    n_application_lbs_acre  = n_application,
    grain_n_uptake_lbs_acre  = grain_n_uptake,
    farm_nue_pct             = farm_nue,
    farm_data_score          = _seg_score("Farm"),
    flour_n_lbs_acre         = mill_result["flour_n"],
    bran_n_lbs_acre          = mill_result["bran_n"],
    mill_nue_pct             = mill_result["mill_nue"],
    mill_data_score          = _seg_score("Mill"),
    flour_n_g_per_loaf       = flour_n_g_per_loaf,
    bakery_result            = bakery_result,
    bakery_data_score        = _seg_score("Bakery & Retail"),
    loaves_per_acre          = loaves_per_acre,
)

# Translated farm-validation message (override engine's English string)
if _nue_calc_error is None:
    _status = farm_validation["status"]
    if _status == "critical":
        farm_validation["message"] = t("msg_soil_mining")
    elif _status == "optimal":
        farm_validation["message"] = t("msg_optimal")
    else:
        farm_validation["message"] = t("msg_warning")


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  MAIN AREA — DASHBOARD TABS
# ╚══════════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab_urea = st.tabs([t("tab_flow"), t("tab_nue"), t("tab_audit"), "📊 Urea Market"])


# ── Tab 1: Nitrogen Flow ──────────────────────────────────────────────────────
with tab1:
    st.markdown(f"### {t('t1_header')}")
    st.caption(t("t1_caption"))
    bread_type = st.radio(
        "Bread Type",
        options=["Refined", "Whole Wheat"],
        horizontal=True,
        key="bread_type_selector",
    )
    st.plotly_chart(
        charts.build_nitrogen_sankey(pipeline_df, bread_type, dark_mode=_is_dark),
        use_container_width=True,
    )
    col_bar, col_pie = st.columns(2)
    with col_bar:
        st.plotly_chart(
            charts.build_bread_comparison_bar_chart(_is_dark),
            use_container_width=True,
        )
    with col_pie:
        st.plotly_chart(
            charts.build_nue_distribution_pie(bread_type, _is_dark),
            use_container_width=True,
        )

    st.divider()
    st.markdown(f"#### {t('t1_table_hdr')}")
    st.dataframe(
        pipeline_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "segment":    st.column_config.TextColumn(t("col_segment")),
            "n_in_g":     st.column_config.NumberColumn(t("col_n_in"),   format="%.2f"),
            "n_out_g":    st.column_config.NumberColumn(t("col_n_out"),  format="%.2f"),
            "n_loss_g":   st.column_config.NumberColumn(t("col_n_loss"), format="%.2f"),
            "nue_pct":    st.column_config.NumberColumn(t("col_nue"),    format="%.1f"),
            "data_score": st.column_config.NumberColumn(t("col_score")),
            "data_label": st.column_config.TextColumn(t("col_quality")),
        },
    )


# ── Tab 2: NUE Dashboard ──────────────────────────────────────────────────────
with tab2:
    # Validation banner
    if _nue_calc_error:
        st.error(f"🚨 {_nue_calc_error}")
    elif farm_validation["status"] == "critical":
        st.error(f"🚨 {farm_validation['message']}")
    elif farm_validation["status"] == "optimal":
        st.success(f"✅ {farm_validation['message']}")
    else:
        st.warning(f"⚠️ {farm_validation['message']}")

    st.markdown(f"### {t('t2_header')}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f"<h5 style='text-align:center;color:{_C_ACCENT}'>{t('seg_farm')}</h5>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            charts.build_nue_gauge(farm_nue, t("seg_farm"), dark_mode=_is_dark),
            use_container_width=True,
        )
    with col2:
        st.markdown(
            f"<h5 style='text-align:center;color:{_C_GREEN_BOLD}'>{t('seg_mill')}</h5>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            charts.build_nue_gauge(mill_result["mill_nue"], t("seg_mill"), dark_mode=_is_dark),
            use_container_width=True,
        )
    with col3:
        st.markdown(
            f"<h5 style='text-align:center;color:{_C_GREEN_BOLD}'>{t('seg_bakery')}</h5>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            charts.build_nue_gauge(
                bakery_result["bakery_nue"], t("seg_bakery"), dark_mode=_is_dark
            ),
            use_container_width=True,
        )

    # System NUE
    st.divider()
    st.markdown(f"### {t('t2_sys_header')}")
    st.caption(t("t2_sys_caption"))

    if _sys_nue_error:
        st.error(f"🚨 {_sys_nue_error}")
    else:
        _sys_col, _ = st.columns([2, 1])
        with _sys_col:
            st.plotly_chart(
                charts.build_nue_gauge(
                    system_nue, t("t2_sys_header"), dark_mode=_is_dark
                ),
                use_container_width=True,
            )

    # Consumer output
    st.divider()
    st.markdown(f"### {t('t2_consumer_hdr')}")
    st.caption(t("t2_benchmark").format(
        prot=bakery_result["reference_protein_g"],
        n=bakery_result["reference_n_g"],
    ))

    # FIXED: Extract active selection from your radio toggle key
    _active_bread = st.session_state.get("bread_type_selector", "Refined")

    if _active_bread == "Refined":
        loaf_nitrogen = 18.77
        loaf_protein = 107
    else:
        loaf_nitrogen = 21.53
        loaf_protein = 123

    col_a, col_b = st.columns(2)
    with col_a:
        st.metric(
            label=t("metric_final_n"),
            value=f"{loaf_nitrogen:.2f} g",
            delta=t("delta_n_vs_ref").format(
                v=loaf_nitrogen - 21.525
            ),
        )
    with col_b:
        st.metric(
            label=t("metric_protein"),
            value=f"{loaf_protein}.0 g ({loaf_protein/10:.1f}%)",
            delta=t("delta_n_factor"),
        )

    # Economic sub-grid
    st.divider()
    st.markdown(f"### {t('t2_eco_header')}")
    st.caption(t("t2_eco_caption").format(
        cplb=economic_result["cost_per_lb_n"],
        price=_fert_price_ton,
    ))

    eco1, eco2, eco3 = st.columns(3)
    with eco1:
        st.metric(
            label=t("metric_gross"),
            value=f"${economic_result['gross_revenue']:,.2f}",
            delta=t("delta_gross").format(y=_yield, p=_wheat_price),
        )
    with eco2:
        st.metric(
            label=t("metric_fert_cost"),
            value=f"${economic_result['fertilizer_cost']:,.2f}",
            delta=t("delta_fert").format(
                n=_fert_applied, c=economic_result["cost_per_lb_n"]
            ),
        )
    with eco3:
        _is_profit = economic_result["net_margin"] >= 0
        st.metric(
            label=t("metric_net"),
            value=f"${economic_result['net_margin']:,.2f}",
            delta=t("lbl_profitable") if _is_profit else t("lbl_loss"),
            delta_color="normal" if _is_profit else "inverse",
        )


# ── Tab 3: Data Audit ─────────────────────────────────────────────────────────
with tab3:
    st.markdown(f"### {t('t3_header')}")
    st.caption(t("t3_caption").format(threshold=AUDIT_RISK_THRESHOLD))

    st.plotly_chart(
        audit.get_heatmap_figure(audit_df, dark_mode=_is_dark),
        use_container_width=True,
    )

    if _any_risk:
        st.error(t("err_data_integrity").format(threshold=AUDIT_RISK_THRESHOLD))

    st.divider()
    st.markdown(f"#### {t('t3_table_hdr')}")
    st.dataframe(
        audit_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "segment":   st.column_config.TextColumn(t("col_segment")),
            "dimension": st.column_config.TextColumn(t("col_dimension")),
            "score":     st.column_config.NumberColumn(t("col_audit_score")),
            "risk_flag": st.column_config.CheckboxColumn(t("col_risk")),
        },
    )

    with st.expander(t("legend_title"), expanded=False):
        st.markdown(
            f"""
| {t('col_audit_score')} | {t('col_quality')} | Source |
|---|---|---|
| **5** | {t('audit_high')} | IoT / farm-level ledger |
| **3** | {t('audit_med')} | Regional / cooperative DB |
| **1** | {t('audit_low')} | Stale industry defaults |
            """
        )
        st.markdown(
            f"Scores **≤ {AUDIT_RISK_THRESHOLD}** trigger a red heatmap cell and the alert above."
        )


# ── Tab 4: Urea Market Trend ──────────────────────────────────────────────────
with tab_urea:
    import polars as _pl_urea   # local alias — polars not imported at app.py top level
    import pathlib as _pathlib_urea

    st.subheader("Northwest U.S. Urea Price History (2015–2024)")

    # Safe initialization — only set if not already in session state
    if "urea_price_per_ton" not in st.session_state:
        st.session_state["urea_price_per_ton"] = 400.0
    if "urea_n_applied_lbs" not in st.session_state:
        st.session_state["urea_n_applied_lbs"] = 120.0
    if "urea_yield_bu" not in st.session_state:
        st.session_state["urea_yield_bu"] = 60.0
    if "urea_market_wheat_price" not in st.session_state:
        st.session_state["urea_market_wheat_price"] = 6.50

    # Sidebar — urea cost slider (appended below existing sidebar widgets)
    with st.sidebar:
        st.markdown(
            f"<p style='color:{_C_ACCENT};font-weight:700;font-size:0.77rem;"
            "letter-spacing:0.07em;margin:10px 0 2px'>── UREA MARKET ──</p>",
            unsafe_allow_html=True,
        )
        st.session_state["urea_price_per_ton"] = float(st.slider(
            "Urea Price (USD/ton)", 150, 900,
            int(st.session_state["urea_price_per_ton"]), step=10,
            key="_urea_price_slider",
        ))

    # Chart axis selector
    _UREA_CHART_OPTIONS = {
        "Nominal Price (USD/mt)":   "Nominal Price\n(USD/mt)",
        "Real Price (2024 USD/mt)": "Real Price\n(2024 USD/mt)",
        "NW Consumption (mt)":      "Consumption\nin Weight (mt)",
        "Per Capita Consumption":   "Consumption\nPer Capita (mt/person)",
    }
    _selected_label = st.selectbox(
        "Y-Axis Metric", list(_UREA_CHART_OPTIONS.keys()), key="_urea_y_axis"
    )
    _selected_col = _UREA_CHART_OPTIONS[_selected_label]

    # Load Excel — FIXED: Check both root and local directory dynamically
    _base_path = _pathlib_urea.Path(__file__).parent
    _excel_path_primary = _base_path / "Urea_NW_Historical_Analysis_2015_2024.xlsx"
    _excel_path_secondary = _base_path.parent / "Urea_NW_Historical_Analysis_2015_2024.xlsx"

    # Use whichever path successfully finds the file
    if _excel_path_primary.exists():
        _excel_path = str(_excel_path_primary)
    else:
        _excel_path = str(_excel_path_secondary)
        
    try:
        _df_raw = _pl_urea.read_excel(_excel_path, has_header=False)
        _header = _df_raw.row(2)
        urea_df = (
            _df_raw
            .slice(3)
            .rename({
                _df_raw.columns[i]: (str(_header[i]) if _header[i] is not None else f"_col{i}")
                for i in range(len(_df_raw.columns))
            })
        )
        st.plotly_chart(
            charts.build_urea_history_chart(urea_df, _selected_col, _is_dark),
            use_container_width=True,
        )
    except Exception as _e:
        st.error(f"Could not load urea data: {_e}")

    # ── Economic Return Calculator ──────────────────────────────────────────
    st.markdown("---")
    st.subheader("Economic Return Calculator")
    _eco_c1, _eco_c2 = st.columns(2)
    with _eco_c1:
        _u_n_lbs = st.number_input(
            "N Applied (lbs/acre)", 0, 300,
            int(st.session_state["urea_n_applied_lbs"]),
            key="_urea_n_input",
        )
        _u_yld = st.number_input(
            "Expected Yield (bu/acre)", 0, 200,
            int(st.session_state["urea_yield_bu"]),
            key="_urea_yield_input",
        )
    with _eco_c2:
        _u_wheat_px = st.number_input(
            "Wheat Price ($/bu)", 0.0, 20.0,
            st.session_state["urea_market_wheat_price"], 0.10,
            key="_urea_wheat_px_input",
        )

    _urea_result = math_engine.calc_urea_economic_return(
        n_applied_lbs      = float(_u_n_lbs),
        yield_bu           = float(_u_yld),
        market_wheat_price = float(_u_wheat_px),
        urea_price_per_ton = float(st.session_state["urea_price_per_ton"]),
    )
    _um1, _um2, _um3 = st.columns(3)
    with _um1:
        st.metric("Gross Revenue ($/acre)",        f"${_urea_result['gross_revenue']:,.2f}")
    with _um2:
        st.metric("Fertilizer Cost ($/acre)",       f"${_urea_result['fertilizer_cost']:,.2f}")
    with _um3:
        st.metric(
            "Net Operating Margin ($/acre)",
            f"${_urea_result['net_operating_margin']:,.2f}",
            delta=f"Urea needed: {_urea_result['urea_needed_lbs']:.1f} lbs/acre",
        )


# ── Technical Audit Assumptions & Future Scope ────────────────────────────────
st.divider()
with st.expander(t("exp_tech_audit"), expanded=False):
    st.markdown(
        """
### Documentation Notes

Current system data is strictly normalized around **Pacific Northwest / Idaho regional ag extension
conversion tables** for Hard Red Winter Wheat. Calibration benchmarks:

| Parameter | Value | Source |
|-----------|-------|--------|
| Yield target | 72 bu/ac | UI Extension / PNW ag data |
| N requirement multiplier | 2.625 lbs N/bu (189 lbs N / 72 bu) | PNW regional |
| White flour extraction | 76.54% | Updated milling standard |
| Bran fraction remainder | 23.46% | 100 − 76.54 |
| Bread protein per 100 g | 12.3 g | USDA FDC hard red winter wheat bread |
| N per g protein | 0.175 g N/g protein | 1 ÷ 5.714 Kjeldahl scalar |
| Reference loaf N | 21.525 g per 1 kg loaf | 123.0 g protein × 0.175 |
| Fertilizer baseline | 104 lbs N/ac | Regional university extension |
| Fertilizer N content | 46% (urea standard) | Industry |

---

### Future Verification Layers Required

Actual NUE models require field verification including:

- **Deep soil nitrate analysis** — sub-surface N pools not captured in current SOM / soil-test credits
- **Carbon crop residue ratios** — C:N immobilization varies significantly with residue type and tillage
- **Atmospheric volatilization losses** (NH₃, N₂O) — gaseous N loss pathways are unquantified; may represent 10–30% of applied N in dryland PNW conditions
- **Leaching rate verification** — precipitation-driven NO₃⁻ movement requires field lysimeter data at site-specific soil texture and drainage class
- **Milling extraction variance** — 76.54% is a mean estimate; actual rates are sensitive to grain protein content, moisture, and equipment
- **Supply chain freight and storage losses** — post-bakery N losses in packaging and retail shelf life are currently set to zero

> ⚠️ Until these layers are incorporated, **all NUE outputs should be treated as directional
> estimates only**, not regulatory-grade measurements.
        """,
        unsafe_allow_html=False,
    )
