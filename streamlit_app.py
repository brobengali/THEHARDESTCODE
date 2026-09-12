import streamlit as st
import pandas as pd
import json
import os

st.set_page_config(
    page_title="Buy or Wait? — Financial Decision Engine",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for polished aesthetics
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #94a3b8;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 1.5rem;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 1.05rem;
        font-weight: 600;
        padding: 0.75rem 1rem;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    if os.path.exists("web_data.json"):
        with open("web_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data["stats"], pd.DataFrame(data["requests"])
    
    # Fallback to direct CSVs
    output_df = pd.read_csv("output.csv")
    requests_df = pd.read_csv("dataset/requests.csv")
    merged = pd.merge(requests_df, output_df, on="request_id")
    stats = {
        "total": len(merged),
        "affordability": output_df["affordability_status"].value_counts().to_dict(),
        "methods": output_df["recommended_payment_method"].value_counts().to_dict()
    }
    return stats, merged

stats, df = load_data()

st.markdown('<div class="main-header">⚖️ Buy or Wait? — Financial Decision Engine</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">HackerRank Orchestrate — 90-Day Cash Flow Forecasting & Affordability Decision Platform</div>', unsafe_allow_html=True)

# Top KPIs
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Total Requests", stats["total"], help="Total evaluated purchase requests")
with col2:
    st.metric("Affordable Now", stats["affordability"].get("affordable_now", 54), delta="Pay in Full", delta_color="normal")
with col3:
    st.metric("With Plan", stats["affordability"].get("affordable_with_plan", 50), delta="Installments/Partial", delta_color="normal")
with col4:
    st.metric("Affordable Later", stats["affordability"].get("affordable_later", 43), delta="Wait for Income", delta_color="off")
with col5:
    st.metric("Not Affordable", stats["affordability"].get("not_affordable", 103), delta="Exceeds Min Balance", delta_color="inverse")

st.divider()

# Sidebar Filters
st.sidebar.header("🔍 Filters & Search")
search_query = st.sidebar.text_input("Search (ID, User, Text):", placeholder="e.g. request_26, user_01, laptop")

status_options = ["All", "affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"]
selected_status = st.sidebar.selectbox("Affordability Status:", status_options)

method_options = ["All"] + sorted(list(df["recommended_payment_method"].unique()))
selected_method = st.sidebar.selectbox("Recommended Method:", method_options)

# Filter dataframe
filtered_df = df.copy()
if selected_status != "All":
    filtered_df = filtered_df[filtered_df["affordability_status"] == selected_status]

if selected_method != "All":
    filtered_df = filtered_df[filtered_df["recommended_payment_method"] == selected_method]

if search_query:
    q = search_query.lower()
    filtered_df = filtered_df[
        filtered_df["request_id"].str.lower().str.contains(q) |
        filtered_df["user_id"].str.lower().str.contains(q) |
        filtered_df["request_text"].str.lower().str.contains(q)
    ]

# Navigation Tabs
tab1, tab2, tab3 = st.tabs(["📋 Request Explorer", "📊 Analytics & Visuals", "ℹ️ System Overview"])

with tab1:
    st.subheader(f"Showing {len(filtered_df)} Requests")
    
    # Display table summary
    display_cols = ["request_id", "user_id", "request_date", "requested_amount", "currency", "amount_safe_to_pay", "affordability_status", "recommended_payment_method"]
    st.dataframe(
        filtered_df[display_cols],
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    st.subheader("🔎 Request Deep-Dive Inspector")
    req_ids = filtered_df["request_id"].tolist()
    if req_ids:
        selected_req_id = st.selectbox("Select Request to Inspect:", req_ids)
        row = filtered_df[filtered_df["request_id"] == selected_req_id].iloc[0]
        
        detail_col1, detail_col2 = st.columns([1, 1])
        with detail_col1:
            st.markdown(f"### **Request:** `{row['request_id']}` ({row['user_id']})")
            st.markdown(f"**Item/Description:** {row['request_text']}")
            st.markdown(f"**Requested Amount:** `{row['requested_amount']:,.2f} {row['currency']}`")
            st.markdown(f"**Date of Request:** `{row['request_date']}`")
            st.markdown(f"**Desired Completion Date:** `{row['desired_completion_date']}`")
            st.markdown(f"**Allows Partial Payment:** `{row['allows_partial_payment']}`")
            
        with detail_col2:
            st.markdown("### **Recommendation:**")
            status_color = {
                "affordable_now": "green",
                "affordable_with_plan": "blue",
                "affordable_later": "orange",
                "not_affordable": "red"
            }.get(row["affordability_status"], "gray")
            
            st.markdown(f":{status_color}[**Status: {row['affordability_status'].upper()}**]")
            st.markdown(f"**Recommended Method:** `{row['recommended_payment_method']}`")
            st.markdown(f"**Amount Safe to Pay Today:** `{row['amount_safe_to_pay']} {row['currency']}`")
            st.markdown(f"**Earliest Safe Full Payment Date:** `{row['earliest_date_for_full_payment'] or 'N/A'}`")
            st.markdown(f"**Spending Changes Required:** `{row['spending_changes_needed']}`")
        
        st.info(f"**Decision Explanation:**\n\n{row['decision_explanation']}")
        
        if row['payment_plan'] and row['payment_plan'] != 'none':
            st.markdown("#### 📅 Recommended Payment Plan")
            plan_items = row['payment_plan'].split('|')
            plan_data = [p.split(':') for p in plan_items]
            plan_df = pd.DataFrame(plan_data, columns=["Date", "Payment Amount"])
            st.table(plan_df)
            
        if "payment_options" in row and isinstance(row["payment_options"], list) and len(row["payment_options"]) > 0:
            st.markdown("#### 💳 Seller / Vendor Payment Options")
            st.dataframe(pd.DataFrame(row["payment_options"]), use_container_width=True, hide_index=True)
    else:
        st.warning("No requests match the current filters.")

with tab2:
    st.subheader("Distribution Breakdown")
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.write("##### Affordability Status Breakdown")
        status_counts = pd.DataFrame(list(stats["affordability"].items()), columns=["Status", "Count"])
        st.bar_chart(status_counts.set_index("Status"))
        
    with col_chart2:
        st.write("##### Recommended Payment Methods")
        method_counts = pd.DataFrame(list(stats["methods"].items()), columns=["Method", "Count"])
        st.bar_chart(method_counts.set_index("Method"))

with tab3:
    st.subheader("About the Buy or Wait? System")
    st.markdown("""
    This application is the interactive frontend for the **Buy or Wait?** autonomous financial agent developed for **HackerRank Orchestrate (September 2026)**.
    
    ### Key System Features:
    - **100% Deterministic Cash Flow Forecasting**: Simulates daily account balance across a 90-day horizon.
    - **Minimum Balance Protection**: Ensures user's balance never breaches `minimum_balance_to_keep`.
    - **Multimodal Grounding**: Incorporates OCR receipt amounts from `dataset/media/images/` and message clarifications.
    - **Tie-Breaker Optimization**: Selects the optimal plan minimizing spending modifications, total interest/fees, and installment count.
    
    ### Official Submission Links:
    - [HackerRank Challenge Submission](https://www.hackerrank.com/contests/hackerrank-orchestrate-september26/challenges/buy-or-wait/submission)
    - [GitHub Source Code](https://github.com/brobengali/THEHARDESTCODE)
    """)
