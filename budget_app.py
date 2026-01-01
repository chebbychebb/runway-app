import streamlit as st
import pandas as pd
import datetime
import time 
from streamlit_gsheets import GSheetsConnection
import altair as alt
import pytz

# --- CONFIG ---
st.set_page_config(page_title="PhD Survival Kit", page_icon="💸", layout="centered")

# --- AESTHETICS & CSS (Safe Version) ---
st.markdown("""
    <style>
        /* Hides the 'Made with Streamlit' footer */
        footer {visibility: hidden;}
        
        /* Standard padding */
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
        .stMarkdown { white-space: normal; }
    </style>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
""", unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

# --- DEFAULTS ---
DEFAULT_ALLOWANCE = 1300.0  
FIXED_COSTS = 0.0  
ADMIN_PASSWORD = "1234"  

# --- DATA ENGINE (LOADERS) ---
def load_data(worksheet_name="Logs"):
    # Load transactions (Logs) OR liabilities (Liabilities)
    df = conn.read(worksheet=worksheet_name, ttl=0) 
    df = df.dropna(how='all')
    if not df.empty:
        # Only process 'Date' column if it exists in the sheet (Liabilities sheet has different columns)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date'])
    return df

def save_entry(item, category, amount, worksheet_name="Logs"):
    unique_id = "ID-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    
    df = load_data(worksheet_name=worksheet_name)
    
    # Create the new row dynamically based on context
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
            "Date_Paid": ["PENDING"], # Initial status
            "Status": ["PENDING"],
            "Debt_ID": [unique_id] 
        })

    updated_df = pd.concat([df, new_row], ignore_index=True)
    
    # Ensure date columns are strings before saving back
    if 'Date' in updated_df.columns:
        updated_df['Date'] = updated_df['Date'].apply(lambda x: x.strftime('%Y-%m-%d'))
    
    conn.update(worksheet=worksheet_name, data=updated_df)

# --- DEBT MANAGEMENT LOGIC ---
def add_new_debt(item, amount):
    # Amount is saved as positive debt value
    save_entry(item, amount, amount, worksheet_name="Liabilities")

def settle_debt(debt_id, amount_paid, item_name):
    # 1. Load Liabilities
    liabilities_df = load_data(worksheet_name="Liabilities")
    
    # 2. Find the row and update status
    liabilities_df['Debt_ID_str'] = liabilities_df['Debt_ID'].astype(str)
    row_index = liabilities_df[liabilities_df['Debt_ID_str'] == debt_id].index
    
    if not row_index.empty:
        # Update liability status
        liabilities_df.loc[row_index, 'Date_Paid'] = pd.Timestamp(datetime.date.today()).strftime('%Y-%m-%d')
        liabilities_df.loc[row_index, 'Status'] = 'PAID'
        liabilities_df.loc[row_index, 'Amount'] = amount_paid # Record the settled amount
        
        # 3. Log Payment in Transaction Sheet (CRUCIAL: Deducts from balance)
        # Category "Debt Payment"
        save_entry(f"Payment: {item_name}", "Debt Payment", amount_paid, worksheet_name="Logs")
        
        # 4. Save the updated Liabilities sheet
        liabilities_df = liabilities_df.drop(columns=['Debt_ID_str'])
        conn.update(worksheet="Liabilities", data=liabilities_df)
        return True
        
    return False

# --- DELETE LOGIC (FINAL FIXED VERSION) ---
def delete_entry(entry_id, worksheet_name="Logs"):
    df = load_data(worksheet_name=worksheet_name)
    
    entry_id = str(entry_id).strip()
    
    if worksheet_name == "Logs":
        # Check if the ID is missing the prefix and add it back for lookup
        if not entry_id.startswith("ID-"):
            entry_id = "ID-" + entry_id
        df['ID'] = df['ID'].astype(str)
        id_col = 'ID'
    elif worksheet_name == "Liabilities":
        if not entry_id.startswith("ID-"):
            entry_id = "ID-" + entry_id
        df['Debt_ID'] = df['Debt_ID'].astype(str)
        id_col = 'Debt_ID'
    
    initial_count = len(df)
    
    df_kept = df[df[id_col] != entry_id].copy()
    deleted_count = initial_count - len(df_kept)
    
    if not df_kept.empty:
        if 'Date' in df_kept.columns:
            df_kept['Date'] = df_kept['Date'].apply(lambda x: x.strftime('%Y-%m-%d'))
    
    conn.update(worksheet=worksheet_name, data=df_kept)
    return deleted_count


