import pandas as pd
import streamlit as st
import plotly.express as px

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="Strategic Fleet Dashboard", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# 2. CONSTANTS & BENCHMARKS
# ---------------------------------------------------------
FUEL_RATES = {
    'NISSAN SUNNY': 8.0, 
    'NISSAN ALTIMA': 8.5, 
    'MAZDA': 9.0, 
    'ASHOK LEYLAND': 16.0, 
    'MITSUBISHI CANTER': 15.0
}
PETROL_PRICE = 2.60
DIESEL_PRICE = 2.85

# --- BRAND COLORS (Visual Upgrade) ---
# Updated to be safe: covers specific models AND generic brand names
BRAND_COLORS = {
    'NISSAN SUNNY': '#1E88E5', 'NISSAN': '#1E88E5',      # Blue
    'NISSAN ALTIMA': '#1565C0',                          # Darker Blue
    'MAZDA': '#00ACC1',                                  # Cyan
    'ASHOK LEYLAND': '#43A047',                          # Green (Trucks)
    'MITSUBISHI CANTER': '#E53935', 'MITSUBISHI': '#E53935', # Red (Trucks)
    'General Pool': '#78909C',                           # Grey
    '(?)': '#ECEFF1'                                     # Root Color
}

CITY_COORDS = {
    'Dubai': (25.2048, 55.2708),
    'Abu Dhabi': (24.4539, 54.3773),
    'Sharjah': (25.3463, 55.4209),
    'Al Ain': (24.1302, 55.7434),
    'Ras Al Khaimah': (25.8007, 55.9762),
    'Fujairah': (25.1288, 56.3265),
    'Ajman': (25.4052, 55.5136),
    'Umm Al Quwain': (25.5471, 55.7032),
    'Unknown': (25.0, 55.0)
}

# ---------------------------------------------------------
# 3. SIDEBAR & FILE UPLOAD
# ---------------------------------------------------------
st.sidebar.image("https://img.icons8.com/fluency/96/000000/truck.png", width=80)
st.sidebar.title("Fleet Control Panel")
st.sidebar.markdown("---")
st.sidebar.header("1. Upload Data")

uploaded_file = st.sidebar.file_uploader("Upload 'Telematics Report' (Excel)", type=["xlsx"])

# ---------------------------------------------------------
# 4. DATA LOADING ENGINE (ROBUST)
# ---------------------------------------------------------
@st.cache_data
def load_data(file):
    try:
        # Load File
        df = pd.read_excel(file, sheet_name=0, skiprows=2, engine="openpyxl")
        df = df[df.iloc[:, 0].notna()].copy()
        
        # Standardize Columns
        df.columns = ['Sr', 'Plate_Number', 'Make', 'Location', 'Start_Km', 'End_Km', 'Total_Km']

        # Numeric Conversions
        for col in ['Start_Km', 'End_Km', 'Total_Km']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Regex Extraction (Plate -> ID + Role)
        df[['Vehicle_ID', 'Role_Notes']] = df['Plate_Number'].astype(str).str.extract(r'^([A-Z0-9-]+)\s*(.*)$')
        
        # Clean Text
        df['Vehicle_ID'] = df['Vehicle_ID'].fillna(df['Plate_Number'].astype(str))
        df['Role_Notes'] = df['Role_Notes'].fillna("General Pool").replace("", "General Pool").str.strip()
        df['Make'] = df['Make'].astype(str).str.strip().str.upper()

        # Normalize Locations
        df['Location'] = df['Location'].astype(str).str.upper()\
            .str.replace('CWL-DUBAI', 'DUBAI').str.replace('CWL DUBAI', 'DUBAI')\
            .str.replace('SHJ-THAMEEM', 'SHARJAH').str.replace('AUH', 'ABU DHABI')\
            .str.replace('AL AIN', 'AL AIN').str.strip()
        
        # Map Clean Names
        df['Location'] = df['Location'].map({
            'DUBAI': 'Dubai', 'ABU DHABI': 'Abu Dhabi', 'SHARJAH': 'Sharjah',
            'AL AIN': 'Al Ain', 'RAS AL KHAIMAH': 'Ras Al Khaimah',
            'FUJAIRAH': 'Fujairah', 'AJMAN': 'Ajman', 'UMM AL QUWAIN': 'Umm Al Quwain'
        }).fillna('Unknown')

        # Map Coordinates
        df['Lat'] = df['Location'].map(lambda x: CITY_COORDS.get(x, CITY_COORDS['Unknown'])[0])
        df['Lon'] = df['Location'].map(lambda x: CITY_COORDS.get(x, CITY_COORDS['Unknown'])[1])

        # Maintenance Segmentation
        # ⚠️ .astype(str) prevents the dashboard from crashing on categorical errors
        df['Maintenance_Band'] = pd.cut(df['End_Km'],
            bins=[0, 50000, 100000, float('inf')],
            labels=['Fresh (<50k km)', 'Mid-Life (50-100k km)', 'End-of-Life (>100k km)'],
            include_lowest=True
        ).astype(str)

        # Fuel Cost Calculation
        def calc_fuel(row):
            rate = FUEL_RATES.get(row['Make'], 12.0)
            liters = (row['Total_Km'] / 100) * rate
            price = PETROL_PRICE if row['Make'] in ['NISSAN SUNNY', 'NISSAN ALTIMA', 'MAZDA'] else DIESEL_PRICE
            return round(liters * price)

        df['Est_Fuel_Cost_AED'] = df.apply(calc_fuel, axis=1)

        return df

    except Exception as e:
        st.error(f"Error parsing file: {e}")
        st.stop()

