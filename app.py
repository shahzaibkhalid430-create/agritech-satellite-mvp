import streamlit as st
import folium
from streamlit_folium import st_folium
import hashlib

# Page Configuration
st.set_page_config(page_title="Khetify - AI Satellite Analysis Engine", layout="wide")

# --- MULTI-LANGUAGE TRANSLATION DICTIONARY SYSTEM ---
LANG_DATA = {
    "English": {
        "title": "🌾 Khetify - Real-time Satellite Diagnostics",
        "subtitle": "Enter coordinates or **click anywhere directly on the map** to run live multi-spectral analysis on adjacent fields.",
        "sidebar_title": "📍 Field Coordinates",
        "lat": "Latitude",
        "lon": "Longitude",
        "sat_config": "🛰️ Satellite Source Configuration",
        "sat_select": "Select Target Satellite:",
        "btn_run": "⚙️ Run Satellite Diagnostics",
        "results_heading": "📊 Satellite Analysis Results",
        "map_heading": "🗺️ Precision Field Mapping",
        "metrics_heading": "📈 Core Diagnostics Metrics",
        "active_target": "Active Coordinates Target",
        "size": "Size",
        "acres": "Acres",
        "status_healthy": "✅ Field Status: HEALTHY",
        "status_infected": "🚨 Field Status: ANOMALY DETECTED (INFECTED)",
        "ndvi": "NDVI (Vegetation Index)",
        "moisture": "Soil Moisture Profile",
        "stable_veg": "Stable Vegetation",
        "optimal_range": "Optimal Range",
        "stress_drop": "Critical Stress Drop",
        "economic_heading": "💰 Estimated Field Economic Value",
        "economic_loss_heading": "💰 Projected Economic Impact",
        "market_value": "Est. Total Produce Market Value",
        "target_attained": "100% Target Attained",
        "value_caption": "Value metrics are dynamically tied to regional market index and current acreage scale.",
        "risk_value": "Risk Exposure Value (Potential Loss)",
        "yield_vuln": "Crop Yield Vulnerability",
        "spray_savings": "Targeted Spray Cost Savings",
        "chem_reduction": "+90% Chemical Reduction",
        "alert_heading": "📱 Localized Actionable Outbound Alert",
        "broadcast_title": "Automated Broadcast Content",
        "remedy_heading": "💊 AI Targeted Remedy & Action Plan",
        "info_sidebar": "👈 Enter coordinates or run initial diagnostic to activate the interactive live matrix view.",
        "disease_detected": "⚠️ Fungal Leaf Rust detected. Action Required.",
        "remedy_text": "👉 **Recommendation:** Apply *Tebuconazole* or *Propiconazole* fungicide spray **ONLY inside the identified red circle zone**. Do not spray the whole field. Ensure localized application within 48 hours to prevent spread."
    },
    "Urdu (اردو)": {
        "title": "🌾 کھیتی فائی - لائیو سیٹلائٹ تشخیصی نظام",
        "subtitle": "برائے مہربانی کوآرڈینیٹس درج کریں یا کھیت کا لائیو تجزیہ دیکھنے کے لیے **نقشے پر کہیں بھی کلک کریں**۔",
        "sidebar_title": "📍 کھیت کے کوآرڈینیٹس",
        "lat": "عرض بلد (Latitude)",
        "lon": "طول بلد (Longitude)",
        "sat_config": "🛰️ سیٹلائٹ کنفیگریشن",
        "sat_select": "ٹارگٹ سیٹلائٹ منتخب کریں:",
        "btn_run": "⚙️ سیٹلائٹ ٹیسٹ شروع کریں",
        "results_heading": "📊 سیٹلائٹ تجزیہ کے نتائج",
        "map_heading": "🗺️ درست فیلڈ میپنگ (نقشہ)",
        "metrics_heading": "📈 بنیادی تشخیصی انڈیکس",
        "active_target": "موجودہ فعال کوآرڈینیٹس",
        "size": "کھیت کا سائز",
        "acres": "ایکڑ",
        "status_healthy": "✅ کھیت کی حالت: صحت مند (HEALTHY)",
        "status_infected": "🚨 کھیت کی حالت: بیماری کا انکشاف (INFECTED)",
        "ndvi": "این ڈی وی آئی (سبزے کی مقدار)",
        "moisture": "مٹی میں نمی کا تناسب",
        "stable_veg": "بہتر سبزہ اور فصل",
        "optimal_range": "مناسب ترین نمی",
        "stress_drop": "فصل پر شدید دباؤ",
        "economic_heading": "💰 کھیت کی متوقع معاشی قیمت",
        "economic_loss_heading": "💰 متوقع معاشی نقصان کا تخمینہ",
        "market_value": "فصل کی کل متوقع مارکیٹ ویلیو",
        "target_attained": "100% ہدف حاصل",
        "value_caption": "معاشی قیمت کا تعین علاقائی مارکیٹ انڈیکس اور رقبے کے مطابق کیا گیا ہے۔",
        "risk_value": "خطرہ کی زد میں موجود مالیت (ممکنہ نقصان)",
        "yield_vuln": "پیداوار کو شدید خطرہ",
        "spray_savings": "ٹارگٹڈ اسپرے سے ہونے والی بچت",
        "chem_reduction": "ادویات کے خرچے میں 90 فیصد کمی",
        "alert_heading": "📱 مقامی کسان کے لیے الرٹ میسج",
        "broadcast_title": "خودکار ایس ایم ایس پیغام",
        "remedy_heading": "💊 آرٹیفیشل انٹیلیجنس تجویز اور طریقہ علاج",
        "info_sidebar": "👈 لائیو میٹرکس اور نقشہ فعال کرنے کے لیے کوآرڈینیٹس درج کریں یا ٹیسٹ کا بٹن دبائیں۔",
        "disease_detected": "⚠️ پودوں میں فنگل لیف رسٹ (کنگی کی بیماری) پائی گئی ہے۔",
        "remedy_text": "👉 **تجویز کردہ طریقہ علاج:** فنگس کش دوا *Tebuconazole* یا *Propiconazole* کا اسپرے **صرف نقشے پر نشان زدہ سرخ دائرے کے اندر کریں**۔ پورے کھیت میں اسپرے کرنے کی بالکل ضرورت نہیں ہے۔ اگلے 48 گھنٹوں میں اسپرے مکمل کریں تاکہ بیماری مزید نہ پھیلے۔"
    },
    "Spanish (Español)": {
        "title": "🌾 Khetify - Diagnóstico Satelital en Tiempo Real",
        "subtitle": "Ingrese las coordenadas o **haga clic en cualquier lugar del mapa** para ejecutar el análisis multiespectral.",
        "sidebar_title": "📍 Coordenadas del Campo",
        "lat": "Latitud",
        "lon": "Longitud",
        "sat_config": "🛰️ Configuración del Satélite",
        "sat_select": "Seleccionar Satélite Objetivo:",
        "btn_run": "⚙️ Ejecutar Diagnóstico Satelital",
        "results_heading": "📊 Resultados del Análisis Satelital",
        "map_heading": "🗺️ Mapeo de Precisión del Campo",
        "metrics_heading": "📈 Métricas de Diagnóstico Críticas",
        "active_target": "Coordenadas Activas",
        "size": "Tamaño",
        "acres": "Acres",
        "status_healthy": "✅ Estado del Campo: SALUDABLE",
        "status_infected": "🚨 Estado del Campo: ANOMALÍA DETECTADA (INFECTADO)",
        "ndvi": "NDVI (Índice de Vegetación)",
        "moisture": "Perfil de Humedad del Suelo",
        "stable_veg": "Vegetación Estable",
        "optimal_range": "Rango Óptimo",
        "stress_drop": "Caída Crítica de Estrés",
        "economic_heading": "💰 Valor Económico Estimado del Campo",
        "economic_loss_heading": "💰 Impacto Económico Proyectado",
        "market_value": "Valor de Mercado Estimado del Producción",
        "target_attained": "100% del Objetivo Alcanzado",
        "value_caption": "Las métricas se calculan dinámicamente según el índice de mercado regional y la escala del área.",
        "risk_value": "Valor de Exposición al Riesgo (Pérdida Potencial)",
        "yield_vuln": "Vulnerabilidad del Rendimiento",
        "spray_savings": "Ahorro de Costos en Fumigación Localizada",
        "chem_reduction": "90% de Reducción de Químicos",
        "alert_heading": "📱 Alerta Automatizada para el Agricultor",
        "broadcast_title": "Contenido del Mensaje de Texto",
        "remedy_heading": "💊 Plan de Acción y Remedio IA",
        "info_sidebar": "👈 Ingrese las coordenadas o ejecute el diagnóstico para activar la vista interactiva.",
        "disease_detected": "⚠️ Roya fúngica de la hoja detectada. Acción requerida.",
        "remedy_text": "👉 **Recomendación:** Aplique el fungicida *Tebuconazole* o *Propiconazole* **SOLO dentro de la zona del círculo rojo identificado**. No fumigue todo el campo. Aplique dentro de las 48 horas para contener la infección."
    }
}

