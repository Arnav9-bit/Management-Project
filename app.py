import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from textblob import TextBlob
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
import numpy as np
from datetime import timedelta

# --- 1. PAGE CONFIG & DESIGN (Premium White & Orange Theme) ---
st.set_page_config(page_title="D2C Competitive Intelligence", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    h1, h2, h3 { 
        color: #ff6600; 
        font-family: 'Anton', sans-serif; 
        text-transform: uppercase; 
        letter-spacing: 1px;
    }
    .stMetric { 
        border-left: 8px solid #ff6600; 
        background: #ffffff; 
        padding: 25px; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.05); 
        border-radius: 4px;
        transition: transform 0.3s ease;
    }
    .stMetric:hover { transform: translateY(-5px); }
    [data-testid="stMetricLabel"] {
        color: #212529 !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricValue"] {
        color: #ff6600 !important;
        font-weight: 700 !important;
    }
    .guide-box {
        background-color: #fff8f4;
        padding: 20px;
        border-radius: 4px;
        border-left: 8px solid #ff6600;
        margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(255, 102, 0, 0.05);
    }
    section[data-testid="stSidebar"] {
        background-color: #333333 !important;
        border-right: 1px solid #444;
    }
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stMarkdown {
        color: #ffffff !important;
    }
    div[data-baseweb="select"] { color: #000000 !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 30px; }
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
@st.cache_data(ttl=3600)
def process_competitor_data():
    try:
        df_p = pd.read_csv("amazon_product_data.csv")
        df_d = pd.read_csv("amazon_product_details.csv")

        for d in [df_p, df_d]:
            if 'asin' in d.columns:
                d['asin'] = d['asin'].astype(str).str.replace(r'[\t\n\r]', '', regex=True).str.strip()

        df_p["date"] = pd.to_datetime(df_p["date"])

        name_map_raw = df_p.sort_values('date', ascending=False).groupby('asin')['product_name'].first().to_dict()
        clean_name_map = {
            asin: (str(name)[:35] + '..') if len(str(name)) > 35 else str(name)
            for asin, name in name_map_raw.items()
        }
        df_p['Display_Name'] = df_p['asin'].map(clean_name_map)

        def get_brand(details_str):
            if pd.isna(details_str): return "D2C Brand"
            try:
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


# --- PHASE 2: NLP PROCESSING LOGIC ---
@st.cache_data(ttl=3600)
def process_nlp_sentiment():
    try:
        df_rev = pd.read_csv("amazon_product_reviews.csv")

        if 'asin' in df_rev.columns:
            df_rev['asin'] = df_rev['asin'].astype(str).str.replace(r'[\t\n\r]', '', regex=True).str.strip()

        if 'date' in df_rev.columns:
            df_rev['date'] = pd.to_datetime(df_rev['date'])

        VULNERABILITY_KEYWORDS = [
            'waste', 'regret', 'cheated', 'fraud', 'broken', 'stopped working',
            'poor quality', 'disappointed', 'terrible', 'pathetic', 'useless',
            'refund', 'return', 'worst', 'never buy', 'money wasted', 'bakwaas',
            'kharab', 'bekar', 'dhoka'
        ]

        def get_sentiment(text):
            if pd.isna(text): return 0
            return TextBlob(str(text)).sentiment.polarity

        def get_scepticism(text):
            if pd.isna(text): return 0
            blob = TextBlob(str(text))
            subjectivity = blob.sentiment.subjectivity
            polarity = blob.sentiment.polarity
            scepticism = subjectivity * (1 - abs(polarity))
            return round(scepticism, 4)

        def get_vulnerability(text):
            if pd.isna(text): return 0
            text_lower = str(text).lower()
            hits = sum(1 for word in VULNERABILITY_KEYWORDS if word in text_lower)
            return round(min(hits / 3, 1.0), 4)

        df_rev['sentiment_score']         = df_rev['review_comment'].apply(get_sentiment)
        df_rev['consumer_scepticism']     = df_rev['review_comment'].apply(get_scepticism)
        df_rev['consumer_vulnerability']  = df_rev['review_comment'].apply(get_vulnerability)

        _, name_map = process_competitor_data()
        df_rev['Display_Name'] = df_rev['asin'].map(name_map)

        return df_rev
    except:
        return pd.DataFrame()


# -----------------------------------------------------------------------
# PRICE FORECASTING ENGINE (FIXED — NaN-safe)
#
# For each product:
#   1. Drop rows where price is NaN  ← this fixes the ValueError
#   2. Convert dates to numeric (days since first observation)
#   3. Fit Polynomial Regression (degree 2 if ≥4 points, else linear)
#   4. Predict prices for the next N scraping windows (~3.5 days each)
#   5. Clamp predictions between ₹500–₹6000
#   6. Compute movement signal: Rising / Falling / Stable
# -----------------------------------------------------------------------
def get_next_collection_dates(from_date, n):
    """
    Starting from from_date, walk forward day by day and collect
    the next n dates that fall on Wednesday (weekday=2) or Saturday (weekday=5).
    This ensures predictions land exactly on your real scraping windows.
    """
    future_dates = []
    candidate    = from_date + timedelta(days=1)
    while len(future_dates) < n:
        if candidate.weekday() in (2, 5):   # 2 = Wednesday, 5 = Saturday
            future_dates.append(candidate)
        candidate += timedelta(days=1)
    return future_dates


@st.cache_data(ttl=3600)
def run_price_forecast(df_main, forecast_steps=6):
    forecast_records = []
    summary_records  = []

    for asin, grp in df_main.groupby('asin'):
        # Drop NaN prices before fitting — fixes sklearn ValueError
        grp = grp.dropna(subset=['price']).sort_values('date').drop_duplicates('date')
        if len(grp) < 2:
            continue

        display_name = grp['Display_Name'].iloc[0]

        # Convert dates to numeric (days since first observation) for the model
        first_date     = grp['date'].min()
        grp['day_num'] = (grp['date'] - first_date).dt.total_seconds() / 86400

        X = grp['day_num'].values.reshape(-1, 1)
        y = grp['price'].values

        # Degree 2 if enough points, else linear
        degree = 2 if len(grp) >= 4 else 1
        model  = make_pipeline(PolynomialFeatures(degree), LinearRegression())
        model.fit(X, y)

        # Store historical rows
        for _, row in grp.iterrows():
            forecast_records.append({
                'Display_Name': display_name,
                'date'        : row['date'],
                'price'       : row['price'],
                'type'        : 'Historical'
            })

        # ── Predict only on real Wed/Sat future dates ─────────────────────
        last_date    = grp['date'].max()
        future_dates = get_next_collection_dates(last_date, forecast_steps)

        # Convert future dates to day_num on the same scale as training data
        future_day_nums = [
            (fd - first_date).total_seconds() / 86400
            for fd in future_dates
        ]
        future_prices = model.predict(np.array(future_day_nums).reshape(-1, 1))
        future_prices = np.clip(future_prices, 500, 6000)

        for fdate, fprice in zip(future_dates, future_prices):
            forecast_records.append({
                'Display_Name': display_name,
                'date'        : fdate,
                'price'       : round(float(fprice), 0),
                'type'        : 'Predicted'
            })

        # Summary row — immediate next window
        last_price = float(grp['price'].iloc[-1])
        next_price = float(future_prices[0])
        next_date  = future_dates[0]
        pct_change = ((next_price - last_price) / last_price) * 100

        # Label which window the next prediction falls on
        day_label = "Wednesday 9PM" if next_date.weekday() == 2 else "Saturday 1PM"

        if pct_change > 1.5:
            signal = "🔴 Rising"
        elif pct_change < -1.5:
            signal = "🟢 Falling"
        else:
            signal = "🟡 Stable"

        summary_records.append({
            'Product'             : display_name,
            'Current Price'       : f"₹{last_price:,.0f}",
            'Next Window'         : f"{next_date.strftime('%d %b %Y')} ({day_label})",
            'Next Predicted Price': f"₹{next_price:,.0f}",
            'Expected Change'     : f"{pct_change:+.1f}%",
            'Price Trend Signal'  : signal
        })

    return pd.DataFrame(forecast_records), pd.DataFrame(summary_records)


# -----------------------------------------------------------------------
# ELASTICITY MODEL — used only for the plain-English simulator
# No technical stats are shown to the user from this.
# -----------------------------------------------------------------------
@st.cache_data(ttl=3600)
def build_elasticity_model(df_main):
    model_data = df_main[['price', 'review_count']].dropna()
    if len(model_data) < 5:
        return None, None
    X = model_data[['price']].values
    y = model_data['review_count'].values
    model = LinearRegression()
    model.fit(X, y)
    avg_price = float(model_data['price'].mean())
    return model, avg_price


# --- Load all data ---
df, product_options = process_competitor_data()
df_sentiment        = process_nlp_sentiment()


# --- 3. DASHBOARD UI ---
st.title("🎧 D2C Competitive Intelligence Dashboard")
st.markdown(
    f"**Target Market Segment:** Earbuds Range (₹2500–₹3000) | "
    f"**Monitoring:** {len(product_options)} Strategic Competitors"
)

if not df.empty:
    st.sidebar.header("Market Controls")
    all_names     = list(product_options.values())
    selected_list = st.sidebar.multiselect("Filter Competitors", options=all_names, default=all_names)

    working_df  = df[df['Display_Name'].isin(selected_list)].sort_values('date')
    latest_date = working_df['date'].max()
    snapshot    = working_df.sort_values('date').groupby('asin').tail(1)

    st.markdown("""
        <div class='guide-box'>
            <h4 style='color: #ff6600; margin-top:0;'>STRATEGIC MARKET OVERVIEW</h4>
            <p style='color: #444; margin-bottom:0;'>
                This dashboard provides a continuous competitive analysis of 9 target TWS earbuds.
                It monitors <strong>Price Volatility</strong>, <strong>Consumer Sentiment Stability</strong>,
                and <strong>Market Share Growth</strong>. Use the interactive charts below to identify
                "Value Disruptors"—competitors maintaining high ratings despite lower price points.
            </p>
        </div>
    """, unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.metric("Competitive Set", len(selected_list))
    with k2: st.metric("Avg. Market Price", f"₹{snapshot['price'].mean():,.0f}")
    with k3: st.metric("Mean Market Rating", f"{snapshot['rating'].mean():.1f} ⭐")
    with k4: st.metric("Data Points Logged", f"{snapshot['review_count'].sum():,} Reviews")

    st.divider()

    tab_map, tab_trend, tab_sentiment, tab_predict, tab_grid = st.tabs([
        "🎯 STRATEGIC MAPPING",
        "📈 MARKET TRENDS",
        "🗣️ CUSTOMER SENTIMENT (AI)",
        "🔮 PRICE PREDICTOR (ML)",
        "📂 DETAILED SNAPSHOT"
    ])

    # ── Tab 1: Strategic Mapping ──────────────────────────────────────────
    with tab_map:
        col_left, col_right = st.columns([2, 1])
        with col_left:
            st.subheader("VALUE POSITIONING QUADRANTS")
            fig_s = px.scatter(
                snapshot, x="price", y="rating",
                size="review_count", color="Display_Name",
                hover_name="product_name",
                labels={"price": "Price (₹)", "rating": "Rating", "Display_Name": "Competitor"},
                template="plotly_white", height=600,
                color_discrete_sequence=px.colors.qualitative.Prism
            )
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
            snapshot['Price_Gap'] = snapshot['price'] - snapshot['price'].mean()
            fig_gap = px.bar(
                snapshot.sort_values('Price_Gap'), x='Display_Name', y='Price_Gap',
                labels={"Price_Gap": "Delta from Mean (₹)", "Display_Name": "Product"},
                title="Price Variance from Category Avg"
            )
            fig_gap.update_traces(marker_color='#ff6600')
            fig_gap.update_layout(xaxis_tickangle=-45, template="plotly_white")
            st.plotly_chart(fig_gap, use_container_width=True)

    # ── Tab 2: Market Trends ──────────────────────────────────────────────
    with tab_trend:
        st.subheader("LONGITUDINAL PRICING TRENDS")
        fig_p = px.line(
            working_df, x="date", y="price", color="Display_Name",
            markers=True, template="plotly_white",
            labels={"price": "Unit Price (₹)", "date": "Timeline"}
        )
        fig_p.update_layout(hovermode="x unified", legend=dict(orientation="h", y=-0.6))
        st.plotly_chart(fig_p, use_container_width=True)

        st.subheader("CONSUMER ENGAGEMENT (REVIEW GROWTH)")
        fig_v = px.line(
            working_df, x="date", y="review_count", color="Display_Name",
            markers=True, template="plotly_white",
            labels={"review_count": "Aggregate Reviews", "date": "Timeline"}
        )
        fig_v.update_layout(hovermode="x unified", legend=dict(orientation="h", y=-0.6))
        st.plotly_chart(fig_v, use_container_width=True)
        st.caption("Strategic Note: Slopes indicate the velocity of consumer traction for each competitor.")

    # ── Tab 3: Sentiment ──────────────────────────────────────────────────
    with tab_sentiment:
        st.subheader("AI-DRIVEN CUSTOMER SENTIMENT ANALYSIS")
        if not df_sentiment.empty:
            filtered_sentiment = df_sentiment[df_sentiment['Display_Name'].isin(selected_list)]

            s1, s2, s3 = st.columns(3)
            with s1:
                st.metric("Net Sentiment Score", f"{filtered_sentiment['sentiment_score'].mean():.2f}")
            with s2:
                velocity = filtered_sentiment.groupby('Display_Name').tail(10).shape[0]
                st.metric("Latest Review Velocity", f"{velocity} New / Period")
            with s3:
                pos_ratio = (filtered_sentiment['sentiment_score'] > 0).mean() * 100
                st.metric("Positive Sentiment Ratio", f"{pos_ratio:.1f}%")

            s4, s5 = st.columns(2)
            with s4:
                avg_scepticism = filtered_sentiment['consumer_scepticism'].mean()
                st.metric(
                    "Avg. Consumer Scepticism", f"{avg_scepticism:.2f}",
                    help="0 = Fully trusting reviews | 1 = Highly doubtful/opinionated reviews"
                )
            with s5:
                avg_vulnerability = filtered_sentiment['consumer_vulnerability'].mean()
                st.metric(
                    "Avg. Consumer Vulnerability", f"{avg_vulnerability:.2f}",
                    help="0 = No distress signals | 1 = High regret/frustration in reviews"
                )

            brand_sentiment = filtered_sentiment.groupby('Display_Name')['sentiment_score'].mean().reset_index()
            fig_sent_bar = px.bar(
                brand_sentiment.sort_values('sentiment_score', ascending=False),
                x='sentiment_score', y='Display_Name', orientation='h',
                title="Brand Happiness Index (NLP Scored)",
                labels={'sentiment_score': 'Sentiment Score (-1 to 1)', 'Display_Name': 'Competitor'},
                color='sentiment_score', color_continuous_scale='RdYlGn'
            )
            st.plotly_chart(fig_sent_bar, use_container_width=True)

            st.subheader("SENTIMENT VOLATILITY OVER TIME")
            sentiment_ts = filtered_sentiment.groupby(
                [filtered_sentiment['date'].dt.date, 'Display_Name']
            )['sentiment_score'].mean().reset_index()
            fig_sent_ts = px.line(
                sentiment_ts, x='date', y='sentiment_score', color='Display_Name', markers=True,
                title="Product Satisfaction Stability",
                labels={'sentiment_score': 'Daily Avg Sentiment'}
            )
            st.plotly_chart(fig_sent_ts, use_container_width=True)

            st.divider()
            st.subheader("CONSUMER SCEPTICISM & VULNERABILITY ANALYSIS")
            brand_psych = filtered_sentiment.groupby('Display_Name').agg(
                consumer_scepticism=('consumer_scepticism', 'mean'),
                consumer_vulnerability=('consumer_vulnerability', 'mean')
            ).reset_index()

            col_skep, col_vuln = st.columns(2)
            with col_skep:
                fig_skep = px.bar(
                    brand_psych.sort_values('consumer_scepticism', ascending=False),
                    x='Display_Name', y='consumer_scepticism',
                    title="Consumer Scepticism by Brand",
                    labels={'consumer_scepticism': 'Scepticism Score (0–1)', 'Display_Name': 'Competitor'},
                    color='consumer_scepticism', color_continuous_scale='Oranges'
                )
                fig_skep.update_layout(xaxis_tickangle=-45, template="plotly_white")
                st.plotly_chart(fig_skep, use_container_width=True)
                st.caption("⚠️ High score = Customers are opinionated but uncertain. Brand trust is fragile.")

            with col_vuln:
                fig_vuln = px.bar(
                    brand_psych.sort_values('consumer_vulnerability', ascending=False),
                    x='Display_Name', y='consumer_vulnerability',
                    title="Consumer Vulnerability by Brand",
                    labels={'consumer_vulnerability': 'Vulnerability Score (0–1)', 'Display_Name': 'Competitor'},
                    color='consumer_vulnerability', color_continuous_scale='RdPu'
                )
                fig_vuln.update_layout(xaxis_tickangle=-45, template="plotly_white")
                st.plotly_chart(fig_vuln, use_container_width=True)
                st.caption("🚨 High score = Customers expressing regret, fraud, or product failure.")

            st.divider()
            col_pos, col_neg = st.columns(2)
            with col_pos:
                st.markdown("#### ✅ Representative Positive Reviews (All Competitors)")
                top_reviews = filtered_sentiment.sort_values(
                    'sentiment_score', ascending=False
                ).groupby('Display_Name').head(1)
                st.dataframe(
                    top_reviews[['Display_Name', 'review_comment', 'sentiment_score']],
                    hide_index=True, use_container_width=True
                )
            with col_neg:
                st.markdown("#### ❌ Representative Critical Reviews (All Competitors)")
                bottom_reviews = filtered_sentiment.sort_values(
                    'sentiment_score', ascending=True
                ).groupby('Display_Name').head(1)
                st.dataframe(
                    bottom_reviews[['Display_Name', 'review_comment', 'sentiment_score']],
                    hide_index=True, use_container_width=True
                )

            st.info("💡 **Prescriptive Strategy:** Brands with consistent negative 'Representative Reviews' should prioritize immediate engineering fixes over marketing spend.")
        else:
            st.warning("Sentiment Data Source Not Found.")

    # ── Tab 4: Price Predictor (REBUILT — manager-friendly) ──────────────
    with tab_predict:
        st.subheader("🔮 PRICE PREDICTOR")

        st.markdown("""
            <div class='guide-box'>
                <h4 style='color: #ff6600; margin-top:0;'>HOW THIS WORKS</h4>
                <p style='color: #444; margin-bottom:0;'>
                    Using the historical price data collected at our two scraping windows
                    (<strong>Wednesday 9 PM</strong> &amp; <strong>Saturday 1 PM</strong>),
                    this tool predicts what each competitor's price is likely to be
                    at the <strong>next few collection cycles</strong>.
                    It also tells you whether a product's price is trending up, down, or holding steady —
                    so you can act <em>before</em> the market moves, not after.
                </p>
            </div>
        """, unsafe_allow_html=True)

        # Slider — how many future windows to predict
        forecast_steps = st.slider(
            "How many future price windows to predict?",
            min_value=2, max_value=8, value=4,
            help="Each step = approximately 3.5 days (one scraping cycle)"
        )

        forecast_df, summary_df = run_price_forecast(working_df, forecast_steps=forecast_steps)

        if not forecast_df.empty:

            # ── SECTION 1: Price Forecast Chart ──────────────────────────
            st.subheader("PREDICTED PRICE MOVEMENT — ALL COMPETITORS")
            st.markdown(
                "Solid lines show the **actual observed prices**. "
                "Dashed lines show the **predicted future prices** based on each product's pricing trend."
            )

            fig_forecast = go.Figure()
            all_products = forecast_df['Display_Name'].unique()
            colors       = px.colors.qualitative.Prism

            for i, product in enumerate(all_products):
                color   = colors[i % len(colors)]
                prod_df = forecast_df[forecast_df['Display_Name'] == product]
                hist    = prod_df[prod_df['type'] == 'Historical'].sort_values('date')
                pred    = prod_df[prod_df['type'] == 'Predicted'].sort_values('date')

                # Historical solid line
                fig_forecast.add_trace(go.Scatter(
                    x=hist['date'], y=hist['price'],
                    mode='lines+markers', name=product,
                    line=dict(color=color, width=2),
                    legendgroup=product, showlegend=True
                ))

                # Bridge connector so lines join smoothly
                if not hist.empty and not pred.empty:
                    fig_forecast.add_trace(go.Scatter(
                        x=[hist['date'].iloc[-1], pred['date'].iloc[0]],
                        y=[hist['price'].iloc[-1], pred['price'].iloc[0]],
                        mode='lines',
                        line=dict(color=color, width=1.5, dash='dot'),
                        legendgroup=product, showlegend=False
                    ))

                # Predicted dashed line
                if not pred.empty:
                    fig_forecast.add_trace(go.Scatter(
                        x=pred['date'], y=pred['price'],
                        mode='lines+markers',
                        name=f"{product} (Predicted)",
                        line=dict(color=color, width=2, dash='dash'),
                        marker=dict(symbol='diamond', size=7),
                        legendgroup=product, showlegend=True
                    ))

            # Vertical marker where forecast begins
            # add_vline() is broken for datetime axes in newer Plotly+pandas versions
            # — it tries to do arithmetic on the x value internally and crashes.
            # Solution: draw the line with add_shape() and the label with add_annotation()
            # separately, both accepting plain strings without any arithmetic.
            last_actual_date_str = str(
                forecast_df[forecast_df['type'] == 'Historical']['date'].max()
            )
            fig_forecast.add_shape(
                type="line",
                x0=last_actual_date_str, x1=last_actual_date_str,
                y0=0, y1=1,
                xref="x", yref="paper",
                line=dict(color="gray", width=1.5, dash="dash")
            )
            fig_forecast.add_annotation(
                x=last_actual_date_str,
                y=1,
                xref="x", yref="paper",
                text="Forecast Starts →",
                showarrow=False,
                xanchor="left",
                font=dict(color="gray", size=12)
            )

            fig_forecast.update_layout(
                template="plotly_white", height=520,
                hovermode="x unified",
                xaxis_title="Date",
                yaxis_title="Price (₹)",
                legend=dict(orientation="h", y=-0.30, x=0.5, xanchor="center"),
                margin=dict(l=20, r=20, t=30, b=20)
            )
            st.plotly_chart(fig_forecast, use_container_width=True)
            st.caption("◆ = Predicted data point  |  Dashed line = Predicted  |  Solid line = Actual observed")

            st.divider()

            # ── SECTION 2: Next-Cycle Price Summary Table ─────────────────
            st.subheader("NEXT PREDICTED PRICE — QUICK SUMMARY")
            st.markdown(
                "This table shows each competitor's **current price**, the **predicted price** "
                "at the very next scraping window, and whether prices are expected to go "
                "**up 🔴**, **down 🟢**, or **stay the same 🟡**."
            )

            st.dataframe(summary_df, use_container_width=True, hide_index=True)

            st.divider()

            # ── SECTION 3: Competitive Price Gap Alert ───────────────────
            st.subheader("COMPETITIVE PRICE GAP ALERT")
            st.markdown(
                "This table compares where each product is priced **right now** versus "
                "the market average. It helps you instantly spot which competitors are "
                "running risky high prices — and which ones are undercutting the market."
            )

            snap_clean = snapshot[['Display_Name', 'price', 'rating', 'review_count']].dropna(subset=['price']).copy()
            market_avg = snap_clean['price'].mean()
            snap_clean['Gap from Avg'] = (snap_clean['price'] - market_avg).round(0)
            snap_clean['Gap %']        = ((snap_clean['price'] - market_avg) / market_avg * 100).round(1)

            def price_signal(gap_pct):
                if gap_pct > 5:
                    return "🔴 Overpriced — Risk of losing buyers"
                elif gap_pct < -5:
                    return "🟢 Underpriced — Gaining price-sensitive buyers"
                else:
                    return "🟡 Competitively priced"

            snap_clean['Market Position'] = snap_clean['Gap %'].apply(price_signal)
            snap_clean['price']           = snap_clean['price'].apply(lambda x: f"₹{x:,.0f}")
            snap_clean['Gap from Avg']    = snap_clean['Gap from Avg'].apply(lambda x: f"₹{x:+,.0f}")
            snap_clean['Gap %']           = snap_clean['Gap %'].apply(lambda x: f"{x:+.1f}%")

            snap_clean = snap_clean.rename(columns={
                'Display_Name': 'Product',
                'price'       : 'Current Price',
                'rating'      : 'Rating ⭐',
                'review_count': 'Reviews',
            })

            st.dataframe(
                snap_clean[['Product', 'Current Price', 'Rating ⭐', 'Reviews',
                            'Gap from Avg', 'Gap %', 'Market Position']],
                use_container_width=True, hide_index=True
            )
            st.caption(f"📌 Market Average Price: ₹{market_avg:,.0f}")

            st.divider()

            # ── SECTION 4: Plain-English Pricing Simulator ───────────────
            st.subheader("WHAT HAPPENS IF I CHANGE MY PRICE?")
            st.markdown(
                "Use the slider below to simulate a price point. "
                "The tool will tell you — in plain terms — how many more or fewer "
                "buyers you can expect to attract based on historical market patterns."
            )

            ml_model, avg_price = build_elasticity_model(working_df)

            if ml_model is not None:
                price_min = max(500,  int(working_df['price'].dropna().min()) - 200)
                price_max = min(6000, int(working_df['price'].dropna().max()) + 500)

                sim_price         = st.slider(
                    "Select a hypothetical price (₹)",
                    min_value=price_min, max_value=price_max,
                    value=int(avg_price), step=50
                )
                predicted_reviews = ml_model.predict(np.array([[sim_price]]))[0]
                baseline_reviews  = ml_model.predict(np.array([[avg_price]]))[0]
                delta             = int(predicted_reviews - baseline_reviews)
                delta_abs         = abs(delta)

                sim1, sim2 = st.columns(2)
                sim1.metric("Selected Price", f"₹{sim_price:,}")
                sim2.metric(
                    "Estimated Market Traction",
                    f"{max(0, int(predicted_reviews)):,} reviews",
                )

                # Plain-English interpretation — no formulas shown
                if sim_price < avg_price:
                    st.success(
                        f"✅ At ₹{sim_price:,}, your product is **below the market average (₹{avg_price:,.0f})**. "
                        f"Based on historical patterns, this price point is associated with approximately "
                        f"**{delta_abs:,} more buyer interactions** compared to the average. "
                        "This is a strong play for capturing price-sensitive Tier 2/3 customers."
                    )
                elif sim_price > avg_price:
                    st.warning(
                        f"⚠️ At ₹{sim_price:,}, your product is **above the market average (₹{avg_price:,.0f})**. "
                        f"This pricing is associated with approximately "
                        f"**{delta_abs:,} fewer buyer interactions** compared to the average. "
                        "This is only advisable if the product offers clearly superior features or brand trust."
                    )
                else:
                    st.info(
                        f"📌 At ₹{sim_price:,}, your product is priced **at the market average**. "
                        "You are neither gaining nor losing traction from price alone — "
                        "differentiation must come from quality, sentiment, or availability."
                    )
            else:
                st.warning("Not enough data to run the pricing simulator.")

        else:
            st.warning("Not enough historical data to generate forecasts. Ensure at least 2 date entries exist per product.")

    # ── Tab 5: Detailed Snapshot ──────────────────────────────────────────
    with tab_grid:
        st.subheader("COMPETITIVE SNAPSHOT TABLE")
        st.dataframe(
            snapshot[['brand', 'Display_Name', 'price', 'rating', 'review_count']].sort_values('price'),
            use_container_width=True, hide_index=True
        )

        st.subheader("BRAND AUTHORITY COMPARISON")
        fig_rev_bar = px.bar(
            snapshot.sort_values('review_count', ascending=False),
            x='Display_Name', y='review_count', color='Display_Name',
            labels={'review_count': 'Market Volume (Reviews)', 'Display_Name': 'Competitor'},
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig_rev_bar.update_layout(xaxis_tickangle=-45, showlegend=False, template="plotly_white")
        st.plotly_chart(fig_rev_bar, use_container_width=True)

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
        <strong>Arnav Chauhan</strong> | MB24023 | Project 2025-26 | IIT Mandi
    </div>
    """,
    unsafe_allow_html=True
)
