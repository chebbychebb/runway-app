import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIG ---
st.set_page_config(page_title="Runway", page_icon="💸", layout="centered")

# --- AESTHETICS ---
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
            font-size: 1.8rem;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
        }
    </style>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
""", unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

# --- YOUR SETTINGS ---
MONTHLY_ALLOWANCE = 1300.0  
FIXED_COSTS = 0.0 

# --- ROBUST DATA ENGINE ---
def load_data():
    # Fetch data
    df = conn.read(worksheet="Logs", usecols=[0, 1, 2, 3], ttl=0)
    
    # 1. Drop ghost rows
    df = df.dropna(how='all')
    
    # 2. Force Date Conversion
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date'])
        
    return df

def save_entry(item, category, amount):
    df = load_data()
    
    # Create new row
    new_row = pd.DataFrame({
        "Date": [datetime.date.today().strftime("%Y-%m-%d")],
        "Item": [item],
        "Category": [category],
        "Amount": [amount]
    })
    
    # Concat
    updated_df = pd.concat([df, new_row], ignore_index=True)
    
    # --- THE FIX IS HERE ---
    # We force the entire column to be Datetime Objects first
    updated_df['Date'] = pd.to_datetime(updated_df['Date'])
    
    # NOW we can safely format it back to String for Google Sheets
    updated_df['Date'] = updated_df['Date'].dt.strftime('%Y-%m-%d')
    
    conn.update(worksheet="Logs", data=updated_df)

# --- MAIN LOGIC ---
try:
    df = load_data()
except Exception as e:
    df = pd.DataFrame(columns=["Date", "Item", "Category", "Amount"])

today = datetime.date.today()

if not df.empty:
    # FILTER: Current Month Only
    mask = (df['Date'].dt.month == today.month) & (df['Date'].dt.year == today.year)
    current_month_df = df.loc[mask]
    net_spend = current_month_df["Amount"].sum()
else:
    net_spend = 0.0
    current_month_df = pd.DataFrame()

# The Math
current_balance = MONTHLY_ALLOWANCE - FIXED_COSTS - net_spend

# Time Math
if today.month == 12:
    next_month = datetime.date(today.year + 1, 1, 1)
else:
    next_month = datetime.date(today.year, today.month + 1, 1)
    
days_remaining = (next_month - today).days
daily_safe_spend = current_balance / days_remaining if days_remaining > 0 else 0

# --- DASHBOARD ---
st.title("💸 The Runway")

c1, c2, c3 = st.columns(3)
c1.metric("Balance", f"{current_balance:.0f}", delta=None)
c2.metric("Days Left", f"{days_remaining} d")
c3.metric("Daily Cap", f"{daily_safe_spend:.0f}", 
          delta_color="normal" if daily_safe_spend > 30 else "inverse")

# Progress Bar
budget_limit = MONTHLY_ALLOWANCE - FIXED_COSTS
if not current_month_df.empty:
    gross_spend = current_month_df[current_month_df['Amount'] > 0]['Amount'].sum()
else:
    gross_spend = 0

if budget_limit > 0:
    burn_rate = min(gross_spend / budget_limit, 1.0)
    st.progress(burn_rate)

st.divider()

# --- TABS ---
tab_spend, tab_earn = st.tabs(["💸 Spend", "💰 Top Up"])

with tab_spend:
    with st.form("expense_form", clear_on_submit=True):
        c_a, c_b = st.columns([2, 1])
        item = c_a.text_input("Item", placeholder="Coffee...")
        amt = c_b.number_input("Cost", min_value=0.0, step=1.0)
        cat = st.selectbox("Category", ["Food", "Transport", "Fun", "Bills", "Other"])
        
        if st.form_submit_button("🔥 Burn It", type="primary"):
            if amt > 0:
                save_entry(item, cat, amt)
                st.success("Money gone.")
                st.rerun()

with tab_earn:
    st.caption("Add extra income here.")
    with st.form("income_form", clear_on_submit=True):
        c_x, c_y = st.columns([2, 1])
        source = c_x.text_input("Source", placeholder="Gift...")
        inc_amt = c_y.number_input("Amount", min_value=0.0, step=50.0)
        
        if st.form_submit_button("🚀 Boost Budget"):
            if inc_amt > 0:
                save_entry(source, "Income", -inc_amt)
                st.balloons()
                st.rerun()

# --- HISTORY ---
st.subheader("Recent Activity")
if not df.empty:
    recent = df.tail(5).iloc[::-1]
    for index, row in recent.iterrows():
        amount = row['Amount']
        # Safely handle Date format for display
        try:
            date_str = row['Date'].strftime("%b %d")
        except:
            date_str = str(row['Date'])

        if amount < 0:
            st.info(f"💰 **+ {abs(amount)} MAD** | {row['Item']}")
        else:
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**{row['Item']}**")
            c2.markdown(f"-{amount:.0f} MAD")
            st.divider()
