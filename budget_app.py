import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- MOBILE-FIRST CONFIG ---
st.set_page_config(page_title="Runway", page_icon="💸", layout="centered")

# --- CSS HACKS FOR MOBILE APP FEEL ---
# This hides the top bar and footer, and tightens the padding for phone screens
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        /* Make metrics pop on dark mode */
        [data-testid="stMetricValue"] {
            font-size: 2rem;
        }
    </style>
""", unsafe_allow_html=True)

# --- CONNECT TO GOOGLE SHEETS ---
# We use a specialized connection that handles caching automatically
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    # Read the specific worksheet. If empty, return structure
    try:
        df = conn.read(worksheet="Logs", ttl=0) # ttl=0 means no caching (instant updates)
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
    # Update the Google Sheet
    conn.update(worksheet="Logs", data=updated_df)

# --- APP LOGIC ---
# Fixed inputs (Hardcoded for now or simpler to manage in code for speed)
MONTHLY_ALLOWANCE = 3000.0
FIXED_COSTS = 1000.0

# Load Data
df = load_data()

# Clean numeric conversion
if not df.empty:
    total_spent = df["Amount"].sum()
else:
    total_spent = 0.0

remaining_budget = MONTHLY_ALLOWANCE - FIXED_COSTS - total_spent

# Date Math
today = datetime.date.today()
if today.month == 12:
    next_month = datetime.date(today.year + 1, 1, 1)
else:
    next_month = datetime.date(today.year, today.month + 1, 1)
days_remaining = (next_month - today).days
daily_safe_spend = remaining_budget / days_remaining if days_remaining > 0 else 0

# --- THE MOBILE UI ---

st.title("💸 The Runway")

# 1. The "In Your Face" Metrics
# We use columns to stack them nicely
c1, c2 = st.columns(2)
c1.metric("Left to Spend", f"{remaining_budget:.0f} MAD", delta=f"-{total_spent:.0f}")
c2.metric("Daily Cap", f"{daily_safe_spend:.0f} MAD", 
          delta_color="normal" if daily_safe_spend > 50 else "inverse")

st.progress(min(total_spent / (MONTHLY_ALLOWANCE - FIXED_COSTS), 1.0))

# 2. The "Quick Add" Button
# We use an expander so the form doesn't clutter the screen
with st.expander("➕ Add Expense", expanded=True):
    with st.form("mobile_entry", clear_on_submit=True):
        item = st.text_input("Item")
        cat = st.selectbox("Category", ["Food", "Transport", "Fun", "Bills", "Other"])
        amt = st.number_input("Amount", min_value=0.0, step=10.0)
        
        if st.form_submit_button("Track It", type="primary"):
            if amt > 0:
                save_expense(item, cat, amt)
                st.success("Saved!")
                st.rerun()

# 3. Recent History (Clean List)
st.subheader("Recent Activity")
if not df.empty:
    # Show last 5 items, newest first
    recent = df.tail(5).iloc[::-1]
    for index, row in recent.iterrows():
        st.text(f"{row['Date']} | {row['Category']} | -{row['Amount']} MAD")