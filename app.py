import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# Streamlit page layout configurations
st.set_page_config(page_title="Khetify MVP - AI Crop Analysis", layout="wide")

st.title("🌱 Khetify - Friction-Free Precision Agriculture")
st.subheader("AI-Driven Crop Analysis Dashboard for Smallholder Farmers")

# --- STEP 1: DEMO MODE SWITCH (For Video Presentation) ---
st.sidebar.header("🎬 Video Demo Settings")
demo_mode = st.sidebar.radio(
    "Select Field Condition for Demo:",
    ["Healthy Field Simulation", "🚨 Infected Field (Problem Area Example)"]
)

st.sidebar.write("---")
st.sidebar.header("📍 Farm Location Settings")

# Dynamic coordinates and zoom based on demo mode selection
if "Infected" in demo_mode:
    # Coordinates mimicking a troubled crop area
    default_lat = 33.6150
    default_lon = 73.0820
    map_color = "red"
    fill_color = "crimson"
    layer_name = "🚨 Critical Pest Alert Grid"
else:
    # Default healthy crop coordinates
    default_lat = 33.6007
    default_lon = 73.0679
    map_color = "darkgreen"
    fill_color = "lime"
    layer_name = "🟢 Optimal Crop Grid"

user_lat = st.sidebar.number_input("Enter Latitude", value=default_lat, format="%.6f")
user_lon = st.sidebar.number_input("Enter Longitude", value=default_lon, format="%.6f")
zoom_level = st.sidebar.slider("Map Zoom Level", min_value=1, max_value=18, value=15)

# --- STEP 2: SATELLITE SELECTION ---
st.sidebar.header("🛰️ Satellite Data Sources")
satellite_option = st.sidebar.selectbox(
    "Choose Primary Satellite Layer:",
    ["Sentinel-2 (ESA - High Precision Vegetation)", "Landsat (NASA - Soil & Moisture)"]
)

# --- STEP 3: INTERACTIVE MAP (Absolute Coordinate Locking) ---
st.write(f"### 🗺️ Live Farm Border Tracking: {layer_name}")

# Map initialisation with strict layout [Latitude, Longitude] - Fixes the zoom bug
m = folium.Map(location=[user_lat, user_lon], zoom_start=zoom_level, control_scale=True)

# Farm center pin configuration
folium.Marker(
    [user_lat, user_lon],
    popup=f"Farm Center\nLat: {user_lat}\nLon: {user_lon}",
    tooltip="Click to view farm telemetry",
    icon=folium.Icon(color="red" if "Infected" in demo_mode else "green", icon="leaf")
).add_to(m)

# Drawing the boundary grid based on health selection
folium.Circle(
    location=[user_lat, user_lon],
    radius=250, # 250 meters farm perimeter
    color=map_color,
    fill=True,
    fill_color=fill_color,
    fill_opacity=0.3,
    popup=f"{satellite_option} Telemetry Zone"
).add_to(m)

# Rendering the map
st_folium(m, width=900, height=450, key="khetify_dynamic_map")


# --- STEP 4: RUN AI ANALYSIS (Dynamic Pitch Outputs) ---
st.write("---")
st.write("### 🧠 Diagnostic Center")

if st.button("🚀 Run AI Analysis", type="primary"):
    st.success("🔄 Fetching multi-spectral bands from satellite buffers...")
    
    col1, col2 = st.columns(2)
    
    if "Infected" in demo_mode:
        # PROBLEM AREA SCENARIO FOR VIDEO PITCH
        with col1:
            st.metric(label="🌾 NDVI Health Index (Crop Vigor)", value="0.38", delta="-0.31 (CRITICAL DROPOUT)", delta_color="inverse")
            st.error("🚨 **AI Diagnostic Output: PEST INFESTATION DETECTED**")
            st.write("Spectral signature analysis detects heavy **Yellow Rust (Fungal Infestation)** spreading rapidly across the North-East perimeter grid coordinates.")
            
        with col2:
            st.metric(label="💧 Soil Moisture Saturation", value="34%", delta="-21% (Severe Stress)", delta_color="inverse")
            st.subheader("📲 Automated Farmer Alert Sent:")
            st.warning("*\"Shahzaib sahib, aapke khet ke shumal-mashriqi (North-East) hisse mein pilay rang ki bimari (Yellow Rust) shuru ho chuki hai. Agle 24 ghante mein sirf is zone par 120ml Propiconazole ka spray karein taake baki khet bach jaye.\"*")
    else:
        # HEALTHY FIELD SCENARIO
        with col1:
            st.metric(label="🌾 NDVI Health Index (Crop Vigor)", value="0.74", delta="+0.05 (Healthy)")
            st.write("**AI Diagnostic Output:**")
            st.write("The crop canopy reflects optimal biomass and nitrogen absorption levels. No anomalies found.")
            
        with col2:
            st.metric(label="💧 Soil Moisture Saturation", value="62%", delta="-3% (Optimal)")
            st.write("**Recommended Action Items:**")
            st.info("Everything looks green. Maintain the standard irrigation loop for the next 48 hours.")
else:
    st.warning("Click the 'Run AI Analysis' button above to trigger the satellite diagnostic engine.")