# ---------------------------------------------------------
# 5. MAIN DASHBOARD LOGIC
# ---------------------------------------------------------

if uploaded_file is None:
    st.title("Strategic Fleet Telematics Dashboard")
    st.info("<--- Please upload the 'Telematics Report' Excel file in the sidebar to begin.")
    st.stop()

else:
    # Load Data
    df = load_data(uploaded_file)

    # Sidebar Filters
    st.sidebar.header("2. Filtering")
    threshold = st.sidebar.slider("Active Vehicle Threshold (km)", 0, 200, 10)
    
    locations = st.sidebar.multiselect("Select Location", sorted(df['Location'].unique()), df['Location'].unique())
    makes = st.sidebar.multiselect("Select Make", sorted(df['Make'].unique()), df['Make'].unique())
    
    # --- NEW FILTER: PLATE NUMBER ---
    all_plates = sorted(df['Plate_Number'].astype(str).unique())
    selected_plates = st.sidebar.multiselect("Search Plate Number", all_plates)

    # Filter Logic
    filtered = df.copy()
    if locations:
        filtered = filtered[filtered['Location'].isin(locations)]
    if makes:
        filtered = filtered[filtered['Make'].isin(makes)]
    if selected_plates:
        filtered = filtered[filtered['Plate_Number'].isin(selected_plates)]

    # --- KPIs (MULTI-MONTH SAFE) ---
    active = filtered[filtered['Total_Km'] > threshold]
    
    # ⚠️ Count Unique IDs, not just rows (Safe for multi-month data)
    total_fleet_count = filtered['Vehicle_ID'].nunique()
    active_fleet_count = active['Vehicle_ID'].nunique()
    
    util_rate = (active_fleet_count / total_fleet_count * 100) if total_fleet_count > 0 else 0
    ghost_assets = len(filtered[filtered['Total_Km'] == 0])
    total_fuel = filtered['Est_Fuel_Cost_AED'].sum()

    st.title("Strategic Fleet Telematics Intelligence Platform")
    st.markdown("**Production-Grade Fleet Optimization Dashboard**")

    # --- METRICS ROW ---
    k1, k2, k3, k4, k5 = st.columns(5)
    
    k1.metric("Total Distance", f"{filtered['Total_Km'].sum():,.0f} km",
              help="Sum of total kilometers driven by all filtered vehicles.")
              
    k2.metric("Utilization Rate", f"{util_rate:.1f}%",
              help=f"Percentage of unique vehicles that drove more than {threshold} km.")
              
    k3.metric("Active Vehicles", f"{active_fleet_count} / {total_fleet_count}",
              help="Unique vehicles currently working vs. total unique fleet size.")
              
    k4.metric("Ghost Assets", ghost_assets, delta_color="inverse",
              help="Vehicles with 0 km movement. These are unused assets.")
              
    k5.metric("Est. Fuel Cost", f"AED {total_fuel:,.0f}",
              help="Approximate total fuel cost for the selected period.")

    st.caption(f"⛽ **Fuel Basis:** Petrol {PETROL_PRICE} AED/L (Cars) | Diesel {DIESEL_PRICE} AED/L (Trucks)")
    st.markdown("---")

    # --- ROW 1: CHARTS ---
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Mileage by Location & Make")
        st.caption("📊 **Indicator:** Compare the workload across different sites. Taller bars mean more distance covered.")
        
        bar_data = filtered.groupby(['Location', 'Make'])['Total_Km'].sum().reset_index()
        fig_bar = px.bar(bar_data, x='Location', y='Total_Km', color='Make', text='Total_Km')
        fig_bar.update_traces(texttemplate='%{text:,.0f}')
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        st.subheader("Fleet Composition Hierarchy")
        st.caption("💡 **How to read:** Inner = Make → Middle = Role → Outer = Maintenance Status")
        st.caption("🎨 **Color Key:** Nissan=Blue | Mazda=Cyan | Ashok=Green | Mitsubishi=Red")
        
        sun_data = filtered.groupby(['Make', 'Role_Notes', 'Maintenance_Band']).size().reset_index(name='Count')
        
        # --- SUNBURST (WITH BRAND COLORS) ---
        fig_sun = px.sunburst(
            sun_data, 
            path=['Make', 'Role_Notes', 'Maintenance_Band'], 
            values='Count',
            color='Make',                       # Color by Brand
            color_discrete_map=BRAND_COLORS     # Use Specific Brand Colors
        )
        st.plotly_chart(fig_sun, use_container_width=True)

    # --- ROW 2: TOP PERFORMERS (Moved UP) ---
    st.subheader("Top Workhorses (80/20 Rule Analysis)")
    st.caption("🏆 **Indicator:** Identifies the top vehicles doing the most work. These may require earlier maintenance.")
    
    top_vehicles = filtered.nlargest(int(len(filtered)*0.2) + 5, 'Total_Km')
    fig_pareto = px.bar(top_vehicles, x='Vehicle_ID', y='Total_Km', color='Make', text='Total_Km')
    fig_pareto.update_traces(texttemplate='%{text:,.0f}')
    st.plotly_chart(fig_pareto, use_container_width=True)

    # --- ROW 3: MAP (Moved DOWN) ---
    st.subheader("Geospatial Fleet Overview")
    st.info("ℹ️ **Legend:** Circle Size = Number of vehicles | Color Intensity = Total Distance driven.")

    map_agg = filtered.groupby('Location').agg({
        'Total_Km': 'sum', 'Vehicle_ID': 'count', 'Lat': 'first', 'Lon': 'first'
    }).reset_index()

    fig_map = px.scatter_mapbox(
        map_agg, lat='Lat', lon='Lon', size='Vehicle_ID', color='Total_Km',
        hover_name='Location', color_continuous_scale="OrRd", size_max=60, zoom=6,
        mapbox_style="open-street-map"
    )
    fig_map.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=450)
    st.plotly_chart(fig_map, use_container_width=True)

    # --- ROW 4: DATA TABLE ---
    st.subheader("Detailed Fleet Registry")
    styled_df = filtered[['Vehicle_ID', 'Role_Notes', 'Make', 'Location', 'Total_Km', 'Est_Fuel_Cost_AED', 'Maintenance_Band']]\
        .sort_values('Total_Km', ascending=False)\
        .style.format({'Total_Km': '{:,.0f}', 'Est_Fuel_Cost_AED': '{:,.0f}'})\
        .bar(subset=['Total_Km'], color='#d65f5f')

    st.dataframe(styled_df, use_container_width=True, height=400)
    
    # Export
    csv = filtered.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Report CSV", csv, "Strategic_Fleet_Report.csv", "text/csv")

    # ---------------------------------------------------------
    # 6. GLOSSARY SECTION
    # ---------------------------------------------------------
    st.markdown("---")
    with st.expander("📚 **Glossary & Terminology Definitions (Click to Expand)**", expanded=False):
        st.markdown("""
        ### **1. Key Performance Indicators (KPIs)**
        - **Utilization Rate:** The percentage of the fleet that is actually working. Calculated as `(Active Vehicles / Total Unique Vehicles) * 100`.
        - **Active Vehicle:** A vehicle that has driven more than the selected threshold (default 10 km) in the reporting period.
        - **Ghost Asset:** A vehicle that has **0 km** movement. These are sitting idle and costing money without providing value.
        
        ### **2. Financials**
        - **Est. Fuel Cost:** An approximation of fuel spend. 
            - *Formula:* `(Total Km / 100) * Fuel Rate * Fuel Price`
            - *Assumptions:* Sedans consume ~8.5L/100km (Petrol), Trucks consume ~15L/100km (Diesel).

        ### **3. Data Processing**
        - **Role extraction:** The dashboard reads the `Plate Number` (e.g., "1-98025 RT-198- AUH") and automatically splits it into **ID** (1-98025) and **Role** (RT-198).
        - **Maintenance Band:**
            - 🟢 **Fresh:** < 50,000 km total mileage.
            - 🟡 **Mid-Life:** 50,000 - 100,000 km.
            - 🔴 **End-of-Life:** > 100,000 km (High maintenance risk).
        """)
