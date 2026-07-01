import streamlit as st
import folium
from streamlit_folium import st_folium
import hashlib
import pandas as pd
import io
import datetime
import requests

# Page Configuration
st.set_page_config(page_title="Khetify - AI Satellite Analysis Engine", layout="wide")

# --- CUSTOM CSS FOR INJECTING NATURAL AGRICULTURE CORE THEME ---
st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #0d1611 0%, #111a14 50%, #16241b 100%) !important;
            color: #e2e8f0 !important;
        }
        [data-testid="stSidebar"] {
            background-color: #0b120e !important;
            border-right: 1px solid #1c3325 !important;
        }
        div[data-testid="stMetricValue"] {
            color: #ffffff !important;
        }
    </style>
""", unsafe_allow_html=True)

# =========================================================================
# MODIS REAL DATA ENGINE (NASA ORNL DAAC Web Service - free, no API key)
# Product: MOD13Q1 -> MODIS/Terra Vegetation Indices, 250m, 16-day composite
# Docs: https://modis.ornl.gov/data/modis_webservice.html
# NOTE: This is REAL satellite data, but MODIS composites are produced on a
# 16-day cycle (not literally real-time) and the 250m pixel covers ~6.25
# hectares, so it reflects FIELD-LEVEL vegetation health, not a pinpointed
# infection spot.
# =========================================================================
MODIS_PRODUCT = "MOD13Q1"
MODIS_BASE_URL = "https://modis.ornl.gov/rst/api/v1"
MODIS_FILL_VALUE_THRESHOLD = -3000  # values <= this are invalid/fill pixels
MODIS_SCALE_FACTOR = 0.0001


@st.cache_data(ttl=3600, show_spinner=False)
def modis_fetch_available_dates(lat: float, lon: float):
    """Get list of MODIS composite dates available for this location."""
    url = f"{MODIS_BASE_URL}/{MODIS_PRODUCT}/dates"
    resp = requests.get(
        url,
        params={"latitude": lat, "longitude": lon},
        headers={"Accept": "application/json"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("dates", [])


@st.cache_data(ttl=3600, show_spinner=False)
def modis_fetch_ndvi_subset(lat: float, lon: float, start_modis_date: str, end_modis_date: str):
    """Fetch the real NDVI band subset for a MODIS composite date range."""
    url = f"{MODIS_BASE_URL}/{MODIS_PRODUCT}/subset"
    params = {
        "latitude": lat,
        "longitude": lon,
        "band": "250m_16_days_NDVI",
        "startDate": start_modis_date,
        "endDate": end_modis_date,
        "kmAboveBelow": 0,
        "kmLeftRight": 0,
    }
    resp = requests.get(url, params=params, headers={"Accept": "application/json"}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("subset", [])


def get_real_modis_ndvi_timeseries(lat: float, lon: float, start_date: datetime.date, end_date: datetime.date):
    """
    Orchestrates: find available MODIS composite dates in range -> pull real
    NDVI subset -> scale + QC filter -> return sorted list of records.
    Returns (records, error_message). records is a list of dicts:
    {"date": date, "modis_date": "A2024129", "ndvi": float}
    """
    try:
        all_dates = modis_fetch_available_dates(lat, lon)
    except requests.exceptions.RequestException as e:
        return None, f"Could not reach NASA ORNL DAAC MODIS service: {e}"

    if not all_dates:
        return None, "No MODIS coverage returned for this location (check coordinates)."

    parsed = []
    for d in all_dates:
        try:
            cal_date = datetime.datetime.strptime(d["calendar_date"], "%Y-%m-%d").date()
            parsed.append((cal_date, d["modis_date"]))
        except (KeyError, ValueError):
            continue

    in_range = sorted([p for p in parsed if start_date <= p[0] <= end_date])

    if not in_range:
        return None, "No MODIS composite exists inside the selected date range for this exact location. Try widening the date range."

    # API allows a max of 10 modis dates per subset request
    if len(in_range) > 10:
        in_range = in_range[-10:]

    start_modis = in_range[0][1]
    end_modis = in_range[-1][1]

    try:
        subset = modis_fetch_ndvi_subset(lat, lon, start_modis, end_modis)
    except requests.exceptions.RequestException as e:
        return None, f"Could not reach NASA ORNL DAAC MODIS service: {e}"

    date_lookup = {modis_date: cal_date for cal_date, modis_date in in_range}
    records = []
    for entry in subset:
        raw_vals = entry.get("data", [])
        if not raw_vals:
            continue
        raw = raw_vals[0]
        if raw is None or raw <= MODIS_FILL_VALUE_THRESHOLD:
            continue  # invalid / cloud-masked pixel
        ndvi_val = round(raw * MODIS_SCALE_FACTOR, 4)
        cal_date = date_lookup.get(entry.get("modis_date"))
        if cal_date is None:
            continue
        records.append({"date": cal_date, "modis_date": entry["modis_date"], "ndvi": ndvi_val})

    if not records:
        return None, "MODIS returned no valid (cloud-free) NDVI pixels for this period. Try a wider date range."

    records.sort(key=lambda r: r["date"])
    return records, None


# =========================================================================
# SENTINEL-2 REAL DATA ENGINE (Copernicus Data Space Ecosystem / Sentinel Hub)
# Needs a FREE OAuth client (Client ID + Client Secret) from
# https://dataspace.copernicus.eu -> Dashboard -> User Settings -> OAuth clients
# Resolution: 10m | Revisit: ~5 days | Real, cloud-processed statistics API
# (no imagery download needed - the mean NDVI is computed server-side).
# =========================================================================
CDSE_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CDSE_STATS_URL = "https://sh.dataspace.copernicus.eu/statistics/v1"

SENTINEL2_NDVI_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B04", "B08", "SCL", "dataMask"] }],
    output: [
      { id: "data", bands: 1 },
      { id: "dataMask", bands: 1 }
    ]
  };
}
function evaluatePixel(samples) {
  let ndvi = (samples.B08 - samples.B04) / (samples.B08 + samples.B04);
  var valid = 1;
  if (samples.B08 + samples.B04 == 0) { valid = 0; }
  // exclude cloud shadow(3), water(6), cloud medium/high prob(8,9), cirrus(10)
  if ([3, 6, 8, 9, 10].indexOf(samples.SCL) !== -1) { valid = 0; }
  return {
    data: [ndvi],
    dataMask: [samples.dataMask * valid]
  };
}
"""


