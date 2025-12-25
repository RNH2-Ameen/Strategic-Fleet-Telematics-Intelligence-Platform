import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(
    page_title="Asset Efficiency Guardian",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    
    /* Metric Cards */
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    .metric-label { font-size: 14px; color: #6c757d; font-weight: 600; text-transform: uppercase;}
    .metric-value { font-size: 28px; font-weight: bold; margin: 5px 0; }
    .metric-delta { font-size: 14px; font-weight: 500; }
    
    .color-neutral { color: #2980b9; } 
    .color-good { color: #00C853; }     
    .color-bad { color: #FF1744; }      
    
    /* Legend Badges */
    .legend-badge {
        display: inline-block;
        padding: 4px 8px;
        margin-right: 10px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: bold;
    }
    
    /* Planner Box */
    .planner-box {
        background-color: #e8f5e9;
        border: 1px solid #00C853;
        padding: 20px;
        border-radius: 10px;
        color: #1b5e20;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. DATA PROCESSING ENGINE
# ---------------------------------------------------------
def time_to_hours(time_str):
    try:
        if pd.isna(time_str): return 0.0
        if isinstance(time_str, (int, float)): return float(time_str) * 24
        parts = list(map(int, str(time_str).split(':')))
        return round(parts[0] + parts[1]/60 + parts[2]/3600, 2)
    except:
        return 0.0

@st.cache_data
def load_and_clean_data(file):
    try:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file, header=2)
        else:
            df = pd.read_excel(file, header=2, engine='openpyxl')
        
        df.columns = df.columns.str.strip()
        
        # Validation
        required_columns = ['Grouping', 'Engine hours', 'Boom Operation time']
        if not all(col in df.columns for col in required_columns):
            st.error(f"⚠️ Column Error: The uploaded file is missing one of these required columns: {required_columns}")
            st.stop()

        col_map = {
            'Grouping': 'Date', 'Engine hours': 'Engine_Raw', 
            'Boom Operation time': 'Work_Raw', 'Utilization %': 'Util_Pct'
        }
        df = df.rename(columns=col_map)
        
        df = df.dropna(subset=['Date'])
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date'])
        
        df['Engine_Hours'] = df['Engine_Raw'].apply(time_to_hours)
        df['Work_Hours'] = df['Work_Raw'].apply(time_to_hours)
        
        # LOGIC
        df['Idle_Hours'] = df['Engine_Hours'] - df['Work_Hours']
        df['Idle_Hours'] = df['Idle_Hours'].clip(lower=0)
        
        # Efficiency Calculation
        df['Utilization'] = df.apply(
            lambda x: (x['Work_Hours'] / x['Engine_Hours'] * 100) if x['Engine_Hours'] > 0 else 0, 
            axis=1
        )
        
        return df.sort_values('Date')
    except Exception as e:
        st.error(f"Error processing file: {e}")
        st.stop()

# ---------------------------------------------------------
# 3. SIDEBAR CONTROLS
# ---------------------------------------------------------
with st.sidebar:
    st.title("🚜 Asset Manager")
    
    uploaded_file = st.file_uploader("Upload Report", type=['csv', 'xlsx'])
    
    selected_dates_raw = []

    if uploaded_file:
        df_temp = load_and_clean_data(uploaded_file)
        date_options = ['Select All'] + sorted([str(d) for d in df_temp['Date'].dt.date.unique()])
        
        st.divider()
        st.markdown("### 📅 Time Filter")
        
        selected_dates_raw = st.multiselect(
            "Filter Dates:", 
            options=date_options,
            default=['Select All']
        )
        
    st.divider()
    st.markdown("### 🎯 KPI Thresholds")
    
    target_util = st.slider("Goal: Efficiency %", 30, 95, 60, help="Set your target (e.g., 60%).")
    max_idle = st.slider("Limit: Max Idle (Hrs)", 0.5, 8.0, 1.5, help="How many hours of idle are acceptable?")

# ---------------------------------------------------------
# 4. MAIN DASHBOARD
# ---------------------------------------------------------
if uploaded_file:
    # 1. Load Data
    df_full = load_and_clean_data(uploaded_file)
    
    # 2. Logic for "Select All"
    if not selected_dates_raw or 'Select All' in selected_dates_raw:
        df = df_full.copy()
        current_view = "All Dates"
    else:
        selected_dates = [pd.to_datetime(d).date() for d in selected_dates_raw]
        df = df_full[df_full['Date'].dt.date.isin(selected_dates)].copy()
        current_view = f"{len(selected_dates)} Selected Day(s)"

    # --- Top KPIs Calculation ---
    total_engine = df['Engine_Hours'].sum()
    total_work = df['Work_Hours'].sum()
    total_idle = df['Idle_Hours'].sum()
    period_util = (total_work / total_engine * 100) if total_engine > 0 else 0
    
    eff_color_class = "color-good" if period_util >= target_util else "color-bad"
    eff_icon = "✅" if period_util >= target_util else "⚠️"

    st.title("Operational Efficiency Dashboard")
    st.caption(f"Viewing: {current_view}")

    # --- METRIC CARDS ---
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Engine ON</div>
            <div class="metric-value color-neutral">{total_engine:,.1f} h</div>
            <div class="metric-delta">Runtime</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Productive Boom Time</div>
            <div class="metric-value color-good">{total_work:,.1f} h</div>
            <div class="metric-delta">Work</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Idle Waste</div>
            <div class="metric-value color-bad">{total_idle:,.1f} h</div>
            <div class="metric-delta">Lost Time</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Period Efficiency</div>
            <div class="metric-value {eff_color_class}">{period_util:.1f}%</div>
            <div class="metric-delta">Goal: {target_util}% {eff_icon}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # --- ROW 1: TREND ---
    col_trend, col_pie = st.columns([2, 1])
    config = {'displayModeBar': False}

    with col_trend:
        st.subheader("📈 Efficiency Trend")
        if len(df) > 1:
            fig_trend = go.Figure()
            # STYLE CHANGE: 'spline' for smooth curves
            fig_trend.add_trace(go.Scatter(
                x=df['Date'], y=df['Utilization'],
                mode='lines+markers',
                name='Efficiency',
                line=dict(color='#00C853', width=3, shape='spline'), # <--- Spline for curves
                marker=dict(size=6, color='#00C853', line=dict(width=2, color='white')), 
                fill='tozeroy', fillcolor='rgba(0, 200, 83, 0.05)' # Lighter fill
            ))
            fig_trend.add_hline(
                y=target_util, line_dash="dash", line_color="#FF1744", line_width=2,
                annotation_text=f"Goal: {target_util}%", annotation_position="top left",
                annotation_font=dict(color="#FF1744")
            )
            fig_trend.update_layout(
                yaxis_title="Efficiency %", height=350,
                xaxis=dict(
                    rangeselector=dict(
                        buttons=list([
                            dict(count=7, label="1W", step="day", stepmode="backward"),
                            dict(count=1, label="1M", step="month", stepmode="backward"),
                            dict(count=3, label="3M", step="month", stepmode="backward"),
                            dict(step="all", label="ALL")
                        ]),
                        bgcolor="#f8f9fa", activecolor="#d1fae5",
                    ),
                    type="date", showgrid=False
                ),
                yaxis=dict(range=[0, 110], showgrid=True, gridcolor='#f0f0f0'),
                plot_bgcolor="white", hovermode="x unified"
            )
            st.plotly_chart(fig_trend, use_container_width=True, config=config)
        else:
            st.info("Select multiple days to see a trend line.")

    with col_pie:
        st.subheader("🍰 Boom vs Idle Split")
        pie_data = pd.DataFrame({
            'Category': ['Boom Active (Good)', 'Idle (Waste)'],
            'Hours': [total_work, total_idle]
        })
        # STYLE CHANGE: Donut chart with center text
        fig_pie = px.pie(pie_data, names='Category', values='Hours', hole=0.7,
                         color='Category',
                         color_discrete_map={'Boom Active (Good)':'#00C853', 'Idle (Waste)':'#FF1744'})
        
        # Add center annotation
        fig_pie.add_annotation(text=f"{total_engine:,.0f}h", showarrow=False, font_size=20, x=0.5, y=0.5)
        fig_pie.add_annotation(text="Total", showarrow=False, font_size=12, x=0.5, y=0.4)
        
        fig_pie.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig_pie, use_container_width=True, config=config)

    # --- ROW 2: DETECTIVE ---
    st.subheader("🕵️ The Waste Detective")
    fig_stack = go.Figure()
    fig_stack.add_trace(go.Bar(
        x=df['Date'], y=df['Work_Hours'], name='Productive Work',
        marker_color='#00C853' 
    ))
    fig_stack.add_trace(go.Bar(
        x=df['Date'], y=df['Idle_Hours'], name='Idle Waste',
        marker_color='#FF1744' 
    ))
    fig_stack.update_layout(
        barmode='stack', height=400, yaxis_title="Total Hours",
        hovermode="x unified", legend=dict(orientation="h", y=1.1),
        plot_bgcolor='white', # Cleaner background
        xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#f0f0f0')
    )
    st.plotly_chart(fig_stack, use_container_width=True, config=config)

    # --- ROW 3: PERFORMANCE LOG ---
    st.subheader("📋 Performance Log")
    
    st.markdown(f"""
    <div style="margin-bottom: 10px;">
        <span class="legend-badge" style="background-color: #ffe5e5; color: #FF1744; border: 1px solid #FF1744;">
            🔴 High Waste (Idle > {max_idle}h)
        </span>
        <span class="legend-badge" style="color: #00C853; font-weight: bold; border: 1px solid #00C853;">
            🟢 High Efficiency (Goal > {target_util}%)
        </span>
        <span class="legend-badge" style="color: #95a5a6; font-style: italic; border: 1px solid #95a5a6;">
            ⚪ Low Usage (Runtime < 1h)
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    def highlight_rows(row):
        if row['Engine_Hours'] < 1.0:
            return ['color: #95a5a6; font-style: italic;'] * len(row)
        elif row['Idle_Hours'] > max_idle:
            return ['color: #FF1744; font-weight: bold; background-color: #ffe5e5'] * len(row)
        elif row['Utilization'] > target_util:
            return ['color: #00C853; font-weight: bold;'] * len(row)
        else:
            return ['color: black'] * len(row)

    display_cols = ['Date', 'Engine_Hours', 'Work_Hours', 'Idle_Hours', 'Utilization']
    
    st.dataframe(
        df[display_cols].style
        .format({
            'Engine_Hours': '{:.2f} h',
            'Work_Hours': '{:.2f} h',
            'Idle_Hours': '{:.2f} h',
            'Utilization': '{:.1f}%',
            'Date': '{:%Y-%m-%d}'
        })
        .apply(highlight_rows, axis=1),
        use_container_width=True
    )
    
    # ---------------------------------------------------------
    # 5. NEW: NEXT MONTH'S PLANNER (FRIEND'S IDEA)
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("🔮 Next Month's Planner")
    
    # Calculate Recommendations
    real_days = df[df['Engine_Hours'] > 1.0]
    
    if len(real_days) > 0:
        avg_eff = real_days['Utilization'].mean()
        best_eff = real_days['Utilization'].max()
        recommended_goal = real_days['Utilization'].quantile(0.75)
        
        c_plan1, c_plan2 = st.columns([3, 1])
        with c_plan1:
            st.markdown(f"""
            <div class="planner-box">
                <h4>🎯 AI Goal Recommendation: <b>{recommended_goal:.1f}%</b></h4>
                <p>Based on your current performance, setting your goal to <b>{recommended_goal:.0f}%</b> next month is achievable.</p>
                <ul>
                    <li><b>Current Average:</b> {avg_eff:.1f}% (Baseline)</li>
                    <li><b>Your Best Day:</b> {best_eff:.1f}% (Peak Potential)</li>
                    <li><b>Why {recommended_goal:.0f}%?</b> This matches the performance of your top 25% best operating days. It pushes the team to be like their "best selves" more often.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
        with c_plan2:
            st.info("💡 **Pro Tip:** Share this number with your operators. 'Let's try to hit our Top 25% level every day.'")
    else:
        st.warning("Not enough data to generate a recommendation (need days with >1 hour runtime).")

    # ---------------------------------------------------------
    # 6. GLOSSARY
    # ---------------------------------------------------------
    with st.expander("📚 User Manual & Glossary"):
        st.markdown(f"""
        ### 📖 Definitions
        * **Engine Hours:** Total time key was ON.
        * **Boom Operation:** Time machine was working.
        * **Idle Waste:** Time engine was ON but not working.
        * **Utilization %:** (Boom / Engine) * 100.
        """)

else:
    st.info("👋 Upload your **Telematics Report** to begin analysis.")