# --- RESET LOGIC ---
def reset_data(mode="all", worksheet_name="Logs"):
    # Ensure the empty DataFrame has the new ID column
    if worksheet_name == "Logs":
        empty_df = pd.DataFrame(columns=["Date", "Item", "Category", "Amount", "ID"])
        conn.update(worksheet="Logs", data=empty_df)
    elif worksheet_name == "Liabilities":
        empty_df = pd.DataFrame(columns=['Item', 'Amount', 'Date_Borrowed', 'Date_Paid', 'Status', 'Debt_ID'])
        conn.update(worksheet="Liabilities", data=empty_df)
    # Month reset logic remains complex, so we won't allow for Liabilities just yet

# --- SMART BAR ENGINE (UNCHANGED) ---
def render_smart_bar(current_balance, total_monthly_budget):
    if current_balance > total_monthly_budget:
        surplus = current_balance - total_monthly_budget
        fill_pct = 100
        color = "#00cc96" 
        label = "🟢 EXTRA SURPLUS"
        status_text = f"+{surplus:.2f} MAD Above Budget" 
    elif current_balance < 0:
        debt = abs(current_balance)
        fill_pct = 100
        color = "#ff4b4b" 
        label = "🔴 DEBT ALERT"
        status_text = f"-{debt:.2f} MAD Overdrawn"
    else:
        if total_monthly_budget > 0:
            fill_pct = (current_balance / total_monthly_budget) * 100
            color = "#29b5e8" 
            label = "🔵 CURRENT MONTH BUDGET"
            status_text = f"{fill_pct:.1f}% Remaining"
        else:
            fill_pct = 0
            color = "#808080"
            label = "⚫ LOW BUDGET BASE"
            status_text = "N/A"

    st.markdown(f"""
        <div style="margin-bottom: 5px; font-size: 0.8rem; color: #888;">{label}</div>
        <div style="background-color: #333; border-radius: 10px; height: 25px; width: 100%;">
            <div style="background-color: {color}; width: {fill_pct}%; height: 100%; border-radius: 10px; transition: width 0.5s;"></div>
        </div>
        <div style="text-align: right; font-size: 0.8rem; color: {color}; margin-top: 5px; font-weight: bold;">
            {status_text}
        </div>
    """, unsafe_allow_html=True)

# --- MAIN LOGIC (REVISED FOR HISTORICAL ALLOWANCE) ---
try:
    full_df = load_data()
    liabilities_df = load_data(worksheet_name="Liabilities")
except Exception as e:
    full_df = pd.DataFrame(columns=["Date", "Item", "Category", "Amount", "ID"])
    liabilities_df = pd.DataFrame(columns=['Item', 'Amount', 'Date_Borrowed', 'Date_Paid', 'Status', 'Debt_ID'])

# 1. SPLIT DATA
if not full_df.empty:
    df = full_df[full_df['Category'] != 'ADMIN'].copy()
    
    # Determine the current allowance (for this month)
    admin_df = full_df[full_df['Category'] == 'ADMIN']
    if not admin_df.empty:
        last_admin_row = admin_df.iloc[-1]
        MONTHLY_ALLOWANCE = float(last_admin_row['Amount'])
    else:
        MONTHLY_ALLOWANCE = DEFAULT_ALLOWANCE
else:
    df = pd.DataFrame(columns=["Date", "Item", "Category", "Amount", "ID"])
    MONTHLY_ALLOWANCE = DEFAULT_ALLOWANCE

# SET TIMEZONE
CASABLANCA_TZ = pytz.timezone('Africa/Casablanca')
today_dt = datetime.datetime.now(CASABLANCA_TZ)
today = today_dt.date()

# 2. ROLLOVER (HISTORICALLY ACCURATE VERSION)
rollover = 0.0