def cdse_get_token(client_id: str, client_secret: str) -> str:
    resp = requests.post(
        CDSE_TOKEN_URL,
        data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def cdse_fetch_sentinel2_stats(token: str, lat: float, lon: float, start_date: datetime.date, end_date: datetime.date):
    half = 0.0006  # ~130m box around the point in degrees (covers several 10m pixels)
    bbox = [lon - half, lat - half, lon + half, lat + half]
    body = {
        "input": {
            "bounds": {"bbox": bbox, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
            "data": [{"type": "sentinel-2-l2a", "dataFilter": {"maxCloudCoverage": 50}}],
        },
        "aggregation": {
            "timeRange": {
                "from": f"{start_date.isoformat()}T00:00:00Z",
                "to": f"{end_date.isoformat()}T23:59:59Z",
            },
            "aggregationInterval": {"of": "P5D"},
            "evalscript": SENTINEL2_NDVI_EVALSCRIPT,
            "resx": 10,
            "resy": 10,
        },
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(CDSE_STATS_URL, headers=headers, json=body, timeout=45)
    resp.raise_for_status()
    return resp.json()


def cdse_parse_stats_response(resp_json: dict):
    records = []
    for entry in resp_json.get("data", []):
        interval = entry.get("interval", {})
        from_str = interval.get("from")
        if not from_str:
            continue
        try:
            cal_date = datetime.datetime.fromisoformat(from_str.replace("Z", "+00:00")).date()
        except ValueError:
            continue
        outputs = entry.get("outputs", {})
        bands_dict = outputs.get("data", {}).get("bands", {})
        if not bands_dict:
            continue
        band_stats = next(iter(bands_dict.values())).get("stats", {})
        mean_val = band_stats.get("mean")
        sample_count = band_stats.get("sampleCount", 0)
        nodata_count = band_stats.get("noDataCount", 0)
        if mean_val is None or sample_count <= nodata_count:
            continue
        records.append({"date": cal_date, "ndvi": round(mean_val, 4)})
    records.sort(key=lambda r: r["date"])
    return records


def get_real_sentinel2_ndvi_timeseries(client_id: str, client_secret: str, lat: float, lon: float,
                                         start_date: datetime.date, end_date: datetime.date):
    """Returns (records, error_message)."""
    if not client_id or not client_secret:
        return None, ("Sentinel-2 needs a free Copernicus Data Space Ecosystem OAuth client. "
                       "Sign up at dataspace.copernicus.eu, go to Dashboard → User Settings → OAuth clients, "
                       "create one, then paste the Client ID / Secret in the sidebar.")
    try:
        token = cdse_get_token(client_id, client_secret)
    except requests.exceptions.RequestException as e:
        return None, f"Copernicus authentication failed (check your Client ID/Secret): {e}"

    try:
        resp_json = cdse_fetch_sentinel2_stats(token, lat, lon, start_date, end_date)
    except requests.exceptions.RequestException as e:
        return None, f"Copernicus Sentinel-2 request failed: {e}"

    try:
        records = cdse_parse_stats_response(resp_json)
    except Exception as e:
        return None, f"Could not parse Sentinel-2 response: {e}"

    if not records:
        return None, "No cloud-free Sentinel-2 NDVI data found for this location/period. Try a wider date range."

    return records, None


def classify_ndvi_stress(avg_ndvi: float):
    """Simple, transparent NDVI thresholds for cropland vegetation vigor."""
    if avg_ndvi >= 0.55:
        return "healthy"
    elif avg_ndvi >= 0.30:
        return "moderate_stress"
    else:
        return "severe_stress"


# --- EXTENDED MULTI-LANGUAGE TRANSLATION DICTIONARY SYSTEM ---
LANG_DATA = {
    "English": {
        "title": "🌾 Khetify - Real-time Satellite Diagnostics",
        "subtitle": "Enter coordinates or **click anywhere directly on the map** to run live multi-spectral analysis on adjacent fields.",
        "sidebar_title": "📍 Field Coordinates",
        "lat": "Latitude",
        "lon": "Longitude",
        "field_size_label": "🌱 Field Size (Acres)",
        "sat_config": "🛰️ Satellite Source Configuration",
        "sat_select": "Select Target Satellite:",
        "date_range_heading": "📅 Analysis Date Range",
        "start_date": "Start Date",
        "end_date": "End Date",
        "date_range_caption": "MODIS uses 16-day composites — pick a range of at least a few weeks for best results.",
        "date_error": "⚠️ Start date must be before end date.",
        "btn_run": "⚙️ Run Satellite Diagnostics",
        "results_heading": "📊 Satellite Analysis Results",
        "map_heading": "🗺️ Precision Field Mapping",
        "metrics_heading": "📈 Core Diagnostics Metrics",
        "active_target": "Active Coordinates Target",
        "size": "Size",
        "acres": "Acres",
        "period": "Period",
        "real_data_badge": "🟢 REAL satellite data — NASA MODIS (ORNL DAAC), MOD13Q1, 250m 16-day NDVI",
        "real_data_badge_s2": "🟢 REAL satellite data — Copernicus Sentinel-2 L2A, 10m resolution, ~5-day revisit (cloud-filtered).",
        "simulated_data_badge": "🟡 SIMULATED demo data — real-time Landsat 9 / PlanetScope integration requires a paid provider API key (USGS M2M or Planet Labs), or a heavier GDAL/rasterio setup.",
        "modis_fetching": "Fetching live MODIS satellite data from NASA ORNL DAAC…",
        "sentinel2_fetching": "Fetching live Sentinel-2 satellite data from Copernicus Data Space…",
        "modis_error_prefix": "⚠️ MODIS data fetch failed:",
        "ndvi_trend_heading": "📉 Real NDVI Trend (MODIS Composites)",
        "ndvi_latest": "Latest NDVI Reading",
        "ndvi_avg": "Average NDVI (Selected Period)",
        "status_healthy": "✅ Field Status: HEALTHY",
        "status_moderate_stress": "🟠 Field Status: MODERATE VEGETATION STRESS",
        "status_severe_stress": "🚨 Field Status: SEVERE VEGETATION STRESS",
        "status_infected": "🚨 Field Status: ANOMALY DETECTED (INFECTED)",
        "ndvi": "NDVI (Vegetation Index)",
        "moisture": "Soil Moisture Profile",
        "moisture_proxy": "Estimated Soil Moisture (NDVI-based proxy, not directly measured)",
        "stable_veg": "Stable Vegetation",
        "optimal_range": "Optimal Range",
        "stress_drop": "Critical Stress Drop",
        "economic_heading": "💰 Estimated Field Economic Value",
        "economic_loss_heading": "💰 Projected Economic Impact",
        "market_value": "Est. Total Produce Market Value",
        "target_attained": "100% Target Attained",
        "value_caption": "Value metrics use your entered acreage and an assumed regional price per acre — not a live market feed.",
        "risk_value": "Risk Exposure Value (Potential Loss)",
        "yield_vuln": "Crop Yield Vulnerability",
        "spray_savings": "Targeted Spray Cost Savings",
        "chem_reduction": "+90% Chemical Reduction",
        "alert_heading": "📱 Localized Actionable Outbound Alert",
        "broadcast_title": "Automated Broadcast Content",
        "remedy_heading": "💊 AI Targeted Remedy & Action Plan",
        "info_sidebar": "👈 Enter coordinates or run initial diagnostic to activate the interactive live matrix view.",
        "disease_detected": "⚠️ Fungal Leaf Rust detected. Action Required.",
        "remedy_text": "👉 **Recommendation:** Apply *Tebuconazole* or *Propiconazole* fungicide spray **ONLY inside the identified red circle zone**. Do not spray the whole field. Ensure localized application within 48 hours to prevent spread.",
        "general_remedy_heading": "🔎 Field Vegetation Stress — Recommended Action",
        "general_remedy_text": "MODIS NDVI shows below-normal vegetation vigor for this field over the selected period. This can be caused by several factors — water stress, nutrient deficiency, pest pressure, or disease — and satellite NDVI alone cannot tell them apart. **Recommendation:** physically scout the field before applying any chemical treatment. If you have access to higher-resolution imagery (Sentinel-2/PlanetScope) or a field agronomist, use them to confirm the specific cause.",
        "download_heading": "📥 Export Report",
        "download_excel": "⬇️ Download Report as Excel (.xlsx)",
        "download_caption": "Includes coordinates, satellite source, selected date range, and all diagnostic metrics. When using MODIS, the full real NDVI time series is included on a second sheet.",
        "no_data_available": "No results to show yet for this period/location."
    },
    "Urdu (اردو)": {
        "title": "🌾 کھیتی فائی - لائیو سیٹلائٹ تشخیصی نظام",
        "subtitle": "برائے مہربانی کوآرڈینیٹس درج کریں یا کھیت کا لائیو تجزیہ دیکھنے کے لیے **نقشے پر کہیں بھی کلک کریں**۔",
        "sidebar_title": "📍 کھیت کے کوآرڈینیٹس",
        "lat": "عرض بلد (Latitude)",
        "lon": "طول بلد (Longitude)",
        "field_size_label": "🌱 کھیت کا رقبہ (ایکڑ)",
        "sat_config": "🛰️ سیٹلائٹ کنفیگریشن",
        "sat_select": "ٹارگٹ سیٹلائٹ منتخب کریں:",
        "date_range_heading": "📅 تجزیہ کے لیے تاریخوں کا انتخاب",
        "start_date": "شروع کی تاریخ",
        "end_date": "آخری تاریخ",
        "date_range_caption": "MODIS ڈیٹا 16 دن کی بنیاد پر جمع ہوتا ہے — بہتر نتائج کے لیے کم از کم چند ہفتوں کی مدت منتخب کریں۔",
        "date_error": "⚠️ شروع کی تاریخ آخری تاریخ سے پہلے ہونی چاہیے۔",
        "btn_run": "⚙️ سیٹلائٹ ٹیسٹ شروع کریں",
        "results_heading": "📊 سیٹلائٹ تجزیہ کے نتائج",
        "map_heading": "🗺️ درست فیلڈ میپنگ (نقشہ)",
        "metrics_heading": "📈 بنیادی تشخیصی انڈیکس",
        "active_target": "موجودہ فعال کوآرڈینیٹس",
        "size": "کھیت کا سائز",
        "acres": "ایکڑ",
        "period": "مدت",
        "real_data_badge": "🟢 حقیقی سیٹلائٹ ڈیٹا — NASA MODIS (ORNL DAAC)، 250 میٹر، 16 روزہ NDVI",
        "real_data_badge_s2": "🟢 حقیقی سیٹلائٹ ڈیٹا — Copernicus Sentinel-2، 10 میٹر ریزولوشن، تقریباً ہر 5 دن بعد اپڈیٹ۔",
        "simulated_data_badge": "🟡 نمائشی (سمولیٹڈ) ڈیٹا — Landsat 9 / PlanetScope کے حقیقی ڈیٹا کے لیے پیڈ API کلید یا اضافی سیٹ اپ درکار ہے۔",
        "modis_fetching": "NASA ORNL DAAC سے لائیو MODIS ڈیٹا حاصل کیا جا رہا ہے…",
        "sentinel2_fetching": "Copernicus Data Space سے لائیو Sentinel-2 ڈیٹا حاصل کیا جا رہا ہے…",
        "modis_error_prefix": "⚠️ MODIS ڈیٹا حاصل کرنے میں ناکامی:",
        "ndvi_trend_heading": "📉 حقیقی NDVI رجحان (MODIS ڈیٹا)",
        "ndvi_latest": "تازہ ترین NDVI ریڈنگ",
        "ndvi_avg": "اوسط NDVI (منتخب مدت)",
        "status_healthy": "✅ کھیت کی حالت: صحت مند (HEALTHY)",
        "status_moderate_stress": "🟠 کھیت کی حالت: درمیانہ دباؤ",
        "status_severe_stress": "🚨 کھیت کی حالت: شدید دباؤ",
        "status_infected": "🚨 کھیت کی حالت: بیماری کا انکشاف (INFECTED)",
        "ndvi": "این ڈی وی آئی (سبزے کی مقدار)",
        "moisture": "مٹی میں نمی کا تناسب",
        "moisture_proxy": "تخمینی مٹی کی نمی (NDVI پر مبنی تخمینہ، براہ راست ناپی نہیں گئی)",
        "stable_veg": "بہتر سبزہ اور فصل",
        "optimal_range": "مناسب ترین نمی",
        "stress_drop": "فصل پر شدید دباؤ",
        "economic_heading": "💰 کھیت کی متوقع معاشی قیمت",
        "economic_loss_heading": "💰 متوقع معاشی نقصان کا تخمینہ",
        "market_value": "فصل کی کل متوقع مارکیٹ ویلیو",
        "target_attained": "100% ہدف حاصل",
        "value_caption": "یہ اعداد آپ کے درج کردہ رقبے اور فرضی علاقائی قیمت پر مبنی ہیں — یہ لائیو مارکیٹ ڈیٹا نہیں ہے۔",
        "risk_value": "خطرہ کی زد میں موجود مالیت (ممکنہ نقصان)",
        "yield_vuln": "پیداوار کو شدید خطرہ",
        "spray_savings": "ٹارگٹڈ اسپرے سے ہونے والی بچت",
        "chem_reduction": "ادویات کے خرچے میں 90 فیصد کمی",
        "alert_heading": "📱 مقامی کسان کے لیے الرٹ میسج",
        "broadcast_title": "خودکار ایس ایم ایس پیغام",
        "remedy_heading": "💊 آرٹیفیشل انٹیلیجنس تجویز اور طریقہ علاج",
        "info_sidebar": "👈 لائیو میٹرکس اور نقشہ فعال کرنے کے لیے کوآرڈینیٹس درج کریں یا ٹیسٹ کا بٹن دبائیں۔",
        "disease_detected": "⚠️ پودوں میں فنگل لیف رسٹ (کنگی کی بیماری) پائی گئی ہے۔",
        "remedy_text": "👉 **تجویز کردہ طریقہ علاج:** فنگس کش دوا *Tebuconazole* یا *Propiconazole* کا اسپرے **صرف نقشے پر نشان زدہ سرخ دائرے کے اندر کریں**۔ پورے کھیت میں اسپرے کرنے کی بالکل ضرورت نہیں ہے۔ اگلے 48 گھنٹوں میں اسپرے مکمل کریں تاکہ بیماری مزید نہ پھیلے۔",
        "general_remedy_heading": "🔎 کھیت میں سبزے کا دباؤ — تجویز کردہ اقدام",
        "general_remedy_text": "منتخب مدت میں MODIS NDVI اس کھیت میں معمول سے کم سبزہ ظاہر کر رہا ہے۔ اس کی کئی وجوہات ہو سکتی ہیں — پانی کی کمی، غذائی اجزاء کی کمی، کیڑوں کا حملہ، یا بیماری — اور صرف سیٹلائٹ NDVI سے ان کی تفریق ممکن نہیں۔ **تجویز:** کوئی بھی کیمیکل استعمال کرنے سے پہلے کھیت کا خود معائنہ کریں، یا مزید تفصیلی تصاویر (Sentinel-2/PlanetScope) یا ماہر زراعت سے مدد لیں۔",
        "download_heading": "📥 رپورٹ ڈاؤن لوڈ کریں",
        "download_excel": "⬇️ رپورٹ ایکسل (.xlsx) میں ڈاؤن لوڈ کریں",
        "download_caption": "اس فائل میں کوآرڈینیٹس، سیٹلائٹ ذریعہ، منتخب کردہ تاریخیں، اور تمام تشخیصی اعداد و شمار شامل ہیں۔ MODIS استعمال کرنے پر مکمل حقیقی NDVI ٹائم سیریز دوسری شیٹ میں شامل ہوگی۔",
        "no_data_available": "اس مدت/مقام کے لیے ابھی کوئی نتیجہ دستیاب نہیں۔"
    }
}

for lang in ["Spanish (Español)", "Portuguese (Português)", "Punjabi (پنجابی)", "Arabic (العربية)", "Hindi (हिंदी)"]:
    if lang not in LANG_DATA:
        LANG_DATA[lang] = LANG_DATA["English"]

# --- GLOBAL LANGUAGE SELECTOR ---
selected_lang = st.selectbox(
    "🌐 Select System Language / زبان منتخب کریں / Seleccione o idioma:",
    ["English", "Urdu (اردو)", "Spanish (Español)", "Portuguese (Português)", "Punjabi (پنجابی)", "Arabic (العربية)", "Hindi (हिंदी)"]
)

T = LANG_DATA[selected_lang]

st.title(T["title"])
st.markdown(T["subtitle"])

# --- SESSION STATE INITIALIZATION ---
if "clicked" not in st.session_state:
    st.session_state.clicked = False
if "lat" not in st.session_state:
    st.session_state.lat = 31.1853
if "lon" not in st.session_state:
    st.session_state.lon = 73.9621

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header(T["sidebar_title"])

input_lat = st.sidebar.number_input(T["lat"], value=st.session_state.lat, format="%.4f")
input_lon = st.sidebar.number_input(T["lon"], value=st.session_state.lon, format="%.4f")

if input_lat != st.session_state.lat and input_lat != 31.1853:
    st.session_state.lat = input_lat
if input_lon != st.session_state.lon and input_lon != 73.9621:
    st.session_state.lon = input_lon

st.sidebar.markdown("---")
field_acres = st.sidebar.number_input(T["field_size_label"], min_value=0.5, value=5.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.header(T["sat_config"])
satellite_source = st.sidebar.selectbox(
    T["sat_select"],
    [
        "MODIS (Terra/Aqua - REAL Data, 250m, no signup needed)",
        "Sentinel-2 (REAL Data via Copernicus, 10m - needs free API key)",
        "Landsat 9 (Thermal & Optical) [Simulated Demo]",
        "PlanetScope (High-Res Daily) [Simulated Demo]",
    ]
)
is_modis = satellite_source.startswith("MODIS")
is_sentinel2 = satellite_source.startswith("Sentinel-2")

cdse_client_id = None
cdse_client_secret = None
if is_sentinel2:
    st.sidebar.markdown("---")
    st.sidebar.caption(
        "🔑 Free Copernicus Data Space credentials needed. "
        "Sign up at dataspace.copernicus.eu → Dashboard → User Settings → OAuth clients."
    )
    cdse_client_id = st.sidebar.text_input("Copernicus Client ID", type="password", key="cdse_client_id")
    cdse_client_secret = st.sidebar.text_input("Copernicus Client Secret", type="password", key="cdse_client_secret")

# --- DATE RANGE SELECTION ---
st.sidebar.markdown("---")
st.sidebar.header(T["date_range_heading"])

default_end_date = datetime.date.today()
default_start_date = default_end_date - datetime.timedelta(days=90)

start_date = st.sidebar.date_input(
    T["start_date"], value=default_start_date, max_value=default_end_date, key="start_date_input"
)
end_date = st.sidebar.date_input(
    T["end_date"], value=default_end_date, max_value=default_end_date, key="end_date_input"
)

date_range_valid = start_date <= end_date
if not date_range_valid:
    st.sidebar.error(T["date_error"])

if is_modis:
    st.sidebar.caption(T["date_range_caption"])

st.sidebar.markdown("---")
run_analysis = st.sidebar.button(T["btn_run"], type="primary", disabled=not date_range_valid)

if run_analysis:
    st.session_state.clicked = True

# --- CURRENT TARGET ---
current_lat = st.session_state.lat
current_lon = st.session_state.lon

USD_RATE = 278.0

# =========================================================================
# MAIN RENDER
# =========================================================================
if st.session_state.clicked:
    st.subheader(f"{T['results_heading']} ({satellite_source})")

    # ---------------------------------------------------------------
    # 1) Compute NDVI / status either from REAL MODIS data or SIMULATED
    # ---------------------------------------------------------------
    real_records = None
    real_error = None
    is_real_data = False
    data_source_label = "SIMULATED / DEMO"

    if is_modis:
        st.info(T["real_data_badge"])
        with st.spinner(T["modis_fetching"]):
            real_records, real_error = get_real_modis_ndvi_timeseries(current_lat, current_lon, start_date, end_date)
        data_source_label = "REAL - NASA MODIS (ORNL DAAC)"
        if real_error:
            st.error(f"{T['modis_error_prefix']} {real_error}")
    elif is_sentinel2:
        st.info(T["real_data_badge_s2"])
        with st.spinner(T["sentinel2_fetching"]):
            real_records, real_error = get_real_sentinel2_ndvi_timeseries(
                cdse_client_id, cdse_client_secret, current_lat, current_lon, start_date, end_date
            )
        data_source_label = "REAL - Copernicus Sentinel-2"
        if real_error:
            st.error(f"{T['modis_error_prefix']} {real_error}")
    else:
        st.warning(T["simulated_data_badge"])

    if real_records:
        is_real_data = True
        avg_ndvi = sum(r["ndvi"] for r in real_records) / len(real_records)
        latest_ndvi = real_records[-1]["ndvi"]
        calc_ndvi = round(latest_ndvi, 2)
        stress_level = classify_ndvi_stress(avg_ndvi)
        # NDVI-based soil moisture proxy (rough monotonic estimate, NOT measured)
        calc_moisture = int(min(95, max(5, round(20 + avg_ndvi * 70))))

    if not is_real_data:
        # --- SIMULATED / DEMO ENGINE (unchanged mock logic, clearly labeled) ---
        hash_seed = f"{current_lat:.4f},{current_lon:.4f},{satellite_source},{start_date},{end_date}"
        coord_hash = int(hashlib.md5(hash_seed.encode()).hexdigest(), 16)
        stress_level = "severe_stress" if (coord_hash % 2) == 1 else "healthy"
        base_modifier = (coord_hash % 15) / 100.0

        if stress_level == "healthy":
            calc_ndvi = round(0.72 + (base_modifier * 0.5), 2)
            if calc_ndvi > 0.88: calc_ndvi = 0.85
            calc_moisture = int(58 + (coord_hash % 12))
        else:
            calc_ndvi = round(0.38 - (base_modifier * 0.3), 2)
            if calc_ndvi < 0.21: calc_ndvi = 0.25
            calc_moisture = int(32 + (coord_hash % 10))

    # Economic calc (uses user-entered acreage, not hash-random)
    if stress_level == "healthy":
        calc_market_value = int(field_acres * 350000)
        calc_market_value_usd = round(calc_market_value / USD_RATE, 2)
    else:
        calc_total_value = int(field_acres * 340000)
        calc_risk_exposure = int(calc_total_value * (0.3 + (0.05 if stress_level == "moderate_stress" else 0.15)))
        calc_risk_exposure_usd = round(calc_risk_exposure / USD_RATE, 2)
        calc_savings = int(field_acres * 28000)
        calc_savings_usd = round(calc_savings / USD_RATE, 2)

    # ---------------------------------------------------------------
    # 2) Map + Metrics
    # ---------------------------------------------------------------
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(f"### {T['map_heading']}")
        google_satellite_url = "https://mt1.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}"
        m = folium.Map(location=[current_lat, current_lon], zoom_start=16, tiles=google_satellite_url, attr="Google Satellite Imagery")

        if stress_level == "healthy":
            folium.Circle(radius=110, location=[current_lat, current_lon], color="#00FF00", fill=True,
                          fill_color="#00FF00", fill_opacity=0.35, popup="Healthy Vegetation Target Area").add_to(m)
        elif is_real_data:
            # Real satellite reading: show a field-level indicator, NOT a fake pinpoint
            folium.Circle(radius=125, location=[current_lat, current_lon], color="#FFA500", fill=True,
                          fill_color="#FFA500", fill_opacity=0.35,
                          popup=f"{data_source_label}: field-level vegetation stress (not a pinpointed spot)").add_to(m)
        else:
            infected_lat = current_lat + 0.0004
            infected_lon = current_lon + 0.0004
            folium.Circle(radius=65, location=[infected_lat, infected_lon], color="#FF0000", fill=True,
                          fill_color="#FF0000", fill_opacity=0.7, popup="⚠️ Infection Anomaly Area Spot!").add_to(m)

        map_output = st_folium(m, width=800, height=650, key="khetify_fixed_map_layer")

        if map_output and "last_clicked" in map_output and map_output["last_clicked"] is not None:
            clicked_data = map_output["last_clicked"]
            clicked_lat = round(clicked_data["lat"], 4)
            clicked_lon = round(clicked_data["lng"], 4)
            if clicked_lat != current_lat or clicked_lon != current_lon:
                st.session_state.lat = clicked_lat
                st.session_state.lon = clicked_lon
                st.rerun()

        # Real NDVI trend chart (only when we actually have real satellite data)
        if is_real_data:
            st.markdown(f"### {T['ndvi_trend_heading']} — {data_source_label}")
            df_trend = pd.DataFrame(real_records)[["date", "ndvi"]].set_index("date")
            st.line_chart(df_trend)

    with col2:
        st.markdown(f"### {T['metrics_heading']}")
        st.caption(f"{T['active_target']}: {current_lat:.4f}, {current_lon:.4f} | {T['size']}: {field_acres} {T['acres']}")
        st.caption(f"{T['period']}: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}")

        if stress_level == "healthy":
            st.success(T["status_healthy"])
        elif stress_level == "moderate_stress":
            st.warning(T["status_moderate_stress"])
        elif is_real_data:
            st.error(T["status_severe_stress"])
        else:
            st.error(T["status_infected"])

        if is_real_data:
            st.metric(label=T["ndvi_latest"], value=f"{calc_ndvi}")
            st.metric(label=T["ndvi_avg"], value=f"{round(avg_ndvi, 2)}")
        else:
            delta_label = T["stable_veg"] if stress_level == "healthy" else T["stress_drop"]
            st.metric(label=T["ndvi"], value=f"{calc_ndvi}", delta=delta_label,
                      delta_color="normal" if stress_level == "healthy" else "inverse")

        moisture_label = T["moisture_proxy"] if (is_real_data) else T["moisture"]
        moisture_delta = T["optimal_range"] if stress_level == "healthy" else T["stress_drop"]
        st.metric(label=moisture_label, value=f"{calc_moisture}%", delta=moisture_delta,
                  delta_color="normal" if stress_level == "healthy" else "inverse")

        st.markdown("---")
        if stress_level == "healthy":
            st.markdown(f"### {T['economic_heading']}")
            st.metric(label=T["market_value"], value=f"PKR {calc_market_value:,}", delta=f"${calc_market_value_usd:,} USD")
            st.caption(T["value_caption"])
        else:
            st.markdown(f"### {T['economic_loss_heading']}")
            st.metric(label=T["risk_value"], value=f"PKR {calc_risk_exposure:,}",
                      delta=f"${calc_risk_exposure_usd:,} USD {T['yield_vuln']}", delta_color="inverse")
            st.metric(label=T["spray_savings"], value=f"PKR {calc_savings:,}",
                      delta=f"${calc_savings_usd:,} USD ({T['chem_reduction']})")
            st.caption(T["value_caption"])

    # ---------------------------------------------------------------
    # 3) Excel Export
    # ---------------------------------------------------------------
    st.markdown("---")
    st.markdown(f"### {T['download_heading']}")

    report_data = {
        "Latitude": [current_lat],
        "Longitude": [current_lon],
        "Satellite Source": [satellite_source],
        "Data Type": [data_source_label],
        "Start Date": [start_date.strftime("%Y-%m-%d")],
        "End Date": [end_date.strftime("%Y-%m-%d")],
        "Field Size (Acres)": [field_acres],
        "Field Status": [stress_level],
        "NDVI": [calc_ndvi],
        "Soil Moisture (%)": [calc_moisture],
    }
    if is_real_data:
        report_data["Average NDVI (Period)"] = [round(avg_ndvi, 4)]

    if stress_level == "healthy":
        report_data["Market Value (PKR)"] = [calc_market_value]
        report_data["Market Value (USD)"] = [calc_market_value_usd]
    else:
        report_data["Risk Exposure (PKR)"] = [calc_risk_exposure]
        report_data["Risk Exposure (USD)"] = [calc_risk_exposure_usd]
        report_data["Spray Cost Savings (PKR)"] = [calc_savings]
        report_data["Spray Cost Savings (USD)"] = [calc_savings_usd]

    df_report = pd.DataFrame(report_data)

    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df_report.to_excel(writer, index=False, sheet_name="Khetify_Report")
        ws = writer.sheets["Khetify_Report"]
        for i, col in enumerate(df_report.columns):
            max_len = max(df_report[col].astype(str).map(len).max(), len(col)) + 2
            ws.column_dimensions[chr(65 + i)].width = max_len

        if is_real_data:
            df_ts_full = pd.DataFrame(real_records)
            if "modis_date" in df_ts_full.columns:
                df_ts = df_ts_full[["date", "modis_date", "ndvi"]]
                df_ts.columns = ["Calendar Date", "MODIS Composite ID", "NDVI"]
            else:
                df_ts = df_ts_full[["date", "ndvi"]]
                df_ts.columns = ["Calendar Date", "NDVI"]
            sheet_name = "NDVI_Timeseries"
            df_ts.to_excel(writer, index=False, sheet_name=sheet_name)
            ws2 = writer.sheets[sheet_name]
            for i, col in enumerate(df_ts.columns):
                max_len = max(df_ts[col].astype(str).map(len).max(), len(col)) + 2
                ws2.column_dimensions[chr(65 + i)].width = max_len

    excel_buffer.seek(0)
    file_name = f"khetify_report_{current_lat:.4f}_{current_lon:.4f}_{start_date}_{end_date}.xlsx"

    st.download_button(
        label=T["download_excel"], data=excel_buffer, file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.caption(T["download_caption"])

    # ---------------------------------------------------------------
    # 4) Remedy / Alert Panels
    # ---------------------------------------------------------------
    if stress_level != "healthy":
        st.markdown("---")
        if is_real_data:
            # Real data: give a general, responsible recommendation — no fake diagnosis
            st.markdown(f"### {T['general_remedy_heading']}")
            st.warning(T["general_remedy_text"])
        else:
            remedy_col, alert_col = st.columns(2)
            with remedy_col:
                st.markdown(f"### {T['remedy_heading']}")
                st.warning(T["disease_detected"])
                st.markdown(T["remedy_text"])
            with alert_col:
                st.markdown(f"### {T['alert_heading']}")
                infected_lat_sms = current_lat + 0.0004
                infected_lon_sms = current_lon + 0.0004
                sms_texts = {
                    "English": f"⚠️ Khetify Alert:\nDisease detected at coordinates ({infected_lat_sms:.4f}, {infected_lon_sms:.4f}). Apply targeted pesticide inside the marked red circle to save input costs.",
                    "Urdu (اردو)": f"⚠️ کھیتی فائی الرٹ:\nآپکے کھیت کے کوآرڈینیٹس ({infected_lat_sms:.4f}, {infected_lon_sms:.4f}) پر بیماری ملی ہے۔ نقصان سے بچنے کے لیے صرف نشان زدہ سرخ دائرے کے اندر اسپرے کریں۔"
                }
                sms_val = sms_texts.get(selected_lang, sms_texts["English"])
                st.text_area(f"{T['broadcast_title']}:", value=sms_val, height=130)
else:
    st.info(T["info_sidebar"])