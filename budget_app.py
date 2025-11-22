import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- MOBILE-FIRST CONFIG ---
st.set_page_config(page_title="Runway", page_icon="💸", layout="centered")

# --- CSS HACKS ---
# Hides the hamburger menu, footer, and header for a cleaner App look
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .block-container {
            padding-top: 1rem;
            padding-bottom: 5rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        [data-testid="stMetricValue"] {
            font-size: 2rem;
        }
    </style>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
""", unsafe_allow_html=True)

# --- CONNECT TO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        df = conn.read(worksheet="Logs", ttl=0) 
        return df
    except:
        return pd.DataFrame(columns=["Date", "Item", "Category", "Amount"])

def save_expense(item, category, amount):
    df = load_data()
    new_row = pd.DataFrame({
        "Date": [datetime.date.today().strftime("%Y-%m-%d")],
        "Item": [item],
        "Category": [category],
        "Amount": [amount]
    })
    updated_df = pd.concat([df, new_row], ignore_index=True)
    conn.update(worksheet="Logs", data=updated_df)

# --- YOUR FINANCIAL SETTINGS ---
# CHEBB: CHANGE THESE NUMBERS HERE IF THEY CHANGE IN THE FUTURE
MONTHLY_ALLOWANCE = 1300.0  
FIXED_COSTS = 0.0           # Set this to your total monthly bills (Phone, Internet, etc.)

# --- APP LOGIC ---
df = load_data()

if not df.empty:
    total_spent = df["Amount"].sum()
else:
    total_spent = 0.0

# The Magic Formula
remaining_budget = MONTHLY_ALLOWANCE - FIXED_COSTS - total_spent

# Date Math
today = datetime.date.today()
# Logic to handle month rollover
if today.month == 12:
    next_month = datetime.date(today.year + 1, 1, 1)
else:
    next_month = datetime.date(today.year, today.month + 1, 1)
    
days_remaining = (next_month - today).days
daily_safe_spend = remaining_budget / days_remaining if days_remaining > 0 else 0

# --- THE UI ---
st.title("💸 The Runway")

# Metrics
c1, c2 = st.columns(2)
c1.metric("Left to Spend", f"{remaining_budget:.0f}", delta=f"-{total_spent:.0f} spent")
c2.metric("Daily Cap", f"{daily_safe_spend:.0f}", 
          delta_color="normal" if daily_safe_spend > 20 else "inverse")

# Progress Bar
budget_limit = MONTHLY_ALLOWANCE - FIXED_COSTS
if budget_limit > 0:
    burn_rate = total_spent / budget_limit
    st.progress(min(burn_rate, 1.0))
    if burn_rate >= 1.0:
        st.error("🚨 You are broke.")

# Add Expense Form
with st.expander("➕ Add Expense", expanded=True):
    with st.form("mobile_entry", clear_on_submit=True):
        c_a, c_b = st.columns([2, 1])
        item = c_a.text_input("Item", placeholder="e.g., Coffee")
        amt = c_b.number_input("Cost", min_value=0.0, step=1.0) # Step 1.0 is better for small amounts
        cat = st.selectbox("Category", ["Food", "Transport", "Printing", "Fun", "Other"])
        
        if st.form_submit_button("Track It", type="primary"):
            if amt > 0:
                save_expense(item, cat, amt)
                st.success("Saved!")
                st.rerun()

# History
st.subheader("Recent Activity")
if not df.empty:
    recent = df.tail(5).iloc[::-1]
    for index, row in recent.iterrows():
        st.markdown(f"**{row['Item']}** ({row['Category']})")
        st.caption(f"{row['Date']} — **{row['Amount']} MAD**")
        st.divider()