if not df.empty:
    start_date = df['Date'].min().date()
    
    # We iterate from the first month of data up until the START of the current month
    # This allows us to calculate exactly what was saved/lost in each past month based on the allowance at that time.
    iter_date = datetime.date(start_date.year, start_date.month, 1)
    current_month_start = datetime.date(today.year, today.month, 1)
    
    while iter_date < current_month_start:
        # Determine the end of the iteration month
        if iter_date.month == 12:
            next_month_start = datetime.date(iter_date.year + 1, 1, 1)
        else:
            next_month_start = datetime.date(iter_date.year, iter_date.month + 1, 1)
            
        # A. Calculate Spend for this past month
        # We filter the dataframe for transactions falling strictly within this month
        month_mask = (df['Date'] >= pd.Timestamp(iter_date)) & (df['Date'] < pd.Timestamp(next_month_start))
        monthly_spend = df.loc[month_mask, "Amount"].sum()
        
        # B. Find the Allowance that was active at the END of this past month
        # We look for ADMIN entries logged before the next month started.
        historical_admin_mask = (full_df['Category'] == 'ADMIN') & (full_df['Date'] < pd.Timestamp(next_month_start))
        historical_admin = full_df[historical_admin_mask]
        
        if not historical_admin.empty:
            # The last entry before the month ended is the one that ruled that month
            historical_limit = float(historical_admin.sort_values('Date').iloc[-1]['Amount'])
        else:
            historical_limit = DEFAULT_ALLOWANCE
            
        # C. Add this month's result to the running rollover total
        rollover += (historical_limit - monthly_spend)
        
        # Move to the next month
        iter_date = next_month_start

# 3. CURRENT MONTH
if not df.empty:
    current_mask = (df['Date'].dt.month == today.month) & (df['Date'].dt.year == today.year)
    current_month_spend = df.loc[current_mask, "Amount"].sum()
else:
    current_month_spend = 0.0

# 4. TOTALS
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
    
    # ALLOWANCE SETTING
    with st.expander("💰 Edit Allowance"):
        new_allowance = st.number_input("New Monthly Limit", value=MONTHLY_ALLOWANCE, step=0.01)
        password_allowance = st.text_input("Password", type="password", key="pw_allowance")
        
        if st.button("Update Allowance"):
            if password_allowance == ADMIN_PASSWORD:
                save_entry("Allowance Update", "ADMIN", new_allowance)
                st.success(f"Allowance changed to {new_allowance:.2f}")
                st.rerun()
            else:
                st.error("Wrong Password")

    # DELETE SINGLE ENTRY (FIXED)
    with st.expander("✂️ Delete Entry"):
        st.caption("Copy the full ID from the Intel Tab.")
        entry_id_input = st.text_input("Transaction ID to Delete")
        password_delete = st.text_input("Password", type="password", key="pw_delete")
        
        if st.button("Delete Transaction"):
            if password_delete == ADMIN_PASSWORD:
                if not entry_id_input:
                    st.error("Please enter a valid ID.")
                else:
                    try:
                        # Deletes from Logs sheet
                        deleted_rows = delete_entry(entry_id_input.strip(), worksheet_name="Logs")
                        if deleted_rows > 0:
                            st.success(f"✅ Entry deleted successfully. {deleted_rows} row(s) removed.")
                        else:
                            st.warning("⚠️ No matching ID found.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Deletion failed: {e}")
            else:
                st.error("Wrong Password")

    # DANGER ZONE
    with st.expander("⚠️ Danger Zone"):
        password_reset = st.text_input("Password", type="password", key="pw_reset")
        
        st.caption("Reset Current Month")
        if st.button("🗑️ Wipe This Month"):
            if password_reset == ADMIN_PASSWORD:
                reset_data(mode="month", worksheet_name="Logs")
                st.success("Month wiped.")
                st.rerun()
            else:
                st.error("Wrong Password")
        
        st.caption("Factory Reset (Delete All)")
        if st.button("☢️ RESET EVERYTHING"):
            if password_reset == ADMIN_PASSWORD:
                reset_data(mode="all", worksheet_name="Logs")
                reset_data(mode="all", worksheet_name="Liabilities") # Wipe both sheets
                st.success("App Reset to Zero.")
                st.rerun()
            else:
                st.error("Wrong Password")