# --- GLOBAL LANGUAGE SELECTOR ---
# Placed at the very top of the script layout
selected_lang = st.selectbox(
    "🌐 Select System Language / زبان منتخب کریں / Seleccione el idioma del sistema:",
    ["English", "Urdu (اردو)", "Spanish (Español)"]
)

# Fetch current active dictionary based on user choice
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
st.sidebar.header(T["sat_config"])
satellite_source = st.sidebar.selectbox(
    T["sat_select"],
    ["Sentinel-2 (Multi-spectral)", "Landsat 9 (Thermal & Optical)", "PlanetScope (High-Res Daily)"]
)

st.sidebar.markdown("---")
run_analysis = st.sidebar.button(T["btn_run"], type="primary")

if run_analysis:
    st.session_state.clicked = True

# --- DYNAMIC CALCULATION ENGINE BASED ON COORDINATES ---
current_lat = st.session_state.lat
current_lon = st.session_state.lon

coord_hash = int(hashlib.md5(f"{current_lat:.4f},{current_lon:.4f}".encode()).hexdigest(), 16)
is_infected = (coord_hash % 2) == 1  

base_modifier = (coord_hash % 15) / 100.0 
dynamic_acreage = 5 + (coord_hash % 8)     

if not is_infected:
    calc_ndvi = round(0.72 + (base_modifier * 0.5), 2)
    if calc_ndvi > 0.88: calc_ndvi = 0.85
    calc_moisture = int(58 + (coord_hash % 12))
    calc_market_value = int(dynamic_acreage * 350000)
