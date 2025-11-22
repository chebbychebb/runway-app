import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection
import altair as alt

# --- CONFIG ---
st.set_page_config(page_title="Runway", page_icon="💸", layout="centered")

# --- AESTHETICS & CSS ---
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
        .price-tag-neg { color: #ff4b4b; font-weight: bold; float: right; }
        .price-tag-pos { color: #00cc96; font-weight: bold; float: right; }
        .item-name { font-weight: 600; font-size: 1.1rem; }
    </style>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
""", unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

# --- SETTINGS ---
MONTHLY_ALLOWANCE = 1300.0  
FIXED_COSTS = 0.0 

# --- DATA ENGINE ---
def load_data():
    df = conn.read(worksheet="Logs", usecols=[0, 1, 2, 3], ttl=0)
    df = df.dropna(how='all')
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date'])
    return df

def save_entry(item, category, amount):
    df = load_data()
    new_row = pd.DataFrame({
        "Date": [pd.Timestamp(datetime.date.today())], 
        "Item": [item],
        "Category": [category],
        "Amount": [amount]
    })
    updated_df = pd.concat([df, new_row], ignore_index=True)
    updated_df['Date'] = updated_df['Date'].apply(lambda x: x.strftime('%Y-%m-%d'))
    conn.update(worksheet="Logs", data=updated_df)

# --- THE SMART BAR ENGINE (UPDATED LOGIC) ---
def render_smart_bar(current_balance, allowance):
    # 1. GREEN SCENARIO (Bonus)
    if current_balance > allowance:
        surplus = current_balance - allowance
        # Bar fills based on how big the surplus is relative to a month salary
        fill_pct = min((surplus / allowance) * 100, 100)
        color = "#00cc96" # Green
        label = "🟢 BONUS BUFFER"
        # Intelligent Alternative: Show exact amount
        status_text = f"+{surplus:.0f} MAD Surplus"
    
    # 2. RED SCENARIO (Debt)
    elif current_balance < 0:
        debt = abs(current_balance)
        # Bar fills based on severity of debt
        fill_pct = min((debt / allowance) * 100, 100)
        color = "#ff4b4b" # Red
        label = "🔴 DEBT ALERT"
        # Intelligent Alternative: Show exact debt
        status_text = f"-{debt:.0f} MAD Over Budget"
        
    # 3. BLUE SCENARIO (Normal)
    else:
        fill_pct = (current_balance / allowance) * 100
        color = "#29b5e8" # Blue
        label = "🔵 REMAINING ALLOWANCE"
        # Keep Percentage for standard tracking
        status_text = f"{fill_pct:.1f}% Fuel Remaining"

    # Render Bar
    st.markdown(f"""
        <div style="margin-bottom: 5px; font-size: 0.8rem; color: #888;">{label}</div>
        <div style="background-color: #333; border-radius: 10px; height: 25px; width: 100%;">
            <div style="background-color: {color}; width: {fill_pct}%; height: 100%; border-radius: 10px; transition: width 0.5s;"></div>
        </div>
        <div style="text-align: right; font-size: 0.8rem; color: {color}; margin-top: 5px; font-weight: bold;">
            {status_text}
        </div>
    """, unsafe_allow_html=True)

# --- MAIN LOGIC ---
try:
    df = load_data()
except Exception as e:
    df = pd.DataFrame(columns=["Date", "Item", "Category", "Amount"])

today = datetime.date.today()

if not df.empty:
    mask = (df['Date'].dt.month == today.month) & (df['Date'].dt.year == today.year)
    current_month_df = df.loc[mask]
    net_spend = current_month_df["Amount"].sum()
else:
    net_spend = 0.0
    current_month_df = pd.DataFrame()

current_balance = MONTHLY_ALLOWANCE - FIXED_COSTS - net_spend

if today.month == 12:
    next_month = datetime.date(today.year + 1, 1, 1)
else:
    next_month = datetime.date(today.year, today.month + 1, 1)
    
days_remaining = (next_month - today).days
daily_safe_spend = current_balance / days_remaining if days_remaining > 0 else 0

# --- DASHBOARD HEADER ---
st.title("💸 The Runway")

c1, c2, c3 = st.columns(3)
c1.metric("Balance", f"{current_balance:.0f}", delta=None)
c2.metric("Days Left", f"{days_remaining} d")
c3.metric("Daily Cap", f"{daily_safe_spend:.0f}", 
          delta_color="normal" if daily_safe_spend > 20 else "inverse")

st.divider()

# Inject Smart Bar
render_smart_bar(current_balance, MONTHLY_ALLOWANCE)

st.divider()

# --- TABS ---
mode_action, mode_intel = st.tabs(["🚀 Action", "📊 Intel"])

# === ACTION TAB ===
with mode_action:
    with st.expander("➕ Add Transaction", expanded=True):
        tab_expense, tab_income = st.tabs(["Spend", "Earn"])
        
        with tab_expense:
            with st.form("expense_form", clear_on_submit=True):
                c_a, c_b = st.columns([2, 1])
                item = c_a.text_input("Item", placeholder="Coffee...")
                amt = c_b.number_input("Price", min_value=0.0, step=1.0)
                cat = st.selectbox("Category", ["Food", "Transport", "Fun", "Bills", "Other"])
                if st.form_submit_button("🔥 Burn It", type="primary"):
                    if amt > 0:
                        save_entry(item, cat, amt)
                        st.rerun()

        with tab_income:
            with st.form("income_form", clear_on_submit=True):
                c_x, c_y = st.columns([2, 1])
                source = c_x.text_input("Source")
                inc_amt = c_y.number_input("Amount", min_value=0.0, step=50.0)
                if st.form_submit_button("🚀 Boost"):
                    if inc_amt > 0:
                        save_entry(source, "Income", -inc_amt)
                        st.balloons()
                        st.rerun()

    st.subheader("Recent Activity")
    if not df.empty:
        recent = df.tail(5).iloc[::-1]
        for index, row in recent.iterrows():
            amt = row['Amount']
            if amt < 0:
                st.markdown(f"""
                <div style="padding: 10px; border-radius: 5px; background-color: #1E1E1E; margin-bottom: 5px;">
                    <span class="item-name">💰 {row['Item']}</span>
                    <span class="price-tag-pos">+{abs(amt):.0f} MAD</span>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="padding: 10px; border-radius: 5px; background-color: #1E1E1E; margin-bottom: 5px;">
                    <span class="item-name">{row['Item']}</span>
                    <span class="price-tag-neg">-{amt:.0f} MAD</span>
                </div>""", unsafe_allow_html=True)

# === INTEL TAB ===
with mode_intel:
    st.header("🧐 Analysis")
    
    if not current_month_df.empty:
        current_month_df['Week'] = current_month_df['Date'].dt.isocalendar().week
        this_week = today.isocalendar().week
        weekly_spend = current_month_df[
            (current_month_df['Week'] == this_week) & 
            (current_month_df['Amount'] > 0)
        ]['Amount'].sum()
        st.metric("Spent This Week", f"{weekly_spend:.0f} MAD")

        st.caption("Spending by Category")
        cat_data = current_month_df[current_month_df['Amount'] > 0].groupby('Category')['Amount'].sum().reset_index()
        
        chart = alt.Chart(cat_data).mark_bar().encode(
            x=alt.X('Category', sort='-y'),
            y='Amount',
            color=alt.Color('Category', legend=None),
            tooltip=['Category', 'Amount']
        )
        st.altair_chart(chart, use_container_width=True)

        st.divider()
        with st.expander("📂 View Full History"):
            display_df = df.copy().sort_values(by="Date", ascending=False)
            display_df['Amount'] = display_df['Amount'] * -1
            
            def format_currency(val):
                return f"+{val:.0f} MAD" if val > 0 else f"{val:.0f} MAD"
            
            display_df['Cost'] = display_df['Amount'].apply(format_currency)
            st.dataframe(
                display_df[['Date', 'Item', 'Category', 'Cost']],
                use_container_width=True,
                hide_index=True,
                column_config={"Date": st.column_config.DateColumn("Date", format="MMM DD")}
            )
    else:
        st.info("No data yet.")
