import streamlit as st
import pandas as pd
import plotly.express as px

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="Strategic Fleet Intelligence", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# 2. CUSTOM CSS (Visual Contrast)
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    /* Fixes dropdown menu contrast for Dark Mode */
    div[data-baseweb="popover"] { background-color: #262730 !important; border: 1px solid #4c4c4c !important; }
    div[role="listbox"] ul { background-color: #262730 !important; }
    span[data-baseweb="tag"] { background-color: #31333F !important; border: 1px solid #FF4B4B; }
    
    /* KPI Card Styling */
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #ff4b4b;
    }
    
    /* AI Box Styling */
    .ai-box {
        background-color: #e3f2fd;
        border: 1px solid #2196f3;
        padding: 20px;
        border-radius: 10px;
        color: #0d47a1;
        margin-bottom: 20px;
    }
    .savings-box {
        background-color: #e8f5e9;
        border: 1px solid #00c853;
        padding: 20px;
        border-radius: 10px;
        color: #1b5e20;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------------------------------------
# 3. HELPER FUNCTIONS
# ---------------------------------------------------------
def multiselect_with_all(label, options, key):
    """Creates a multiselect with a 'Select All' option."""
    options = sorted(list(set(options)))
    all_options = ['Select All'] + options
    selected = st.sidebar.multiselect(label, all_options, default=['Select All'], key=key)
    if 'Select All' in selected:
        return options
    else:
        return selected

# ---------------------------------------------------------
# 4. DATA LOADING ENGINE (Cached)
# ---------------------------------------------------------
@st.cache_data
def load_data(file):
    try:
        # Check for openpyxl dependency implicitly by trying to read
        df = pd.read_excel(file, sheet_name=0, skiprows=2, engine="openpyxl")
        
        # Data Cleaning
        df = df.dropna(subset=[df.columns[0]]).copy()
        # Rename strictly to ensure downstream logic holds
        df.columns = ['Sr', 'Plate', 'Make', 'Location', 'Start_Km', 'End_Km', 'Total_Km']
        
        df['Total_Km'] = pd.to_numeric(df['Total_Km'], errors='coerce').fillna(0)
        df['End_Km'] = pd.to_numeric(df['End_Km'], errors='coerce').fillna(0)
        df['Make'] = df['Make'].astype(str).str.upper().str.strip()
        
        # Regex: ID & Role
        df[['Vehicle_ID', 'Role_Notes']] = df['Plate'].astype(str).str.extract(r'^([A-Z0-9-]+)\s*(.*)$')
        df['Role_Notes'] = df['Role_Notes'].fillna('General Pool').replace('', 'General Pool').str.strip()
        df['Vehicle_ID'] = df['Vehicle_ID'].fillna(df['Plate'].astype(str))

        # Location Standardization and Mapping
        df['Location'] = df['Location'].astype(str).str.upper()\
            .replace({'CWL-DUBAI':'DUBAI', 'CWL DUBAI':'DUBAI', 'SHJ-THAMEEM':'SHARJAH', 'AUH':'ABU DHABI'})\
            .replace({'DUBAI':'Dubai', 'ABU DHABI':'Abu Dhabi', 'SHARJAH':'Sharjah', 'AL AIN':'Al Ain', 
                      'AJMAN':'Ajman', 'FUJAIRAH':'Fujairah', 'RAS AL KHAIMAH':'Ras Al Khaimah'})\
            .fillna('Other')
        coords = {
            'Dubai':(25.20, 55.27), 'Abu Dhabi':(24.45, 54.37), 'Sharjah':(25.34, 55.42),
            'Al Ain':(24.13, 55.74), 'Ajman':(25.40, 55.51), 'Fujairah':(25.12, 56.32),
            'Ras Al Khaimah':(25.80, 55.97), 'Other':(25.0, 55.0)
        }
        df['Lat'] = df['Location'].map(lambda x: coords.get(x, coords['Other'])[0])
        df['Lon'] = df['Location'].map(lambda x: coords.get(x, coords['Other'])[1])
        
        # Maintenance Segments
        df['Maintenance_Band'] = pd.cut(df['End_Km'],
            bins=[0, 50000, 100000, float('inf')],
            labels=['Fresh (<50k km)', 'Mid-Life (50-100k km)', 'End-of-Life (>100k km)'],
            include_lowest=True
        ).astype(str)
        
        return df

    except Exception as e:
        st.error(f"Data Error: {e}")
        st.stop()

# ---------------------------------------------------------
# 5. SIDEBAR & INPUTS
# ---------------------------------------------------------
with st.sidebar:
    st.title("🚛 Fleet Control")
    uploaded_file = st.file_uploader("Upload Report", type=["xlsx"])

    if st.button("Reset All Settings"):
        st.session_state.clear()
        st.rerun()

if uploaded_file is None:
    st.title("Strategic Fleet Intelligence Platform")
    st.info("👋 Please upload your Telematics Excel file to begin analysis.")
    st.stop()

# Load Data
df_base = load_data(uploaded_file)

# --- A. SIMULATION INPUTS (The UI) ---
st.sidebar.markdown("---")
st.sidebar.header("1. Cost Simulation")
petrol_price = st.sidebar.number_input("Petrol Price (AED/L)", value=2.60, step=0.05, key='petrol_input')
diesel_price = st.sidebar.number_input("Diesel Price (AED/L)", value=2.85, step=0.05, key='diesel_input')
global_eff = st.sidebar.slider("Global Weather Impact", 0.9, 1.2, 1.0, key='global_eff_input',
    help="Multiplier for external factors (e.g. 1.1 = Summer Heat).")

# --- B. DYNAMIC COST CALCULATION ---
# Base consumption rates (L/100km)
fuel_rates = {'NISSAN SUNNY':8.0, 'NISSAN ALTIMA':8.5, 'MAZDA':9.0, 'ASHOK LEYLAND':16.0, 'MITSUBISHI CANTER':15.0}

def calculate_smart_cost(row):
    rate = fuel_rates.get(row['Make'], 12.0)
    
    # Health Efficiency Mapping (Age Penalty Logic)
    health_factor = 1.0
    if 'Mid-Life' in row['Maintenance_Band']:
        health_factor = 1.05
    elif 'End-of-Life' in row['Maintenance_Band']:
        health_factor = 1.15
        
    rate = rate * health_factor * global_eff # Apply Health AND Global Weather
    
    price = petrol_price if row['Make'] in ['NISSAN SUNNY', 'NISSAN ALTIMA', 'MAZDA'] else diesel_price
    
    return round((row['Total_Km'] / 100) * rate * price)

df = df_base.copy()
df['Est_Fuel_Cost_AED'] = df.apply(calculate_smart_cost, axis=1)

# --- C. FILTERS ---
st.sidebar.markdown("---")
st.sidebar.header("2. Filter Logic")
st.sidebar.caption("Filters cascade intelligently.")

# 1. Location
loc_options = df['Location'].unique().tolist()
sel_locs = multiselect_with_all("Location", loc_options, key='loc_filter')
df_step1 = df[df['Location'].isin(sel_locs)]

# 2. Make
make_options = df_step1['Make'].unique().tolist()
sel_makes = multiselect_with_all("Make", make_options, key='make_filter')
df_step2 = df_step1[df_step1['Make'].isin(sel_makes)]

# 3. Maintenance
maint_options = df_step2['Maintenance_Band'].unique().tolist()
sel_maint = multiselect_with_all("Maintenance Status", maint_options, key='maint_filter')
df_step3 = df_step2[df_step2['Maintenance_Band'].isin(sel_maint)]

# 4. Vehicle
veh_options = df_step3['Vehicle_ID'].unique().tolist()
sel_vehicles = multiselect_with_all("Vehicle ID", veh_options, key='veh_filter')

selection_filtered = df_step3[df_step3['Vehicle_ID'].isin(sel_vehicles)].copy()

if selection_filtered.empty:
    st.warning("No vehicles selected. Please adjust filters.")
    st.stop()

# 5. Threshold
max_km_found = int(selection_filtered['Total_Km'].max()) if not selection_filtered.empty else 500
threshold = st.sidebar.slider("Active Vehicle Threshold (km)", 0, max(max_km_found + 50, 100), 10, key='thresh_slider')

# Identify Ghost Assets (Zero Usage) vs Low Usage
ghost_assets_data = selection_filtered[selection_filtered['Total_Km'] == 0]

# Calculate CPK (Cost Per Kilometer) - Handling Zero Division
selection_filtered['CPK'] = selection_filtered.apply(
    lambda x: x['Est_Fuel_Cost_AED'] / x['Total_Km'] if x['Total_Km'] > 0 else 0, axis=1
)

# Apply Active Threshold Filter
filtered = selection_filtered[selection_filtered['Total_Km'] > threshold]

# ---------------------------------------------------------
# 6. KPIS
# ---------------------------------------------------------
util_rate = (len(filtered) / len(selection_filtered) * 100) if len(selection_filtered) > 0 else 0
ghost_assets_count = len(ghost_assets_data)
total_fuel = filtered['Est_Fuel_Cost_AED'].sum()
avg_cpk = filtered[filtered['Total_Km']>0]['CPK'].mean() # Average CPK of active vehicles

st.title("Strategic Fleet Intelligence Platform")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Distance", f"{filtered['Total_Km'].sum():,.0f} km")
c2.metric("Utilization Rate", f"{util_rate:.1f}%")
c3.metric("Active Assets", f"{len(filtered)} / {len(selection_filtered)}")
c4.metric("Ghost Assets", ghost_assets_count, delta_color="inverse")
c5.metric("Est. Fuel Cost", f"AED {total_fuel:,.0f}")

st.caption(f"⛽ Basis: Petrol {petrol_price} | Diesel {diesel_price} | Weather Factor {global_eff}x")

# --- Ghost Asset Expander ---
if ghost_assets_count > 0:
    with st.expander(f"⚠️ View {ghost_assets_count} Ghost Assets (0 km usage)", expanded=False):
        st.dataframe(ghost_assets_data[['Vehicle_ID', 'Make', 'Location', 'Role_Notes']], use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------
# 7. VISUALIZATION ROW 1 (CPK & Health)
# ---------------------------------------------------------
col_health, col_cpk = st.columns(2)
color_map = {'Fresh (<50k km)': '#2ecc71', 'Mid-Life (50-100k km)': '#f1c40f', 'End-of-Life (>100k km)': '#e74c3c'}

with col_health:
    st.subheader("Fleet Health (Count)")
    st.caption("Risk segmentation based on total accumulated kilometers.")
    band_counts = filtered['Maintenance_Band'].value_counts().reindex([
        'Fresh (<50k km)', 'Mid-Life (50-100k km)', 'End-of-Life (>100k km)'
    ], fill_value=0).reset_index()
    band_counts.columns = ['Band', 'Count']
    
    fig_maint = px.bar(band_counts, x='Band', y='Count', color='Band',
        color_discrete_map=color_map, text='Count', template='plotly_white')
    fig_maint.update_layout(showlegend=False, xaxis_title=None, height=300)
    st.plotly_chart(fig_maint, use_container_width=True)

with col_cpk:
    st.subheader("Cost Performance by Make")
    st.caption("Lower CPK (Cost per Kilometer) is better performance.")
    
    # Calculate Average CPK per Make (Active vehicles only)
    cpk_data = filtered.groupby('Make')['CPK'].mean().reset_index().sort_values('CPK')

    fig_cpk = px.bar(
        cpk_data, 
        x='Make', 
        y='CPK', 
        color='Make', 
        text='CPK',
        color_discrete_sequence=px.colors.qualitative.Dark24, 
        template='plotly_white'
    )
    fig_cpk.update_traces(texttemplate='AED %{text:.3f}')
    fig_cpk.update_layout(xaxis_title=None, yaxis_title="Average CPK (AED/km)", height=300, showlegend=False)
    st.plotly_chart(fig_cpk, use_container_width=True)


# ---------------------------------------------------------
# 8. VISUALIZATION ROW 2 (Location & Map)
# ---------------------------------------------------------
col_bar, col_map = st.columns(2)

with col_bar:
    st.subheader("Workload by Location")
    bar_data = filtered.groupby(['Location', 'Make'])['Total_Km'].sum().reset_index()
    fig_bar = px.bar(
        bar_data, x='Location', y='Total_Km', color='Make',
        color_discrete_sequence=px.colors.qualitative.Bold, template='plotly_white'
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col_map:
    st.subheader("Geospatial Overview")
    
    # Aggregate data for map
    map_agg = filtered.groupby('Location').agg(
        Total_Km=('Total_Km', 'sum'), 
        Vehicle_Count=('Vehicle_ID', 'count'), 
        Lat=('Lat', 'first'), 
        Lon=('Lon', 'first'),
        Avg_CPK=('CPK', 'mean')
    ).reset_index()
    
    # Enhanced Hover Data
    fig_map = px.scatter_mapbox(
        map_agg, lat='Lat', lon='Lon', size='Vehicle_Count', color='Total_Km',
        color_continuous_scale="Viridis", size_max=50, zoom=6, mapbox_style="open-street-map", 
        hover_name='Location',
        hover_data={
            'Total_Km': ':, .0f', 
            'Vehicle_Count': True,
            'Avg_CPK': ':.3f',
            'Lat': False, # Hide raw coordinates
            'Lon': False
        }
    )
    fig_map.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=350)
    st.plotly_chart(fig_map, use_container_width=True)

# ---------------------------------------------------------
# 9. ROW 3: TOP WORKHORSES & REGISTRY
# ---------------------------------------------------------
st.subheader("Top Workhorses (80/20 Rule Analysis)")
top_vehicles = filtered.nlargest(int(len(filtered)*0.2)+5, 'Total_Km')
fig_top = px.bar(top_vehicles, x='Vehicle_ID', y='Total_Km', color='Make',
    text='Total_Km', color_discrete_sequence=px.colors.qualitative.Vivid, template='plotly_white')
fig_top.update_traces(texttemplate='%{text:,.0f}')
st.plotly_chart(fig_top, use_container_width=True)

# Detailed Table
st.markdown("### 📋 Detailed Registry")
styled_df = filtered[['Vehicle_ID', 'Role_Notes', 'Make', 'Location', 'Total_Km', 'Est_Fuel_Cost_AED', 'CPK', 'Maintenance_Band']]\
    .sort_values('Total_Km', ascending=False)\
    .style.format({'Total_Km': '{:,.0f}', 'Est_Fuel_Cost_AED': '{:,.0f}', 'CPK': '{:.3f}'})\
    .bar(subset=['Total_Km'], color='#8e44ad')

st.dataframe(styled_df, use_container_width=True, height=300)

csv = filtered.to_csv(index=False).encode('utf-8')
st.download_button("📥 Download Filtered Report", csv, "Fleet_Intelligence_Report.csv", "text/csv")

st.markdown("---")

# ---------------------------------------------------------
# 10. AI FLEET ANALYST (NEW FEATURE)
# ---------------------------------------------------------
st.subheader("🤖 AI Fleet Analyst: Optimization Engine")

# AI Logic
avg_fleet_km = filtered['Total_Km'].mean() if not filtered.empty else 0
potential_savings = ghost_assets_count * 1500 # Assuming 1500 AED/Month lease cost
overworked_count = len(filtered[filtered['Total_Km'] > (avg_fleet_km * 2)])

c_ai1, c_ai2 = st.columns([1, 1])

with c_ai1:
    st.markdown(f"""
    <div class="savings-box">
        <h4>💰 Ghost Asset Savings Opportunity</h4>
        <p>You have <b>{ghost_assets_count} vehicles</b> showing 0 km usage.</p>
        <p>If these are rented/leased assets, returning them could save approximately:</p>
        <h2>AED {potential_savings:,.0f} / Month</h2>
        <small><i>*Based on estimated AED 1,500 monthly lease cost per unit.</i></small>
    </div>
    """, unsafe_allow_html=True)

with c_ai2:
    st.markdown(f"""
    <div class="ai-box">
        <h4>🔄 Load Balancing Recommendation</h4>
        <p><b>{overworked_count} vehicles</b> are being overworked (driving > 2x the fleet average).</p>
        <ul>
            <li><b>Fleet Average:</b> {avg_fleet_km:,.0f} km</li>
            <li><b>Risk:</b> High mileage increases breakdown risk by 40%.</li>
            <li><b>Action:</b> Rotate these high-mileage vehicles with the "Fresh" vehicles in your pool to balance wear.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# 11. USER MANUAL & GLOSSARY (NEW FEATURE)
# ---------------------------------------------------------
with st.expander("📚 User Manual & Glossary"):
    st.markdown("""
    ### 📖 Glossary of Terms
    * **CPK (Cost Per Kilometer):** A vital efficiency metric. Calculated as `Total Fuel Cost / Total Km`. Lower is better. A high CPK indicates an inefficient vehicle or driver.
    * **Ghost Asset:** A vehicle that is active in your system but has moved **0 km** during the reporting period. These are pure wasted cost.
    * **Active Vehicle Threshold:** The slider in the sidebar allows you to ignore vehicles with very low usage (e.g., < 10km) so they don't skew your average statistics.
    * **Global Weather Impact:** A multiplier in the sidebar. Use **1.0** for normal days. Use **1.1 or 1.2** for Summer months where AC usage increases fuel consumption by 10-20%.
    * **Maintenance Bands:**
        * 🟢 **Fresh:** < 50k km (Low risk, low maintenance cost)
        * 🟡 **Mid-Life:** 50k - 100k km (Medium risk, scheduled maintenance)
        * 🔴 **End-of-Life:** > 100k km (High risk, consider replacement)

    ### 🛠️ How to use the Filters
    1.  **Hierarchy:** The filters work in order: Location -> Make -> Status -> Vehicle.
    2.  **Comparison:** Select two specific Locations (e.g., Dubai vs Abu Dhabi) to see which branch has a better (lower) CPK in the "Cost Performance" chart.
    3.  **Export:** Use the "Download Filtered Report" button to get the clean data for your monthly presentation.
    """)
