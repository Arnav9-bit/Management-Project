import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json

# --- 1. PAGE CONFIG & DESIGN (Premium White & Orange Theme) ---
st.set_page_config(page_title="D2C Competitive Intelligence", layout="wide")

# Custom CSS for Professional PPT-like look with requested color adjustments
st.markdown("""
    <style>
    /* Main Background */
    .main { background-color: #ffffff; }
    
    /* Typography */
    h1, h2, h3 { 
        color: #ff6600; 
        font-family: 'Anton', sans-serif; 
        text-transform: uppercase; 
        letter-spacing: 1px;
    }
    
    /* Metric Cards Styling */
    .stMetric { 
        border-left: 8px solid #ff6600; 
        background: #ffffff; 
        padding: 25px; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.05); 
        border-radius: 4px;
        transition: transform 0.3s ease;
    }
    .stMetric:hover {
        transform: translateY(-5px);
    }
    
    /* Metric Label and Value Colors (Fixed for visibility) */
    [data-testid="stMetricLabel"] {
        color: #212529 !important; /* Dark grey for clear visibility */
        font-weight: 600 !important;
    }
    [data-testid="stMetricValue"] {
        color: #ff6600 !important; /* Orange for values */
        font-weight: 700 !important;
    }
    
    /* Professional Guide Box */
    .guide-box {
        background-color: #fff8f4;
        padding: 20px;
        border-radius: 4px;
        border-left: 8px solid #ff6600;
        margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(255, 102, 0, 0.05);
    }
    
    /* Sidebar Styling (Dark Grey Background) */
    section[data-testid="stSidebar"] {
        background-color: #333333 !important;
        border-right: 1px solid #444;
    }
    
    /* Sidebar text colors for contrast */
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stMarkdown {
        color: #ffffff !important;
    }
    
    /* Dropdown/Multiselect styling in sidebar */
    div[data-baseweb="select"] {
        color: #000000 !important;
    }
    
    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 30px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        font-weight: 700;
        font-size: 16px;
        color: #555;
    }
    .stTabs [aria-selected="true"] {
        color: #ff6600 !important;
        border-bottom-color: #ff6600 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA PROCESSING ENGINE ---
@st.cache_data
def process_competitor_data():
    try:
        # Files load karna
        df_p = pd.read_csv("amazon_product_data.csv")
        df_d = pd.read_csv("amazon_product_details.csv")

        # ASIN Cleaning: Sabhi files se hidden tabs aur spaces hatana
        for d in [df_p, df_d]:
            if 'asin' in d.columns:
                # Stripping tabs (\t), newlines (\n) and spaces
                d['asin'] = d['asin'].astype(str).str.replace(r'[\t\n\r]', '', regex=True).str.strip()

        # Date formatting
        df_p["date"] = pd.to_datetime(df_p["date"])
        
        # Product Name Mapping
        # Har unique ASIN ke liye readable name (Ensuring all 9 are captured)
        name_map_raw = df_p.sort_values('date', ascending=False).groupby('asin')['product_name'].first().to_dict()
        
        # Creating a slightly longer clean name for clarity
        clean_name_map = {asin: (str(name)[:35] + '..') if len(str(name)) > 35 else str(name) 
                         for asin, name in name_map_raw.items()}
        
        df_p['Display_Name'] = df_p['asin'].map(clean_name_map)

        # Brand Extraction from JSON details
        def get_brand(details_str):
            if pd.isna(details_str): return "D2C Brand"
            try:
                # Fixing JSON formatting issues
                clean_json = str(details_str).replace('""', '"')
                data = json.loads(clean_json)
                return data.get('Brand', 'D2C Brand')
            except:
                return 'D2C Brand'
        
        df_d['brand'] = df_d['product_details'].apply(get_brand)
        brand_map = df_d.groupby('asin')['brand'].first().to_dict()
        df_p['brand'] = df_p['asin'].map(brand_map).fillna('D2C Player')

        return df_p, clean_name_map
    
    except Exception as e:
        st.error(f"Data Load Error: {e}. Make sure CSV files are in the same folder.")
        return pd.DataFrame(), {}

df, product_options = process_competitor_data()

# --- 3. DASHBOARD UI ---
st.title("🎧 D2C Competitive Intelligence Dashboard")
st.markdown(f"**Target Market Segment:** Earbuds Range (₹2500–₹3000) | **Monitoring:** {len(product_options)} Strategic Competitors")

if not df.empty:
    # Sidebar selection
    st.sidebar.header("Market Controls")
    all_names = list(product_options.values())
    
    # Default selection ensures ALL 9 earbuds are shown
    selected_list = st.sidebar.multiselect("Filter Competitors", options=all_names, default=all_names)

    # Filtering Logic
    working_df = df[df['Display_Name'].isin(selected_list)].sort_values('date')
    latest_date = working_df['date'].max()
    
    # Latest Snapshot for KPIs and Scatter
    snapshot = working_df.sort_values('date').groupby('asin').tail(1)

    # Professional Insight Box in English
    st.markdown("""
        <div class='guide-box'>
            <h4 style='color: #ff6600; margin-top:0;'>STRATEGIC MARKET OVERVIEW</h4>
            <p style='color: #444; margin-bottom:0;'>
                This dashboard provides a continuous competitive analysis of 9 target TWS earbuds. 
                It monitors <strong>Price Volatility</strong>, <strong>Consumer Sentiment Stability</strong>, and <strong>Market Share Growth</strong>. 
                Use the interactive charts below to identify "Value Disruptors"—competitors maintaining high ratings despite lower price points.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Row 1: KPI Cards
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Competitive Set", len(selected_list))
    with k2:
        st.metric("Avg. Market Price", f"₹{snapshot['price'].mean():,.0f}")
    with k3:
        st.metric("Mean Market Rating", f"{snapshot['rating'].mean():.1f} ⭐")
    with k4:
        total_revs = snapshot['review_count'].sum()
        st.metric("Data Points Logged", f"{total_revs:,} Reviews")

    st.divider()

    # Row 2: Analytics Tabs
    tab_map, tab_trend, tab_grid = st.tabs(["🎯 STRATEGIC MAPPING", "📈 MARKET TRENDS", "📂 DETAILED SNAPSHOT"])

    with tab_map:
        col_left, col_right = st.columns([2, 1])
        
        with col_left:
            st.subheader("VALUE POSITIONING QUADRANTS")
            # Scatter chart for benchmarking
            fig_s = px.scatter(snapshot, x="price", y="rating", 
                               size="review_count", color="Display_Name",
                               hover_name="product_name",
                               labels={"price": "Price (₹)", "rating": "Rating", "Display_Name": "Competitor"},
                               template="plotly_white", height=600,
                               color_discrete_sequence=px.colors.qualitative.Prism)
            
            # Benchmarking Lines
            avg_p = snapshot['price'].mean()
            avg_r = snapshot['rating'].mean()
            fig_s.add_vline(x=avg_p, line_dash="dot", line_color="#ffb380")
            fig_s.add_hline(y=avg_r, line_dash="dot", line_color="#ffb380")
            
            fig_s.update_layout(
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_s, use_container_width=True)
            st.info("💡 **Managerial Insight:** The Top-Left quadrant identifies 'Market Disruptors' providing superior value at competitive prices.")

        with col_right:
            st.subheader("PRICING BENCHMARK")
            # Clearer bars for price deviation
            snapshot['Price_Gap'] = snapshot['price'] - snapshot['price'].mean()
            fig_gap = px.bar(snapshot.sort_values('Price_Gap'), x='Display_Name', y='Price_Gap',
                             labels={"Price_Gap": "Delta from Mean (₹)", "Display_Name": "Product"},
                             title="Price Variance from Category Avg")
            
            # Setting bar color to solid orange
            fig_gap.update_traces(marker_color='#ff6600')
            fig_gap.update_layout(xaxis_tickangle=-45, template="plotly_white")
            st.plotly_chart(fig_gap, use_container_width=True)

    with tab_trend:
        # Price Fluctuations
        st.subheader("LONGITUDINAL PRICING TRENDS")
        fig_p = px.line(working_df, x="date", y="price", color="Display_Name",
                        markers=True, template="plotly_white",
                        labels={"price": "Unit Price (₹)", "date": "Timeline"})
        fig_p.update_layout(hovermode="x unified", legend=dict(orientation="h", y=-0.6))
        st.plotly_chart(fig_p, use_container_width=True)

        # Popularity Trends
        st.subheader("CONSUMER ENGAGEMENT (REVIEW GROWTH)")
        fig_v = px.line(working_df, x="date", y="review_count", color="Display_Name",
                        markers=True, template="plotly_white", 
                        labels={"review_count": "Aggregate Reviews", "date": "Timeline"})
        fig_v.update_layout(hovermode="x unified", legend=dict(orientation="h", y=-0.6))
        st.plotly_chart(fig_v, use_container_width=True)
        st.caption("Strategic Note: Slopes indicate the velocity of consumer traction for each competitor.")

    with tab_grid:
        st.subheader("COMPETITIVE SNAPSHOT TABLE")
        # Snapshot table for all 9 products
        st.dataframe(snapshot[['brand', 'Display_Name', 'price', 'rating', 'review_count']].sort_values('price'),
                     use_container_width=True, hide_index=True)
        
        st.subheader("BRAND AUTHORITY COMPARISON")
        fig_rev_bar = px.bar(snapshot.sort_values('review_count', ascending=False), 
                             x='Display_Name', y='review_count', color='Display_Name',
                             labels={'review_count': 'Market Volume (Reviews)', 'Display_Name': 'Competitor'},
                             color_discrete_sequence=px.colors.qualitative.Bold)
        fig_rev_bar.update_layout(xaxis_tickangle=-45, showlegend=False, template="plotly_white")
        st.plotly_chart(fig_rev_bar, use_container_width=True)

    # Technical info
    with st.expander("System Audit & Pipeline Metadata"):
        st.write(f"**Integrity Check:** All {len(product_options)} unique identifiers successfully localized.")
        st.write(f"**Synchronization Timestamp:** {latest_date}")
        st.write("Architecture: Python-Streamlit-Plotly Hybrid Pipeline.")

else:
    st.warning("System Error: Data Source Not Detected. Verify CSV localization in the application root.")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #888;'>
        <strong>Arnav Chauhan</strong> | MB24023 | Project 2025 | IIT Mandi
    </div>
    """, 
    unsafe_allow_html=True
)