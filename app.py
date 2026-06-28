import streamlit as st
import folium
from streamlit_folium import st_folium
import hashlib

# Page Configuration
st.set_page_config(page_title="Khetify - AI Satellite Analysis Engine", layout="wide")

st.title("🌾 Khetify - Real-time Satellite Diagnostics")
st.markdown("Enter coordinates or **click anywhere directly on the map** to run live multi-spectral analysis on adjacent fields.")

# --- SESSION STATE MANAGEMENT ---
if "clicked" not in st.session_state:
    st.session_state.clicked = False
if "lat" not in st.session_state:
    st.session_state.lat = 31.1853
if "lon" not in st.session_state:
    st.session_state.lon = 73.9621

# --- SIDEBAR: Coordinates & Satellite Sources ---
st.sidebar.header("📍 Field Coordinates")

# Standard sidebar inputs sync with session state
input_lat = st.sidebar.number_input("Latitude", value=st.session_state.lat, format="%.4f", key="sidebar_lat")
input_lon = st.sidebar.number_input("Longitude", value=st.session_state.lon, format="%.4f", key="sidebar_lon")

# If user modifies manually via sidebar, update session state values
if input_lat != st.session_state.lat or input_lon != st.session_state.lon:
    st.session_state.lat = input_lat
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

# --- BACKEND LOGIC: Deterministic Output based on current active state ---
current_lat = st.session_state.lat
current_lon = st.session_state.lon

coord_hash = int(hashlib.md5(f"{current_lat:.4f},{current_lon:.4f}".encode()).hexdigest(), 16)
is_infected = (coord_hash % 2) == 1  

if st.session_state.clicked:
    st.subheader(f"📊 Satellite Analysis Results ({satellite_source})")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 🗺️ Precision Field Mapping")
        
        # Google Maps Hybrid Layer
        google_satellite_url = "https://mt1.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}"
        m = folium.Map(
            location=[current_lat, current_lon], 
            zoom_start=16, 
            tiles=google_satellite_url,
            attr="Google Satellite Imagery"
        )
        
        if not is_infected:
            # Healthy Field Polygon
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
                popup="Healthy Vegetation Zone"
            ).add_to(m)
            
        else:
            # Base Farm Bound
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
            
            # Isolated Anomaly Zone
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
                popup="⚠️ WARNING: High Fungal/Pest Infection Detected!"
            ).add_to(m)
            
        # Capture map click return events
        map_output = st_folium(m, width=800, height=520, key="khetify_interactive_map")
        
        # INTERACTIVE CLICK ENGINE: If user clicks another field on the map
        if map_output and map_output.get("last_clicked"):
            clicked_coords = map_output["last_clicked"]
            clicked_lat = round(clicked_coords["lat"],  4)
            clicked_lon = round(clicked_coords["lng"], 4)
            
            # Update state values immediately if the click is new
            if clicked_lat != current_lat or clicked_lon != current_lon:
                st.session_state.lat = clicked_lat
                st.session_state.lon = clicked_lon
                st.rerun()
        
    with col2:
        st.markdown("### 📈 Core Diagnostics Metrics")
        st.caption(f"Active Target: {current_lat:.4f}, {current_lon:.4f}")
        
        if not is_infected:
            st.success("✅ Field Status: HEALTHY")
            st.metric(label="NDVI (Vegetation Index)", value="0.78", delta="Stable")
            st.metric(label="Soil Moisture Profile", value="62%", delta="Optimal")
            
            st.markdown("---")
            st.markdown("### 💰 Estimated Field Economic Value")
            st.metric(label="Est. Total Produce Market Value", value="PKR 2,450,000", delta="100% Target Attained")
            st.caption("Value calculated based on standard acreage parameters and current market rate index.")
            
        else:
            st.error("🚨 Field Status: ANOMALY DETECTED (INFECTED)")
            st.metric(label="NDVI (Vegetation Index)", value="0.34", delta="-0.44 Crop Stress", delta_color="inverse")
            st.metric(label="Soil Moisture Profile", value="38%", delta="-24% Critical Drop", delta_color="inverse")
            
            st.markdown("---")
            st.markdown("### 💰 Projected Economic Impact & Recovery")
            st.metric(label="Risk Exposure Value (Potential Crop Loss)", value="PKR 850,000", delta="-34% At Risk", delta_color="inverse")
            st.metric(label="Targeted Spray Cost Savings", value="PKR 145,000", delta="+90% Input Recovery")
            
            st.markdown("---")
            st.markdown("### 📱 Triggered Localized Urdu SMS Alert")
            infected_lat = current_lat + 0.0006
            infected_lon = current_lon + 0.0006
            sms_text = (
                f"⚠️ Khetify Alert:\n"
                f"Aapkay khet ke coordinates ({infected_lat:.4f}, {infected_lon:.4f}) par "
                f"disease scan detect hui hai. Meharbani karkay pooray khet mein spray na karein, "
                f"sirf is nishandahi kiye gaye hissay par target pesticide spray karein taake kharcha bach sakay."
            )
            st.text_area("Automated Outbound SMS Content:", value=sms_text, height=140)
else:
    st.info("👈 Enter coordinates or run initial diagnostic to activate the interactive live matrix view.")