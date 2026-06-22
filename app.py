import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# --- CONFIG ---
st.set_page_config(page_title="Chore Tracker", page_icon="🧹", layout="centered")

st.title("🧹 Daemonangel Chore Tracker")
st.write("Track chores and balances securely via Google Sheets.")

# --- CONNECT TO GOOGLE SHEETS ---
# This establishes the connection using the URL we will provide in Step 3
conn = st.connection("gsheets", type=GSheetsConnection)

# Read the existing data
try:
    df = conn.read(ttl="0d")  # ttl="0d" ensures it clears cache and fetches fresh data on every action
except Exception:
    # If the sheet is completely empty, create a starting placeholder DataFrame
    df = pd.DataFrame(columns=["Name", "Chore", "Value", "Paid"])

# --- PROCESS DATA FOR THE UI ---
# Calculate active balances based on unpaid chores
if not df.empty:
    unpaid_df = df[df["Paid"] == False]
    # Group by name and sum values
    balances = unpaid_df.groupby("Name")["Value"].sum().to_dict()
else:
    balances = {}

# Make sure all known people show up even if balance is 0
all_people = list(df["Name"].unique()) if not df.empty else []

# --- APP UI ---

# Sidebar: Add Family Members
st.sidebar.header("👤 Manage Family")
new_person = st.sidebar.text_input("Add New Person:").strip()
if st.sidebar.button("Add Person"):
    if new_person and new_person not in all_people:
        new_row = pd.DataFrame(
            [{"Name": new_person, "Chore": "Joined Tracker", "Value": 0.0, "Paid": True}]
        )
        df = pd.concat([df, new_row], ignore_index=True)
        conn.update(data=df)
        st.sidebar.success(f"Added {new_person}!")
        st.rerun()

# Main Page: Log a Chore
st.header("💰 Log a Chore")
if all_people:
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col1:
        who = st.selectbox("Who did it?", all_people)
    with col2:
        chore = st.text_input("What was the chore?", placeholder="e.g., Mowed Lawn")
    with col3:
        value = st.number_input("Payout ($)", min_value=0.0, step=0.50, format="%.2f")

    if st.button("Log Chore", type="primary"):
        if chore and value > 0:
            new_chore = pd.DataFrame(
                [{"Name": who, "Chore": chore, "Value": value, "Paid": False}]
            )
            df = pd.concat([df, new_chore], ignore_index=True)
            conn.update(data=df)
            st.success(f"Logged! Added ${value:.2f} to {who}'s balance.")
            st.rerun()
        else:
            st.error("Please enter a chore description and a value greater than $0.")
else:
    st.info("👈 Start by adding a family member in the sidebar!")

st.markdown("---")

# Main Page: Balances & Payouts
st.header("📊 Current Balances")
if all_people:
    for person in all_people:
        current_balance = balances.get(person, 0.0)
        col_name, col_bal, col_pay = st.columns([2, 1, 1])

        with col_name:
            st.subheader(person)
        with col_bal:
            st.subheader(f"${current_balance:.2f}")
        with col_pay:
            if current_balance > 0:
                if st.button(f"Pay {person}", key=f"pay_{person}"):
                    # Mark all this person's unpaid chores as Paid
                    df.loc[(df["Name"] == person) & (df["Paid"] == False), "Paid"] = True
                    conn.update(data=df)
                    st.toast(f"Paid {person}!")
                    st.rerun()
            else:
                st.write("✅ All settled")
else:
    st.write("No data available yet.")