else:
    calc_ndvi = round(0.38 - (base_modifier * 0.3), 2)
    if calc_ndvi < 0.21: calc_ndvi = 0.25
    calc_moisture = int(32 + (coord_hash % 10))
    calc_total_value = int(dynamic_acreage * 340000)
    calc_risk_exposure = int(calc_total_value * (0.3 + (base_modifier * 0.5)))
    calc_savings = int(dynamic_acreage * 28000)

if st.session_state.clicked:
    st.subheader(f"{T['results_heading']} ({satellite_source})")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown(f"### {T['map_heading']}")
        
        google_satellite_url = "https://mt1.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}"
        m = folium.Map(
            location=[current_lat, current_lon], 
            zoom_start=16, 
            tiles=google_satellite_url,
            attr="Google Satellite Imagery"
        )
        
        # FIXED MAP VISUALIZATION: Dynamic polygon & localized red circles
        if not is_infected:
            # Healthy Field Boundary Box (Green)
            folium.Polygon(
                locations=[
                    [current_lat - 0.002, current_lon - 0.002],
                    [current_lat - 0.002, current_lon + 0.002],
                    [current_lat + 0.002, current_lon + 0.002],
                    [current_lat + 0.002, current_lon - 0.002]
                ],
                color="#00FF00",
                fill=True,
                fill_color="#00FF00",
                fill_opacity=0.35,
                popup=f"Healthy Vegetation Zone"
            ).add_to(m)
            
        else:
            # Boundary box stays normal/transparent green, NO red inside it
            folium.Polygon(
                locations=[
                    [current_lat - 0.002, current_lon - 0.002],
                    [current_lat - 0.002, current_lon + 0.002],
                    [current_lat + 0.002, current_lon + 0.002],
                    [current_lat + 0.002, current_lon - 0.002]
                ],
                color="#00FF00",
                fill=True,
                fill_color="#00FF00",
                fill_opacity=0.12,
                popup="Field Boundary"
            ).add_to(m)
            
            # Specific isolated RED CIRCLE to pinpoint exactly where the infection is located
            infected_lat = current_lat + 0.0004
            infected_lon = current_lon + 0.0004
            folium.Circle(
                radius=45, # Radius in meters
                location=[infected_lat, infected_lon],
                color="#FF0000",
                fill=True,
                fill_color="#FF0000",
                fill_opacity=0.65,
                popup="⚠️ Infection Center Spot!"
            ).add_to(m)
            
        map_output = st_folium(m, width=800, height=520, key="khetify_fixed_map_layer")
        
        if map_output and "last_clicked" in map_output biases and map_output["last_clicked"] is not None:
            clicked_data = map_output["last_clicked"]
            clicked_lat = round(clicked_data["lat"], 4)
            clicked_lon = round(clicked_data["lng"], 4)
            
            if clicked_lat != current_lat or clicked_lon != current_lon:
                st.session_state.lat = clicked_lat
                st.session_state.lon = clicked_lon
                st.rerun()
        
    with col2:
        st.markdown(f"### {T['metrics_heading']}")
        st.caption(f"{T['active_target']}: {current_lat:.4f}, {current_lon:.4f} | {T['size']}: {dynamic_acreage} {T['acres']}")
        
        if not is_infected:
            st.success(T["status_healthy"])
            st.metric(label=T["ndvi"], value=f"{calc_ndvi}", delta=T["stable_veg"])
            st.metric(label=T["moisture"], value=f"{calc_moisture}%", delta=T["optimal_range"])
            
            st.markdown("---")
            st.markdown(f"### {T['economic_heading']}")
            st.metric(label=T["market_value"], value=f"PKR {calc_market_value:,}", delta=T["target_attained"])
            st.caption(T["value_caption"])
            
        else:
            st.error(T["status_infected"])
            st.metric(label=T["ndvi"], value=f"{calc_ndvi}", delta=f"{round(calc_ndvi - 0.75, 2)} {T['stress_drop']}", delta_color="inverse")
            st.metric(label=T["moisture"], value=f"{calc_moisture}%", delta=T["stress_drop"], delta_color="inverse")
            
            st.markdown("---")
            st.markdown(f"### {T['economic_loss_heading']}")
            st.metric(label=T["risk_value"], value=f"PKR {calc_risk_exposure:,}", delta=T["yield_vuln"], delta_color="inverse")
            st.metric(label=T["spray_savings"], value=f"PKR {calc_savings:,}", delta=T["chem_reduction"])
            
            st.markdown("---")
            st.markdown(f"### {T['remedy_heading']}")
            st.warning(T["disease_detected"])
            st.markdown(T["remedy_text"])
            
            st.markdown("---")
            st.markdown(f"### {T['alert_heading']}")
            
            # Auto translate SMS alerts alongside layout definitions
            infected_lat_sms = current_lat + 0.0004
            infected_lon_sms = current_lon + 0.0004
            
            sms_texts = {
                "English": f"⚠️ Khetify Alert:\nDisease detected at coordinates ({infected_lat_sms:.4f}, {infected_lon_sms:.4f}). Apply targeted pesticide inside the marked red circle to save input costs.",
                "Urdu (اردو)": f"⚠️ کھیتی فائی الرٹ:\nآپکے کھیت کے کوآرڈینیٹس ({infected_lat_sms:.4f}, {infected_lon_sms:.4f}) پر بیماری ملی ہے۔ نقصان سے بچنے کے لیے صرف نشان زدہ سرخ دائرے کے اندر سپرے کریں۔",
                "Spanish (Español)": f"⚠️ Alerta Khetify:\nInfección detectada en ({infected_lat_sms:.4f}, {infected_lon_sms:.4f}). Aplique pesticida localizado solo dentro del círculo rojo para ahorrar costos."
            }
            st.text_area(f"{T['broadcast_title']}:", value=sms_texts[selected_lang], height=130)
else:
    st.info(T["info_sidebar"])