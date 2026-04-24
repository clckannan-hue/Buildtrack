import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import os

# ☁️ Database Connection
DB_URL = "postgresql://neondb_owner:npg_WqJld5Uu6nCE@ep-lucky-glitter-a14oql0y.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

# ==========================================
# 1. DATABASE SETUP
# ==========================================
def setup_database():
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS construction_expenses (
                exp_id SERIAL PRIMARY KEY,
                exp_date TEXT,
                exp_time TEXT,
                category TEXT,
                payee_desc TEXT,
                amount NUMERIC,
                pay_mode TEXT,
                reconciled TEXT DEFAULT 'Pending'
            );
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Database Error: {e}")

setup_database()

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def fetch_data():
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM construction_expenses ORDER BY exp_id DESC")
    data = cursor.fetchall()
    conn.close()
    
    columns = ["ID", "Date", "Time", "Category", "Description", "Amount (Rs)", "Mode", "Status"]
    if data:
        df = pd.DataFrame(data, columns=columns)
    else:
        df = pd.DataFrame(columns=columns)
    return df

# ==========================================
# 3. STREAMLIT UI SETUP
# ==========================================
st.set_page_config(page_title="BuildTrack App", page_icon="🏠", layout="centered")

st.title("🏠 BuildTrack")
st.subheader("House Construction Expense Tracker")

# Tabs for easy mobile navigation
tab1, tab2, tab3 = st.tabs(["➕ புதிய செலவு (Add)", "📋 செலவு பட்டியல் (View/Manage)", "📊 ரிப்போர்ட் (Reports)"])

