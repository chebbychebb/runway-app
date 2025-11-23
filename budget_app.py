import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection
import altair as alt

# --- CONFIG ---
st.set_page_config(page_title="PhD Survival Kit", page_icon="💸", layout="centered")

# --- AESTHETICS & CSS ---
st.markdown("""
    <style>
        /* Hides the 3-dots menu at top right */
        #MainMenu {visibility: hidden;}
        
        /* Hides the 'Made with Streamlit' footer */
        footer {visibility: hidden;}
        
        /* WE REMOVED THE LINE THAT HID THE HEADER */
        /* This brings back the arrow button > so you can open the sidebar */
        
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
        .rollover-box {
            padding: 10px;
            border-radius: 5px;
            background-color: #262730;
            text-align: center;
            margin-bottom: 20px;
            border: 1px solid #444;
        }
    </style>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
""", unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

# --- SETTINGS ---
MONTHLY_ALLOWANCE = 1300.0  
FIXED_COSTS = 0.0 
ADMIN_PASSWORD = "1234" 

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

# --- RESET LOGIC ---
def reset_data(mode="all"):
    if mode == "all":
        empty_df = pd.DataFrame(columns=["Date", "Item", "Category", "Amount"])
        conn.update(worksheet="Logs", data=empty_df)
    
    elif mode == "month":
        df = load_data()
        if not df.empty:
            today = datetime.date.today()
            mask = ~((df['Date'].dt.month == today.month) & (df['Date'].dt.year == today.year))
            kept_df = df.loc[mask]
            kept_df['Date'] = kept_df['Date'].apply(lambda x: x.strftime('%Y-%m-%d'))
            conn.update(worksheet="Logs", data=kept_df)

# --- SMART BAR ENGINE ---
def render_smart_bar(current_balance, total_monthly_budget):
    if current_balance > total_monthly_budget:
        surplus = current_balance - total_monthly_budget
        fill_pct = 100
        color = "#00cc96" 
        label = "🟢 EXTRA SURPLUS"
        status_text = f"+{surplus:.0f} MAD Above Budget"
    elif current_balance < 0:
        debt = abs(current_balance)
        fill_pct = 100
        color = "#ff4b4b" 
        label = "🔴 DEBT ALERT"
        status_text = f"-{debt:.0f} MAD Overdrawn"
    else:
        if total_monthly_budget > 0:
            fill_pct = (current_balance / total_monthly_budget) * 100
        else:
            fill_pct = 0
        color = "#29b5e8" 
        label = "🔵 CURRENT MONTH BUDGET"
        status_text = f"{fill_pct:.1f}% Remaining"

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

# 1. ROLLOVER
if not df.empty:
    start_date = df['Date'].min()
    months_passed = (today.year - start_date.year) * 12 + (today.month - start_date.month)
    past_mask = (df['Date'] < pd.Timestamp(today.year, today.month, 1))
    past_net_spend = df.loc[past_mask, "Amount"].sum()
    past_total_allowance = months_passed * (MONTHLY_ALLOWANCE - FIXED_COSTS)
    rollover = past_total_allowance - past_net_spend
else:
    rollover = 0.0

# 2. CURRENT MONTH
if not df.empty:
    current_mask = (df['Date'].dt.month == today.month) & (df['Date'].dt.year == today.year)
    current_month_spend = df.loc[current_mask, "Amount"].sum()
else:
    current_month_spend = 0.0

# 3. TOTALS
this_month_budget = (MONTHLY_ALLOWANCE - FIXED_COSTS) + rollover
current_balance = this_month_budget - current_month_spend

# Time Math
if today.month == 12:
    next_month = datetime.date(today.year + 1, 1, 1)
else:
    next_month = datetime.date(today.year, today.month + 1, 1)
days_remaining = (next_month - today).days

# Daily Cap
if days_remaining > 0:
    daily_safe_spend = max(0.0, current_balance / days_remaining)
else:
    daily_safe_spend = 0

# --- SIDEBAR (ADMIN PANEL) ---
with st.sidebar:
    st.header("⚙️ Admin Panel")
    with st.expander("⚠️ Danger Zone"):
        password_input = st.text_input("Admin Password", type="password")
        
        st.caption("Reset Current Month")
        if st.button("🗑️ Wipe This Month"):
            if password_input == ADMIN_PASSWORD:
                reset_data(mode="month")
                st.success("Month wiped.")
                st.rerun()
            else:
                st.error("Wrong Password")
        
        st.caption("Factory Reset (Delete All)")
        if st.button("☢️ RESET EVERYTHING"):
            if password_input == ADMIN_PASSWORD:
                reset_data(mode="all")
                st.success("App Reset to Zero.")
                st.rerun()
            else:
                st.error("Wrong Password")

# --- DASHBOARD ---
st.title("💸 PhD Survival Kit")

if abs(rollover) > 1:
    if rollover > 0:
        st.markdown(f"""
        <div class="rollover-box" style="color: #00cc96;">
            💰 <b>Savings Carried Over:</b> +{rollover:.0f} MAD added to this month.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="rollover-box" style="color: #ff4b4b;">
            📉 <b>Debt Carried Over:</b> {rollover:.0f} MAD deducted from this month.
        </div>""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
c1.metric("Balance", f"{current_balance:.0f} MAD", delta=None)
c2.metric("Days Left", f"{days_remaining} d")
c3.metric("Daily Cap", f"{daily_safe_spend:.0f} MAD", 
          delta_color="normal" if daily_safe_spend > 0 else "inverse")

st.divider()
render_smart_bar(current_balance, this_month_budget)
st.divider()

# --- TABS ---
mode_action, mode_intel = st.tabs(["🚀 Action", "📊 Intel"])

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

with mode_intel:
    st.header("🧐 Analysis")
    
    if not df.empty:
        df['Month_Year'] = df['Date'].dt.to_period('M')
        available_months = df['Month_Year'].unique().astype(str)
        available_months = sorted(available_months, reverse=True)
        
        selected_period = st.selectbox("📅 Select Time Period", available_months, index=0)
        sel_year, sel_month = map(int, selected_period.split('-'))
        
        intel_mask = (df['Date'].dt.month == sel_month) & (df['Date'].dt.year == sel_year)
        intel_df = df.loc[intel_mask]
        
        if not intel_df.empty:
            total_selected_spend = intel_df[intel_df['Amount'] > 0]['Amount'].sum()
            st.metric(f"Total Spent in {selected_period}", f"{total_selected_spend:.0f} MAD")

            st.caption("Spending by Category")
            cat_data = intel_df[intel_df['Amount'] > 0].groupby('Category')['Amount'].sum().reset_index()
            chart = alt.Chart(cat_data).mark_bar().encode(
                x=alt.X('Category', sort='-y'),
                y='Amount',
                color=alt.Color('Category', legend=None),
                tooltip=['Category', 'Amount']
            )
            st.altair_chart(chart, use_container_width=True)

            st.divider()
            with st.expander(f"📂 View Details for {selected_period}", expanded=True):
                display_df = intel_df.copy().sort_values(by="Date", ascending=False)
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
            st.info("No data found for this period.")
    else:
        st.info("Log some expenses to unlock Analysis.")
