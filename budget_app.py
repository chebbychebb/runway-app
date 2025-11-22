import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- MOBILE-FIRST CONFIG ---
st.set_page_config(page_title="Runway", page_icon="💸", layout="centered")

# --- AESTHETIC HACKS ---
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
        /* Make metrics pop */
        [data-testid="stMetricValue"] {
            font-size: 1.8rem;
        }
        /* Custom colors for Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
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

def save_entry(item, category, amount):
    df = load_data()
    # If amount is negative, it's income. If positive, it's expense.
    new_row = pd.DataFrame({
        "Date": [datetime.date.today().strftime("%Y-%m-%d")],
        "Item": [item],
        "Category": [category],
        "Amount": [amount]
    })
    updated_df = pd.concat([df, new_row], ignore_index=True)
    conn.update(worksheet="Logs", data=updated_df)

# --- YOUR SETTINGS ---
MONTHLY_ALLOWANCE = 1300.0  
FIXED_COSTS = 0.0 

# --- ENGINE ROOM ---
df = load_data()

if not df.empty:
    # Sum of all rows (Expenses are positive, Income is negative)
    net_spend = df["Amount"].sum()
else:
    net_spend = 0.0

# The Math: 1300 - (Expenses - Income)
current_balance = MONTHLY_ALLOWANCE - FIXED_COSTS - net_spend

# Time Calculations
today = datetime.date.today()
if today.month == 12:
    next_month = datetime.date(today.year + 1, 1, 1)
else:
    next_month = datetime.date(today.year, today.month + 1, 1)
    
days_remaining = (next_month - today).days
daily_safe_spend = current_balance / days_remaining if days_remaining > 0 else 0

# --- THE DASHBOARD ---
st.title("💸 The Runway")

# 1. The Trifecta Metrics (Days Left is back!)
c1, c2, c3 = st.columns(3)
c1.metric("Balance", f"{current_balance:.0f}", delta=None)
c2.metric("Days Left", f"{days_remaining} d")
c3.metric("Daily Cap", f"{daily_safe_spend:.0f}", 
          delta_color="normal" if daily_safe_spend > 30 else "inverse")

# 2. Visual Health Bar
budget_limit = MONTHLY_ALLOWANCE - FIXED_COSTS
# We calculate burn rate based on positive spend only to keep the bar logical
if not df.empty:
    gross_spend = df[df['Amount'] > 0]['Amount'].sum()
else:
    gross_spend = 0

if budget_limit > 0:
    # Simple progress: How much of the 1300 is gone?
    # (ignoring extra income for the visual bar so you don't get cocky)
    burn_rate = min(gross_spend / budget_limit, 1.0)
    st.progress(burn_rate)

st.divider()

# --- THE ACTION CENTER (TABS) ---
tab_spend, tab_earn = st.tabs(["💸 Spend", "💰 Top Up"])

with tab_spend:
    with st.form("expense_form", clear_on_submit=True):
        c_a, c_b = st.columns([2, 1])
        item = c_a.text_input("What did you buy?", placeholder="Taxi, Coffee...")
        amt = c_b.number_input("Cost", min_value=0.0, step=1.0)
        cat = st.selectbox("Category", ["Food", "Transport", "Fun", "Bills", "Other"])
        
        if st.form_submit_button("🔥 Burn It", type="primary"):
            if amt > 0:
                save_entry(item, cat, amt) # Positive number = Expense
                st.success("Money gone.")
                st.rerun()

with tab_earn:
    st.caption("Got extra cash? Add it here to boost your budget.")
    with st.form("income_form", clear_on_submit=True):
        c_x, c_y = st.columns([2, 1])
        source = c_x.text_input("Source", placeholder="Gift, Side Job...")
        inc_amt = c_y.number_input("Amount", min_value=0.0, step=50.0)
        
        # We save income as NEGATIVE expense to reverse the math
        if st.form_submit_button("🚀 Boost Budget"):
            if inc_amt > 0:
                save_entry(source, "Income", -inc_amt) 
                st.balloons() # A little dopamine hit for making money
                st.rerun()

# --- INTELLIGENT HISTORY ---
st.subheader("Recent Activity")

if not df.empty:
    recent = df.tail(5).iloc[::-1]
    for index, row in recent.iterrows():
        amount = row['Amount']
        
        # Aesthetic Logic: Green for Income, Normal for Expense
        if amount < 0:
            # It's income
            st.info(f"💰 **+ {abs(amount)} MAD** | {row['Item']} (Boost)")
        else:
            # It's expense
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**{row['Item']}**")
            c2.markdown(f"-{amount:.0f} MAD")
            st.divider()
