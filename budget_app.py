import streamlit as st
import pandas as pd
import datetime
import time 
from streamlit_gsheets import GSheetsConnection
import altair as alt
import pytz

# --- CONFIG ---
st.set_page_config(page_title="PhD Survival Kit", page_icon="💸", layout="centered")

# --- AESTHETICS & CSS ---
st.markdown("""
    <style>
        footer {visibility: hidden;}
        .block-container {
            padding-top: 1rem;
            padding-bottom: 5rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        [data-testid="stMetricValue"] { font-size: 1.8rem; }
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
""", unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

# --- DEFAULTS ---
DEFAULT_ALLOWANCE = 1300.0  
FIXED_COSTS = 0.0  
ADMIN_PASSWORD = "1234"  

# --- DATA ENGINE ---
def load_data(worksheet_name="Logs"):
    df = conn.read(worksheet=worksheet_name, ttl=0) 
    df = df.dropna(how='all')
    if not df.empty:
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date'])
    return df

def save_entry(item, category, amount, worksheet_name="Logs"):
    unique_id = "ID-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    
    df = load_data(worksheet_name=worksheet_name)
    
    if worksheet_name == "Logs":
        new_row = pd.DataFrame({
            "Date": [pd.Timestamp(datetime.date.today())], 
            "Item": [item],
            "Category": [category],
            "Amount": [amount],
            "ID": [unique_id] 
        })
    elif worksheet_name == "Liabilities":
        new_row = pd.DataFrame({
            "Item": [item],
            "Amount": [amount],
            "Date_Borrowed": [pd.Timestamp(datetime.date.today()).strftime('%Y-%m-%d')],
            "Date_Paid": ["PENDING"],
            "Status": ["PENDING"],
            "Debt_ID": [unique_id] 
        })

    updated_df = pd.concat([df, new_row], ignore_index=True)
    if 'Date' in updated_df.columns:
        updated_df['Date'] = updated_df['Date'].apply(lambda x: x.strftime('%Y-%m-%d'))
    conn.update(worksheet=worksheet_name, data=updated_df)

def settle_debt(debt_id, amount_paid, item_name):
    liabilities_df = load_data(worksheet_name="Liabilities")
    liabilities_df['Debt_ID_str'] = liabilities_df['Debt_ID'].astype(str)
    row_index = liabilities_df[liabilities_df['Debt_ID_str'] == debt_id].index
    
    if not row_index.empty:
        liabilities_df.loc[row_index, 'Date_Paid'] = pd.Timestamp(datetime.date.today()).strftime('%Y-%m-%d')
        liabilities_df.loc[row_index, 'Status'] = 'PAID'
        liabilities_df.loc[row_index, 'Amount'] = amount_paid
        
        save_entry(f"Payment: {item_name}", "Debt Payment", amount_paid, worksheet_name="Logs")
        
        liabilities_df = liabilities_df.drop(columns=['Debt_ID_str'])
        conn.update(worksheet="Liabilities", data=liabilities_df)
        return True
    return False

def delete_entry(entry_id, worksheet_name="Logs"):
    df = load_data(worksheet_name=worksheet_name)
    entry_id = str(entry_id).strip()
    
    if worksheet_name == "Logs":
        if not entry_id.startswith("ID-"): entry_id = "ID-" + entry_id
        df['ID'] = df['ID'].astype(str)
        id_col = 'ID'
    elif worksheet_name == "Liabilities":
        if not entry_id.startswith("ID-"): entry_id = "ID-" + entry_id
        df['Debt_ID'] = df['Debt_ID'].astype(str)
        id_col = 'Debt_ID'
    
    initial_count = len(df)
    df_kept = df[df[id_col] != entry_id].copy()
    deleted_count = initial_count - len(df_kept)
    
    if not df_kept.empty and 'Date' in df_kept.columns:
        df_kept['Date'] = df_kept['Date'].apply(lambda x: x.strftime('%Y-%m-%d'))
    
    conn.update(worksheet=worksheet_name, data=df_kept)
    return deleted_count

def reset_data(mode="all", worksheet_name="Logs"):
    if worksheet_name == "Logs":
        empty_df = pd.DataFrame(columns=["Date", "Item", "Category", "Amount", "ID"])
        conn.update(worksheet="Logs", data=empty_df)
    elif worksheet_name == "Liabilities":
        empty_df = pd.DataFrame(columns=['Item', 'Amount', 'Date_Borrowed', 'Date_Paid', 'Status', 'Debt_ID'])
        conn.update(worksheet="Liabilities", data=empty_df)

def render_smart_bar(current_balance, total_monthly_budget):
    if current_balance > total_monthly_budget:
        surplus = current_balance - total_monthly_budget
        fill_pct = 100; color = "#00cc96"; label = "🟢 EXTRA SURPLUS"; status_text = f"+{surplus:.2f} MAD Above Budget" 
    elif current_balance < 0:
        debt = abs(current_balance)
        fill_pct = 100; color = "#ff4b4b"; label = "🔴 DEBT ALERT"; status_text = f"-{debt:.2f} MAD Overdrawn"
    else:
        if total_monthly_budget > 0:
            fill_pct = (current_balance / total_monthly_budget) * 100
            color = "#29b5e8"; label = "🔵 CURRENT MONTH BUDGET"; status_text = f"{fill_pct:.1f}% Remaining"
        else:
            fill_pct = 0; color = "#808080"; label = "⚫ LOW BUDGET BASE"; status_text = "N/A"

    st.markdown(f"""
        <div style="margin-bottom: 5px; font-size: 0.8rem; color: #888;">{label}</div>
        <div style="background-color: #333; border-radius: 10px; height: 25px; width: 100%;">
            <div style="background-color: {color}; width: {fill_pct}%; height: 100%; border-radius: 10px; transition: width 0.5s;"></div>
        </div>
        <div style="text-align: right; font-size: 0.8rem; color: {color}; margin-top: 5px; font-weight: bold;">{status_text}</div>
    """, unsafe_allow_html=True)

# --- MAIN LOGIC ---
try:
    full_df = load_data()
    liabilities_df = load_data(worksheet_name="Liabilities")
except Exception as e:
    full_df = pd.DataFrame(columns=["Date", "Item", "Category", "Amount", "ID"])
    liabilities_df = pd.DataFrame(columns=['Item', 'Amount', 'Date_Borrowed', 'Date_Paid', 'Status', 'Debt_ID'])

if not full_df.empty:
    df = full_df[full_df['Category'] != 'ADMIN'].copy()
    # Get Current Allowance (Latest Setting)
    admin_df = full_df[full_df['Category'] == 'ADMIN']
    if not admin_df.empty:
        last_admin_row = admin_df.iloc[-1]
        CURRENT_ALLOWANCE = float(last_admin_row['Amount'])
    else:
        CURRENT_ALLOWANCE = DEFAULT_ALLOWANCE
else:
    df = pd.DataFrame(columns=["Date", "Item", "Category", "Amount", "ID"])
    CURRENT_ALLOWANCE = DEFAULT_ALLOWANCE

# SET TIMEZONE
CASABLANCA_TZ = pytz.timezone('Africa/Casablanca')
today_dt = datetime.datetime.now(CASABLANCA_TZ)
today = today_dt.date()

# =========================================================
# 2. ROLLOVER LOGIC (FIXED: Uses Historic Allowance)
# =========================================================
rollover = 0.0

if not df.empty:
    start_date = df['Date'].min().date()
    
    # Iterate from the first month of data up to the START of the current month
    iter_date = datetime.date(start_date.year, start_date.month, 1)
    current_month_start = datetime.date(today.year, today.month, 1)
    
    # Pre-filter ADMIN logs for speed
    all_admin_logs = full_df[full_df['Category'] == 'ADMIN'].copy()

    while iter_date < current_month_start:
        # Determine End of Month (Start of Next Month)
        if iter_date.month == 12:
            next_month_start = datetime.date(iter_date.year + 1, 1, 1)
        else:
            next_month_start = datetime.date(iter_date.year, iter_date.month + 1, 1)
            
        # A. Calculate Spend for this specific past month
        month_mask = (df['Date'] >= pd.Timestamp(iter_date)) & (df['Date'] < pd.Timestamp(next_month_start))
        monthly_spend = df.loc[month_mask, "Amount"].sum()
        
        # B. Find the allowance that was active DURING that month
        # We look for the latest ADMIN entry that occurred BEFORE that month ended
        relevant_admin = all_admin_logs[all_admin_logs['Date'] < pd.Timestamp(next_month_start)]
        
        if not relevant_admin.empty:
            historical_limit = float(relevant_admin.sort_values('Date').iloc[-1]['Amount'])
        else:
            historical_limit = DEFAULT_ALLOWANCE
            
        # C. Add savings/debt to rollover
        rollover += (historical_limit - monthly_spend)
        
        # Move to next month
        iter_date = next_month_start

# 3. CURRENT MONTH
if not df.empty:
    current_mask = (df['Date'].dt.month == today.month) & (df['Date'].dt.year == today.year)
    current_month_spend = df.loc[current_mask, "Amount"].sum()
else:
    current_month_spend = 0.0

# 4. TOTALS
# Use CURRENT_ALLOWANCE for this month, but 'rollover' contains the math from past allowances
this_month_budget = (CURRENT_ALLOWANCE - FIXED_COSTS) + rollover
current_balance = this_month_budget - current_month_spend

# Time Math
if today.month == 12:
    next_month = datetime.date(today.year + 1, 1, 1)
else:
    next_month = datetime.date(today.year, today.month + 1, 1)
days_remaining = (next_month - today).days
daily_safe_spend = max(0.0, current_balance / days_remaining) if days_remaining > 0 else 0

# --- SIDEBAR (ADMIN PANEL) ---
with st.sidebar:
    st.header("⚙️ Admin Panel")
    with st.expander("💰 Edit Allowance"):
        new_allowance = st.number_input("New Monthly Limit", value=CURRENT_ALLOWANCE, step=0.01)
        password_allowance = st.text_input("Password", type="password", key="pw_allowance")
        if st.button("Update Allowance"):
            if password_allowance == ADMIN_PASSWORD:
                save_entry("Allowance Update", "ADMIN", new_allowance)
                st.success(f"Allowance changed to {new_allowance:.2f}")
                st.rerun()
            else:
                st.error("Wrong Password")

    with st.expander("✂️ Delete Entry"):
        st.caption("Copy the full ID from the Intel Tab.")
        entry_id_input = st.text_input("Transaction ID to Delete")
        password_delete = st.text_input("Password", type="password", key="pw_delete")
        if st.button("Delete Transaction"):
            if password_delete == ADMIN_PASSWORD:
                if entry_id_input:
                    try:
                        deleted_rows = delete_entry(entry_id_input.strip(), worksheet_name="Logs")
                        if deleted_rows > 0: st.success(f"✅ Deleted {deleted_rows} row(s).")
                        else: st.warning("⚠️ No matching ID found.")
                        st.rerun()
                    except Exception as e: st.error(f"Failed: {e}")
                else: st.error("Invalid ID.")
            else: st.error("Wrong Password")

    with st.expander("⚠️ Danger Zone"):
        password_reset = st.text_input("Password", type="password", key="pw_reset")
        if st.button("🗑️ Wipe This Month"):
            if password_reset == ADMIN_PASSWORD:
                reset_data(mode="month", worksheet_name="Logs")
                st.success("Month wiped."); st.rerun()
            else: st.error("Wrong Password")
        if st.button("☢️ RESET EVERYTHING"):
            if password_reset == ADMIN_PASSWORD:
                reset_data(mode="all", worksheet_name="Logs")
                reset_data(mode="all", worksheet_name="Liabilities")
                st.success("App Reset to Zero."); st.rerun()
            else: st.error("Wrong Password")

# --- DASHBOARD ---
st.title("💸 PhD Survival Kit")

if abs(rollover) > 1:
    color_roll = "#00cc96" if rollover > 0 else "#ff4b4b"
    label_roll = "Savings Carried Over" if rollover > 0 else "Debt Carried Over"
    sign_roll = "+" if rollover > 0 else ""
    st.markdown(f"""
    <div class="rollover-box" style="color: {color_roll};">
        💰 <b>{label_roll}:</b> {sign_roll}{rollover:.2f} MAD
    </div>""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
c1.metric("Balance", f"{current_balance:.2f} MAD")
c2.metric("Days Left", f"{days_remaining} d")
c3.metric("Daily Cap", f"{daily_safe_spend:.2f} MAD", delta_color="normal" if daily_safe_spend > 0 else "inverse")

st.divider()
render_smart_bar(current_balance, this_month_budget)
st.divider()

mode_action, mode_debt, mode_intel = st.tabs(["🚀 Action", "⚖️ Debt", "📊 Intel"])

with mode_action:
    with st.expander("➕ Add Transaction", expanded=True):
        t1, t2 = st.tabs(["Spend", "Earn"])
        with t1:
            with st.form("expense"):
                c_a, c_b = st.columns([2, 1])
                item = c_a.text_input("Item", placeholder="Coffee...")
                amt = c_b.number_input("Price", min_value=0.0, step=0.01)
                cat = st.selectbox("Category", ["Food", "Transport", "Fun","Personal Care","Bills","Other"])
                if st.form_submit_button("🔥 Burn It", type="primary"):
                    if amt > 0: save_entry(item, cat, amt); st.rerun()
        with t2:
            with st.form("income"):
                c_x, c_y = st.columns([2, 1])
                src = c_x.text_input("Source"); i_amt = c_y.number_input("Amount", min_value=0.0, step=0.01)
                if st.form_submit_button("🚀 Boost"):
                    if i_amt > 0: save_entry(src, "Income", -i_amt); st.balloons(); st.rerun()

    st.subheader("Recent Activity")
    if not df.empty:
        recent = df.tail(5).iloc[::-1].copy()
        for i, row in recent.iterrows():
            amt = row['Amount']; d_id = str(row['ID'])[-6:]
            if amt < 0:
                st.markdown(f"<div style='padding:10px;border-radius:5px;background-color:#1E1E1E;margin-bottom:5px;'><span class='item-name'>💰 {row['Item']}</span><span class='price-tag-pos'>+ {abs(amt):.2f} MAD</span><p style='font-size:0.75rem;color:#888;margin:0;'>ID: {d_id}</p></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='padding:10px;border-radius:5px;background-color:#1E1E1E;margin-bottom:5px;'><span class='item-name'>{row['Item']}</span><span class='price-tag-neg'>- {amt:.2f} MAD</span><p style='font-size:0.75rem;color:#888;margin:0;'>ID: {d_id}</p></div>", unsafe_allow_html=True)

with mode_debt:
    st.header("⚖️ Debt Ledger")
    with st.expander("➕ Log New Debt", expanded=False):
        with st.form("new_debt"):
            d_item = st.text_input("Description"); d_amt = st.number_input("Amount", min_value=0.01, step=0.01)
            if st.form_submit_button("Log Liability"):
                if d_item and d_amt > 0: save_entry(d_item, "DEBT_LOG", d_amt, worksheet_name="Liabilities"); st.success("Logged."); st.rerun()

    st.divider(); st.subheader("Active Liabilities")
    active = liabilities_df[liabilities_df['Status'] == 'PENDING'].copy()
    if not active.empty:
        active['Amount'] = pd.to_numeric(active['Amount'], errors='coerce')
        d_opts = {f"{r['Item']} ({r['Amount']:.2f})": r['Debt_ID'] for i, r in active.iterrows()}
        sel_d = st.selectbox("Pay Off", list(d_opts.keys()))
        if sel_d:
            sel_id = d_opts[sel_d]; owed = float(active[active['Debt_ID'] == sel_id]['Amount'].iloc[0])
            if st.button(f"✅ Pay {owed:.2f} MAD"):
                if settle_debt(sel_id, owed, sel_d): st.success("Paid!"); st.rerun()
    else: st.info("Debt-free!")
    
    with st.expander("History"):
        st.dataframe(liabilities_df.sort_values("Date_Paid", ascending=False), use_container_width=True)

with mode_intel:
    st.header("🧐 Analysis")
    if not df.empty:
        df['M'] = df['Date'].dt.to_period('M'); periods = sorted(df['M'].unique().astype(str), reverse=True)
        sel_p = st.selectbox("Period", periods); s_y, s_m = map(int, sel_p.split('-'))
        i_df = df[(df['Date'].dt.month == s_m) & (df['Date'].dt.year == s_y)].copy()
        
        if not i_df.empty:
            i_df['Amount'] = pd.to_numeric(i_df['Amount'], errors='coerce'); i_df = i_df.dropna(subset=['Amount'])
            tot = i_df[i_df['Amount'] > 0]['Amount'].sum(); st.metric(f"Total Spent", f"{tot:.2f} MAD")
            
            c_data = i_df[i_df['Amount'] > 0].groupby('Category')['Amount'].sum().reset_index()
            st.altair_chart(alt.Chart(c_data).mark_bar().encode(x=alt.X('Category', sort='-y'), y='Amount', color='Category'), use_container_width=True)
            
            with st.expander("Details"):
                d_df = i_df.copy().sort_values("Date", ascending=False); d_df['Amount'] *= -1
                d_df['Cost'] = d_df['Amount'].apply(lambda x: f"+{x:.2f}" if x>=0 else f"{x:.2f}")
                st.dataframe(d_df[['Date','Item','Category','Cost','ID']], use_container_width=True, hide_index=True)
        else: st.info("No data.")
    else: st.info("No data.")
