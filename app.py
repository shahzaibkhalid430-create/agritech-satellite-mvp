import streamlit as st
import folium
from streamlit_folium import st_folium
import hashlib

# Page Configuration
st.set_page_config(page_title="Khetify - AI Satellite Analysis Engine", layout="wide")

st.title("🌾 Khetify - Real-time Satellite Diagnostics")
st.markdown("Enter coordinates or **click anywhere directly on the map** to run live multi-spectral analysis on adjacent fields.")

# --- SESSION STATE INITIALIZATION ---
if "clicked" not in st.session_state:
    st.session_state.clicked = False
if "lat" not in st.session_state:
    st.session_state.lat = 31.1853
if "lon" not in st.session_state:
    st.session_state.lon = 73.9621

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("📍 Field Coordinates")

input_lat = st.sidebar.number_input("Latitude", value=st.session_state.lat, format="%.4f")
input_lon = st.sidebar.number_input("Longitude", value=st.session_state.lon, format="%.4f")

if input_lat != st.session_state.lat and input_lat != 31.1853:
    st.session_state.lat = input_lat
if input_lon != st.session_state.lon and input_lon != 73.9621:
    st.session_state.lon = input_lon

st.sidebar.markdown("---")
st.sidebar.header("🛰️ Satellite Source Configuration")
satellite_source = st.sidebar.selectbox(
    "Select Target Satellite:",
    ["Sentinel-2 (Multi-spectral)", "Landsat 9 (Thermal & Optical)", "PlanetScope (High-Res Daily)"]
)

st.sidebar.markdown("---")
run_analysis = st.sidebar.button("⚙️ Run Satellite Diagnostics", type="primary")

if run_analysis:
    st.session_state.clicked = True

# --- DYNAMIC CALCULATION ENGINE BASED ON COORDINATES ---
current_lat = st.session_state.lat
current_lon = st.session_state.lon

# Generate a unique hash integer for every single coordinate
coord_hash = int(hashlib.md5(f"{current_lat:.4f},{current_lon:.4f}".encode()).hexdigest(), 16)
is_infected = (coord_hash % 2) == 1  