# --- DASHBOARD ---
st.title("💸 PhD Survival Kit")

# Show Rollover
if abs(rollover) > 1:
    if rollover > 0:
        st.markdown(f"""
        <div class="rollover-box" style="color: #00cc96;">
            💰 <b>Savings Carried Over:</b> +{rollover:.2f} MAD added to this month.
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="rollover-box" style="color: #ff4b4b;">
            📉 <b>Debt Carried Over:</b> {rollover:.2f} MAD deducted from this month.
        </div>""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
c1.metric("Balance", f"{current_balance:.2f} MAD", delta=None)
c2.metric("Days Left", f"{days_remaining} d")
c3.metric("Daily Cap", f"{daily_safe_spend:.2f} MAD", 
          delta_color="normal" if daily_safe_spend > 0 else "inverse")

st.divider()
render_smart_bar(current_balance, this_month_budget)
st.divider()

# --- TABS ---
mode_action, mode_debt, mode_intel = st.tabs(["🚀 Action", "⚖️ Debt", "📊 Intel"])

# === ACTION TAB ===
with mode_action:
    with st.expander("➕ Add Transaction", expanded=True):
        tab_expense, tab_income = st.tabs(["Spend", "Earn"])
        
        with tab_expense:
            with st.form("expense_form", clear_on_submit=True):
                c_a, c_b = st.columns([2, 1])
                item = c_a.text_input("Item", placeholder="Coffee...")
                amt = c_b.number_input("Price", min_value=0.0, step=0.01)
                cat = st.selectbox("Category", ["Food", "Transport", "Fun","Personal Care","Bills","Other"])
                if st.form_submit_button("🔥 Burn It", type="primary"):
                    if amt > 0:
                        save_entry(item, cat, amt)
                        st.rerun()

        with tab_income:
            with st.form("income_form", clear_on_submit=True):
                c_x, c_y = st.columns([2, 1])
                source = c_x.text_input("Source")
                inc_amt = c_y.number_input("Amount", min_value=0.0, step=0.01)
                if st.form_submit_button("🚀 Boost"):
                    if inc_amt > 0:
                        save_entry(source, "Income", -inc_amt)
                        st.balloons()
                        st.rerun()

    st.subheader("Recent Activity")
    if not df.empty:
        recent = df.tail(5).iloc[::-1].copy()
        
        for index, row in recent.iterrows():
            amt = row['Amount']
            display_id = str(row['ID'])[-6:] 
            
            if amt < 0:
                st.markdown(f"""
                <div style="padding: 10px; border-radius: 5px; background-color: #1E1E1E; margin-bottom: 5px;">
                    <span class="item-name">💰 {row['Item']}</span>
                    <span class="price-tag-pos">+ {abs(amt):.2f} MAD</span>
                    <p style='font-size: 0.75rem; color: #888; margin: 0;'>ID: {display_id} (Full ID: {str(row['ID'])[:6]}...)</p>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="padding: 10px; border-radius: 5px; background-color: #1E1E1E; margin-bottom: 5px;">
                    <span class="item-name">{row['Item']}</span>
                    <span class="price-tag-neg">- {amt:.2f} MAD</span>
                    <p style='font-size: 0.75rem; color: #888; margin: 0;'>ID: {display_id} (Full ID: {str(row['ID'])[:6]}...)</p>
                </div>""", unsafe_allow_html=True)

# === DEBT TAB (NEW) ===
with mode_debt:
    st.header("⚖️ Debt Ledger")
    st.caption("Transactions here affect your balance ONLY when settled.")
    
    # 1. ADD NEW DEBT
    with st.expander("➕ Log New Debt", expanded=False):
        with st.form("new_debt_form", clear_on_submit=True):
            debt_item = st.text_input("To whom/For what is the debt?")
            debt_amt = st.number_input("Amount Owed (MAD)", min_value=0.01, step=0.01)
            
            if st.form_submit_button("Log Liability"):
                if debt_item and debt_amt > 0:
                    # FIX: Passed "DEBT_LOG" as the placeholder for the unused 'category' slot.
                    save_entry(debt_item, "DEBT_LOG", debt_amt, worksheet_name="Liabilities")
                    st.success(f"Liability for {debt_amt:.2f} MAD logged.")
                    st.rerun()
                else:
                    st.error("Please enter a description and amount.")
    
    st.divider()
    
    # 2. SETTLE DEBT (The payment mechanism)
    st.subheader("Active Liabilities")
    
    # Filter liabilities for PENDING only
    active_debt = liabilities_df[liabilities_df['Status'] == 'PENDING'].copy()
    
    if not active_debt.empty:
        # Create a dictionary for the select box: {Item Name: Debt_ID}
        # Ensure 'Amount' is float for formatting
        active_debt['Amount'] = pd.to_numeric(active_debt['Amount'], errors='coerce')
        
        debt_options = {
            f"{row['Item']} (Owed: {row['Amount']:.2f} MAD)": row['Debt_ID']
            for index, row in active_debt.iterrows()
        }
        
        selected_debt_item = st.selectbox("Select Debt to Pay Off", list(debt_options.keys()))
        
        # Get the ID of the selected debt
        if selected_debt_item:
            selected_debt_id = debt_options[selected_debt_item]
            owed_amount = float(active_debt[active_debt['Debt_ID'] == selected_debt_id]['Amount'].iloc[0])
            
            st.warning(f"You are settling debt for {owed_amount:.2f} MAD. This will deduct the amount from your available balance.")
            
            if st.button(f"✅ Confirm Payment of {owed_amount:.2f} MAD"):
                if settle_debt(selected_debt_id, owed_amount, selected_debt_item):
                    st.success("Payment confirmed and logged to transactions.")
                    st.rerun()
                else:
                    st.error("Payment settlement failed.")
    
    else:
        st.info("You currently have no active liabilities. You are debt-free!")

    # 3. HISTORY
    with st.expander("History of Paid Debts", expanded=False):
        st.dataframe(
            liabilities_df.sort_values(by="Date_Paid", ascending=False),
            use_container_width=True,
            column_config={
                "Amount": st.column_config.NumberColumn(format="%.2f MAD"),
                "Debt_ID": st.column_config.TextColumn("Debt ID (Hidden)", disabled=True),
            }
        )

# === INTEL TAB ===
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
            
            intel_df['Amount'] = pd.to_numeric(intel_df['Amount'], errors='coerce')
            intel_df = intel_df.dropna(subset=['Amount'])

            total_selected_spend = intel_df[intel_df['Amount'] > 0].groupby('Category')['Amount'].sum().reset_index()
            st.metric(f"Total Spent in {selected_period}", f"{total_selected_spend['Amount'].sum():.2f} MAD")

            st.caption("Spending by Category")
            cat_data = intel_df[intel_df['Amount'] > 0].groupby('Category')['Amount'].sum().reset_index()
            chart = alt.Chart(cat_data).mark_bar().encode(
                x=alt.X('Category', sort='-y'),
                y='Amount',
                color=alt.Color('Category', legend=None),
                tooltip=['Category', alt.Tooltip('Amount', format='.2f')]
            )
            st.altair_chart(chart, use_container_width=True)

            st.divider()
            with st.expander(f"📂 View Details for {selected_period}", expanded=True):
                display_df = intel_df.copy().sort_values(by="Date", ascending=False)
                
                display_df['Amount'] = display_df['Amount'] * -1
                
                def format_currency_for_display(val):
                    return f"+{val:.2f} MAD" if val >= 0 else f"{val:.2f} MAD"
                
                display_df['Cost'] = display_df['Amount'].apply(format_currency_for_display)
                
                st.dataframe(
                    display_df[['Date', 'Item', 'Category', 'Cost', 'ID']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={"Date": st.column_config.DateColumn("Date", format="MMM DD"),
                                   "ID": st.column_config.TextColumn("ID (for Deletion)", help="First few digits of the unique transaction ID")}
                )
        else:
            st.info("No data found for this period.")
    else:
        st.info("Log some expenses to unlock Analysis.")
