import json
import os
import streamlit as st

# --- CONFIG & DATA STORAGE ---
st.set_page_config(page_title="Chore Tracker", page_icon="🧹", layout="centered")
DATA_FILE = "chores_data.json"


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"people": {}}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


data = load_data()

# --- APP UI ---
st.title("🧹 Chore & Payment Tracker")
st.write("Track chores and balances for the whole family.")

# Sidebar: Add Family Members
st.sidebar.header("👤 Manage Family")
new_person = st.sidebar.text_input("Add New Person:").strip()
if st.sidebar.button("Add Person"):
    if new_person and new_person not in data["people"]:
        data["people"][new_person] = {"balance": 0.0, "history": []}
        save_data(data)
        st.sidebar.success(f"Added {new_person}!")
        st.rerun()
    elif new_person in data["people"]:
        st.sidebar.warning("Name already exists.")

# Main Page: Log a Chore
st.header("💰 Log a Chore")
if data["people"]:
    people_list = list(data["people"].keys())

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col1:
        who = st.selectbox("Who did it?", people_list)
    with col2:
        chore = st.text_input("What was the chore?", placeholder="e.g., Mowed Lawn")
    with col3:
        value = st.number_input("Payout ($)", min_value=0.0, step=0.50, format="%.2f")

    if st.button("Log Chore", type="primary"):
        if chore and value > 0:
            data["people"][who]["balance"] += value
            data["people"][who]["history"].append(
                {"chore": chore, "value": value, "paid": False}
            )
            save_data(data)
            st.success(f"Logged! Added ${value:.2f} to {who}'s balance.")
            st.rerun()
        else:
            st.error("Please enter a chore description and a value greater than $0.")
else:
    st.info("👈 Start by adding a family member in the sidebar!")

st.markdown("---")

# Main Page: Balances & Payouts
st.header("📊 Current Balances")
if data["people"]:
    for person, info in data["people"].items():
        col_name, col_bal, col_pay = st.columns([2, 1, 1])

        with col_name:
            st.subheader(person)
        with col_bal:
            st.subheader(f"${info['balance']:.2f}")
        with col_pay:
            if info["balance"] > 0:
                if st.button(f"Pay {person}", key=f"pay_{person}"):
                    data["people"][person]["balance"] = 0.0
                    for c in data["people"][person]["history"]:
                        c["paid"] = True
                    save_data(data)
                    st.toast(f"Paid {person}!")
                    st.rerun()
            else:
                st.write("✅ All settled")

        # Optional: Show short history dropdown per person
        if info["history"]:
            with st.expander(f"View {person}'s History"):
                for item in reversed(info["history"]):
                    status = "✅ Paid" if item["paid"] else "⏳ Unpaid"
                    st.write(f"- {item['chore']}: **${item['value']:.2f}** ({status})")
else:
    st.write("No data available yet.")