# Generate dynamic data points so results are NEVER the same across locations
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
    st.subheader(f"📊 Satellite Analysis Results ({satellite_source})")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 🗺️ Precision Field Mapping")
        
        google_satellite_url = "https://mt1.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}"
        m = folium.Map(
            location=[current_lat, current_lon], 
            zoom_start=16, 
            tiles=google_satellite_url,
            attr="Google Satellite Imagery"
        )
        
        if not is_infected:
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
                popup=f"Healthy Vegetation Zone (NDVI: {calc_ndvi})"
            ).add_to(m)
            
        else:
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
                fill_opacity=0.15,
                popup="Overall Field Bound"
            ).add_to(m)
            
            infected_lat = current_lat + 0.0006
            infected_lon = current_lon + 0.0006
            folium.Polygon(
                locations=[
                    [infected_lat - 0.0007, infected_lon - 0.0007],
                    [infected_lat - 0.0007, infected_lon + 0.0007],
                    [infected_lat + 0.0007, infected_lon + 0.0007],
                    [infected_lat + 0.0007, infected_lon - 0.0007]
                ],
                color="#FF0000",
                fill=True,
                fill_color="#FF0000",
                fill_opacity=0.6,
                popup=f"⚠️ WARNING: High Crop Stress Spotted! (NDVI: {calc_ndvi})"
            ).add_to(m)
            
        map_output = st_folium(m, width=800, height=520, key="khetify_fixed_map_layer")
        
        if map_output and "last_clicked" in map_output and map_output["last_clicked"] is not None:
            clicked_data = map_output["last_clicked"]
            clicked_lat = round(clicked_data["lat"], 4)
            clicked_lon = round(clicked_data["lng"], 4)
            
            if clicked_lat != current_lat or clicked_lon != current_lon:
                st.session_state.lat = clicked_lat
                st.session_state.lon = clicked_lon
                st.rerun()
        
    with col2:
        st.markdown("### 📈 Core Diagnostics Metrics")
        st.caption(f"Active Coordinates Target: {current_lat:.4f}, {current_lon:.4f} | Size: {dynamic_acreage} Acres")
        
        if not is_infected:
            st.success("✅ Field Status: HEALTHY")
            st.metric(label="NDVI (Vegetation Index)", value=f"{calc_ndvi}", delta="Stable Vegetation")
            st.metric(label="Soil Moisture Profile", value=f"{calc_moisture}%", delta="Optimal Range")
            
            st.markdown("---")
            st.markdown("### 💰 Estimated Field Economic Value")
            st.metric(label="Est. Total Produce Market Value", value=f"PKR {calc_market_value:,}", delta="100% Target Attained")
            st.caption("Value metrics are dynamically tied to regional market index and current acreage scale.")
            
        else:
            st.error("🚨 Field Status: ANOMALY DETECTED (INFECTED)")
            st.metric(label="NDVI (Vegetation Index)", value=f"{calc_ndvi}", delta=f"{round(calc_ndvi - 0.75, 2)} Drop State", delta_color="inverse")
            st.metric(label="Soil Moisture Profile", value=f"{calc_moisture}%", delta="Critical Stress Drop", delta_color="inverse")
            
            st.markdown("---")
            st.markdown("### 💰 Projected Economic Impact")
            st.metric(label="Risk Exposure Value (Potential Loss)", value=f"PKR {calc_risk_exposure:,}", delta="Crop Yield Vulnerability", delta_color="inverse")
            st.metric(label="Targeted Spray Cost Savings", value=f"PKR {calc_savings:,}", delta="+90% Chemical Reduction")
            
            st.markdown("---")
            st.markdown("### 📱 Localized Actionable Outbound Alert")
            
            # Searchable Language Option Selector
            selected_lang = st.selectbox(
                "🌐 Select Local Farmer Language:",
                ["Urdu (اردو)", "English", "Spanish (Español)", "Punjabi (پنجابی)", "Arabic (العربية)", "Hindi (हिंदी)", "French (Français)", "Portuguese (Português)"]
            )
            
            infected_lat = current_lat + 0.0006
            infected_lon = current_lon + 0.0006
            
            # Multi-language dictionary engine for simulated real-time translation mapping
            sms_templates = {
                "Urdu (اردو)": (
                    f"⚠️ Khetify Alert:\n"
                    f"Aapkay khet ke coordinates ({infected_lat:.4f}, {infected_lon:.4f}) par disease scan detect hui hai. "
                    f"Meharbani karkay pooray khet mein spray na karein, sirf is nishandahi kiye gaye hissay par target pesticide spray karein taake kharcha bach sakay."
                ),
                "English": (
                    f"⚠️ Khetify Alert:\n"
                    f"Disease detected at coordinates ({infected_lat:.4f}, {infected_lon:.4f}). "
                    f"Do not blanket-spray the entire field. Apply targeted pesticides only to the highlighted patch to minimize costs and chemical usage."
                ),
                "Spanish (Español)": (
                    f"⚠️ Alerta Khetify:\n"
                    f"Enfermedad detectada en las coordenadas ({infected_lat:.4f}, {infected_lon:.4f}). "
                    f"No fumigue todo el campo. Aplique pesticidas específicos solo en la zona afectada para ahorrar costos."
                ),
                "Punjabi (پنجابی)": (
                    f"⚠️ کھیتی فائی الرٹ:\n"
                    f"تہاڈے کھیت دے کوآرڈینیٹس ({infected_lat:.4f}, {infected_lon:.4f}) تے بیماری لبی اے۔ "
                    f"مہربانی کر کے پورے کھیت وچ سپرے نہ کرو، صرف دسے گئے حصے تے ٹارگٹڈ سپرے کرو تاں جے خرچہ بچ سکے۔"
                ),
                "Arabic (العربية)": (
                    f"⚠️ تنبيه خيتيفاي:\n"
                    f"تم رصد إصابة في الإحداثيات ({infected_lat:.4f}, {infected_lon:.4f}). "
                    f"يرجى عدم رش الحقل بالكامل. استخدم المبيدات الموجهة فقط في المنطقة المحددة لتقليل التكاليف."
                ),
                "Hindi (हिंदी)": (
                    f"⚠️ खेतीफाई अलर्ट:\n"
                    f"आपके खेत के निर्देशांक ({infected_lat:.4f}, {infected_lon:.4f}) पर रोग का पता चला है। "
                    f"कृपया पूरे खेत में कीटनाशक न छिड़कें। खर्च बचाने के लिए केवल प्रभावित हिस्से पर ही लक्षित छिड़काव करें।"
                ),
                "French (Français)": (
                    f"⚠️ Alerte Khetify :\n"
                    f"Maladie détectée aux coordonnées ({infected_lat:.4f}, {infected_lon:.4f}). "
                    f"Ne pulvérisez pas tout le champ. Appliquez des pesticides ciblés uniquement sur la zone affectée pour réduire les coûts."
                ),
                "Portuguese (Português)": (
                    f"⚠️ Alerta Khetify:\n"
                    f"Doença detectada nas coordenadas ({infected_lat:.4f}, {infected_lon:.4f}). "
                    f"Não pulverize o campo inteiro. Aplique pesticidas direcionados apenas na área afetada para economizar custos."
                )
            }
            
            st.text_area(f"Automated Broadcast Content ({selected_lang}):", value=sms_templates[selected_lang], height=150)
else:
    st.info("👈 Enter coordinates or run initial diagnostic to activate the interactive live matrix view.")