# ------------------------------------------
# TAB 1: ADD EXPENSE
# ------------------------------------------
with tab1:
    with st.form("add_expense_form"):
        st.write("### புதிய செலவைப் பதிய")
        col1, col2 = st.columns(2)
        with col1:
            exp_date = st.date_input("தேதி (Date)", datetime.now())
        with col2:
            exp_time = st.time_input("நேரம் (Time)", datetime.now().time())
            
        category = st.selectbox("செலவு வகை (Category)", [
            "Builder/Vendor Payment (Requires Reconciliation)", 
            "Miscellaneous Expenses", 
            "Processing Charges"
        ])
        
        desc = st.text_input("கொடுத்தவர் / விவரம் (Description)", placeholder="உதா: Ram Cements - 100 bags")
        
        col3, col4 = st.columns(2)
        with col3:
            amount = st.number_input("தொகை / Amount (₹)", min_value=0.0, step=100.0)
        with col4:
            pay_mode = st.selectbox("பட்டுவாடா முறை (Mode)", ["RTGS/NEFT", "Cash", "Cheque", "GPay"])
            
        submitted = st.form_submit_button("💾 Save Expense")
        
        if submitted:
            if amount <= 0 or not desc:
                st.warning("விவரம் மற்றும் தொகையைச் சரியாக உள்ளிடவும்!")
            else:
                formatted_date = exp_date.strftime("%d-%m-%Y")
                formatted_time = exp_time.strftime("%I:%M %p")
                recon_status = "Pending" if category == "Builder/Vendor Payment (Requires Reconciliation)" or pay_mode == "Cash" else "N/A"
                
                try:
                    conn = psycopg2.connect(DB_URL)
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO construction_expenses 
                        (exp_date, exp_time, category, payee_desc, amount, pay_mode, reconciled) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ''', (formatted_date, formatted_time, category, desc, amount, pay_mode, recon_status))
                    conn.commit()
                    conn.close()
                    st.success("✅ செலவு வெற்றிகரமாக சேமிக்கப்பட்டது!")
                except Exception as e:
                    st.error(f"Error: {e}")

# ------------------------------------------
# TAB 2: VIEW & MANAGE EXPENSES
# ------------------------------------------
with tab2:
    st.write("### பதிவு செய்யப்பட்ட செலவுகள்")
    df = fetch_data()
    st.dataframe(df, use_container_width=True)
    
    st.divider()
    st.write("### ⚙️ கணக்கை நேர் செய்ய / நீக்க (Manage)")
    
    if not df.empty:
        action_id = st.number_input("மாற்ற வேண்டிய பில் ID-ஐ உள்ளிடவும்:", min_value=1, step=1)
        
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button("✔️ Mark as Reconciled"):
                try:
                    conn = psycopg2.connect(DB_URL)
                    cursor = conn.cursor()
                    # Check if ID exists and is applicable
                    cursor.execute("SELECT category, pay_mode FROM construction_expenses WHERE exp_id = %s", (action_id,))
                    res = cursor.fetchone()
                    if res:
                        if res[0] == "Builder/Vendor Payment (Requires Reconciliation)" or res[1] == "Cash":
                            cursor.execute("UPDATE construction_expenses SET reconciled = 'Reconciled ✓' WHERE exp_id = %s", (action_id,))
                            conn.commit()
                            st.success(f"ID {action_id} கணக்கு நேர் செய்யப்பட்டது (Reconciled)!")
                        else:
                            st.warning("இந்த செலவுக்கு Reconcile தேவையில்லை.")
                    else:
                        st.error("தவறான ID.")
                    conn.close()
                except Exception as e:
                    st.error(f"Error: {e}")
                    
        with col_act2:
            if st.button("🗑️ Delete Expense"):
                try:
                    conn = psycopg2.connect(DB_URL)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM construction_expenses WHERE exp_id = %s", (action_id,))
                    conn.commit()
                    conn.close()
                    st.success(f"ID {action_id} வெற்றிகரமாக நீக்கப்பட்டது!")
                except Exception as e:
                    st.error(f"Error: {e}")
    else:
        st.info("தகவல்கள் எதுவும் இல்லை.")

# ------------------------------------------
# TAB 3: REPORTS (PDF & CSV)
# ------------------------------------------
with tab3:
    st.write("### 📊 அறிக்கைகள் (Export)")
    df = fetch_data()
    
    if not df.empty:
        # --- CSV DOWNLOAD ---
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📊 Download Excel (CSV)",
            data=csv_data,
            file_name=f"House_Expenses_{datetime.now().strftime('%d%m%Y')}.csv",
            mime="text/csv",
        )
        
        st.write("---")
        
        # --- PDF GENERATION LOGIC ---
        if st.button("📄 Generate Builder PDF Report"):
            pdf = FPDF(orientation='L', unit='mm', format='A4') 
            pdf.add_page()
            
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, "House Construction Expense Report", ln=True, align='C')
            pdf.set_font("Arial", '', 10)
            pdf.cell(0, 10, f"Generated on: {datetime.now().strftime('%d-%m-%Y %I:%M %p')}", ln=True, align='C')
            pdf.ln(5)

            headers = ["ID", "Date", "Category", "Description", "Mode", "Amount", "Reconciled", "Status"]
            col_widths = [10, 22, 45, 80, 20, 25, 25, 30] 
            
            pdf.set_font("Arial", 'B', 9)
            for i in range(len(headers)):
                pdf.cell(col_widths[i], 8, headers[i], border=1, align='C')
            pdf.ln()

            df_sorted = df.sort_values(by="ID")
            
            grand_total_amt = 0.0
            grand_total_rec = 0.0
            category_totals = {}

            pdf.set_font("Arial", '', 8)
            for index, row in df_sorted.iterrows():
                cat_text = str(row['Category'])
                if "Requires Reconciliation" in cat_text:
                    cat_text = "Builder/Vendor Payment"
                    
                amt = float(row['Amount (Rs)'])
                status_clean = str(row['Status']).replace('✓', '').strip()
                rec_amt = amt if "Reconciled" in status_clean else 0.0

                grand_total_amt += amt
                grand_total_rec += rec_amt

                if cat_text not in category_totals:
                    category_totals[cat_text] = {'amount': 0.0, 'reconciled': 0.0}
                category_totals[cat_text]['amount'] += amt
                category_totals[cat_text]['reconciled'] += rec_amt

                pdf.cell(col_widths[0], 8, str(row['ID']), border=1, align='C')
                pdf.cell(col_widths[1], 8, str(row['Date']), border=1, align='C')
                pdf.cell(col_widths[2], 8, cat_text[:30], border=1) 
                pdf.cell(col_widths[3], 8, str(row['Description'])[:60], border=1)
                pdf.cell(col_widths[4], 8, str(row['Mode']), border=1, align='C')
                pdf.cell(col_widths[5], 8, f"{amt:.2f}", border=1, align='R')
                pdf.cell(col_widths[6], 8, f"{rec_amt:.2f}", border=1, align='R')
                pdf.cell(col_widths[7], 8, status_clean, border=1, align='C')
                pdf.ln()

            # Main Grand Total
            pdf.set_font("Arial", 'B', 9)
            span_width = sum(col_widths[:5])
            pdf.cell(span_width, 8, "GRAND TOTAL", border=1, align='R')
            pdf.cell(col_widths[5], 8, f"{grand_total_amt:.2f}", border=1, align='R')
            pdf.cell(col_widths[6], 8, f"{grand_total_rec:.2f}", border=1, align='R')
            pdf.cell(col_widths[7], 8, "", border=1, align='C')
            pdf.ln(15)

            # SUMMARY TALLY
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 10, "Category-wise Expense Summary (Tally)", ln=True, align='L')
            sum_headers = ["Expense Category", "Total Amount (Rs)", "Reconciled Amount (Rs)", "Pending Balance (Rs)"]
            sum_widths = [80, 40, 40, 40]

            pdf.set_font("Arial", 'B', 9)
            for i in range(len(sum_headers)):
                pdf.cell(sum_widths[i], 8, sum_headers[i], border=1, align='C')
            pdf.ln()

            pdf.set_font("Arial", '', 9)
            for cat, totals in category_totals.items():
                cat_amt = totals['amount']
                cat_rec = totals['reconciled']
                cat_bal = cat_amt - cat_rec
                
                pdf.cell(sum_widths[0], 8, cat, border=1)
                pdf.cell(sum_widths[1], 8, f"{cat_amt:.2f}", border=1, align='R')
                pdf.cell(sum_widths[2], 8, f"{cat_rec:.2f}", border=1, align='R')
                pdf.cell(sum_widths[3], 8, f"{cat_bal:.2f}", border=1, align='R')
                pdf.ln()

            pdf.set_font("Arial", 'B', 9)
            pdf.cell(sum_widths[0], 8, "TOTAL TALLY", border=1, align='R')
            pdf.cell(sum_widths[1], 8, f"{grand_total_amt:.2f}", border=1, align='R')
            pdf.cell(sum_widths[2], 8, f"{grand_total_rec:.2f}", border=1, align='R')
            pdf.cell(sum_widths[3], 8, f"{grand_total_amt - grand_total_rec:.2f}", border=1, align='R')
            pdf.ln()

            # Streamlit-ல் PDF டவுன்லோட் செய்ய
            pdf_file_name = f"Builder_Report_{datetime.now().strftime('%d%m%Y')}.pdf"
            pdf.output(pdf_file_name)
            
            with open(pdf_file_name, "rb") as f:
                pdf_bytes = f.read()
                
            st.success("PDF ரெடி! கீழே உள்ள பட்டனை அழுத்தி Download செய்துகொள்ளவும்.")
            st.download_button(
                label="📥 Download PDF",
                data=pdf_bytes,
                file_name=pdf_file_name,
                mime="application/pdf"
            )
    else:
        st.info("டவுன்லோட் செய்ய எந்தத் தகவலும் இல்லை.")
