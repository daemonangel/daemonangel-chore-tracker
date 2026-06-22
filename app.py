import base64
import json
import requests
import streamlit as st

# --- CONFIG ---
st.set_page_config(page_title="Chore Tracker", page_icon="🧹", layout="centered")

# --- PRESET CHORES & PAYOUTS ---
# Edit this dictionary to change your family's standard jobs and rates
PRESET_CHORES = {
    "🧹 Vacuuming": 3.00,
    "🍽️ Dishwasher (Load/Empty)": 2.00,
    "🗑️ Take Out Trash/Recycling": 1.50,
    "🌱 Mowed Lawn": 15.00,
    "🐶 Fed Pets": 1.00,
    "🚗 Washed Car": 10.00,
    "➕ Custom Chore...": 0.00
}

# --- GITHUB API CONFIG ---
TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = st.secrets["REPO_NAME"]
PATH = st.secrets["FILE_PATH"]
URL = f"https://api.github.com/repos/{REPO}/contents/{PATH}"
HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}


def load_data_from_github():
    response = requests.get(URL, headers=HEADERS)
    if response.status_code == 200:
        file_data = response.json()
        content = base64.b64decode(file_data["content"]).decode("utf-8")
        return json.loads(content), file_data["sha"]
    elif response.status_code == 404:
        return {"people": {}}, None
    else:
        st.error(f"Failed to fetch data from GitHub: {response.text}")
        return {"people": {}}, None


def save_data_to_github(data, sha=None):
    content_str = json.dumps(data, indent=4)
    content_bytes = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
    payload = {"message": "Update chore data via Streamlit", "content": content_bytes}
    if sha:
        payload["sha"] = sha

    response = requests.put(URL, headers=HEADERS, json=payload)
    return response.status_code in [200, 201]


# --- INITIALIZE DATA ---
data, file_sha = load_data_from_github()

st.title("🧹 Chore & Payment Tracker")
st.write("Track chores and balances securely using your GitHub Repository.")

# --- APP UI ---
all_people = list(data["people"].keys())

# Sidebar: Add Family Members
st.sidebar.header("👤 Manage Family")
new_person = st.sidebar.text_input("Add New Person:").strip()
if st.sidebar.button("Add Person"):
    if new_person and new_person not in all_people:
        data["people"][new_person] = {"balance": 0.0, "history": []}
        if save_data_to_github(data, file_sha):
            st.sidebar.success(f"Added {new_person}!")
            st.rerun()
    elif new_person in all_people:
        st.sidebar.warning("Name already exists.")

# Main Page: Log a Chore
st.header("💰 Log a Chore")
if all_people:
    # 1. Who did it?
    who = st.selectbox("Who did it?", all_people)
    
    # 2. Select from Presets (using clickable pills)
    selected_preset = st.pills(
        "Select a preset job:", 
        options=list(PRESET_CHORES.keys()), 
        default="🧹 Vacuuming"
    )
    
    # 3. Dynamic Inputs based on the selected pill (with a safety fallback if unselected)
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # If "Custom" is picked OR nothing is selected at all (selected_preset is None)
        if selected_preset == "➕ Custom Chore..." or selected_preset is None:
            chore_name = st.text_input("Chore Description:", placeholder="e.g., Cleaned windows")
            default_val = 0.00
            is_disabled = False
        else:
            chore_name = selected_preset
            default_val = PRESET_CHORES[selected_preset]
            st.text_input("Chore Description:", value=chore_name, disabled=True)
            is_disabled = True
            
    with col2:
        value = st.number_input(
            "Payout ($)", 
            min_value=0.0, 
            value=default_val, 
            step=0.50, 
            format="%.2f",
            disabled=is_disabled
        )

    if st.button("Log Chore", type="primary"):
        if chore_name and chore_name != "➕ Custom Chore..." and value > 0:
            data["people"][who]["balance"] += value
            data["people"][who]["history"].append(
                {"chore": chore_name, "value": value, "paid": False}
            )
            if save_data_to_github(data, file_sha):
                st.success(f"Logged! Added ${value:.2f} to {who}'s balance.")
                st.rerun()
        else:
            st.error("Please ensure the chore has a valid description and a value greater than $0.")
else:
    st.info("👈 Start by adding a family member in the sidebar!")

st.markdown("---")

# Main Page: Balances & Payouts
st.header("📊 Current Balances")
if all_people:
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
                    if save_data_to_github(data, file_sha):
                        st.toast(f"Paid {person}!")
                        st.rerun()
            else:
                st.write("✅ All settled")

        if info["history"]:
            with st.expander(f"View {person}'s History"):
                for item in reversed(info["history"]):
                    status = "✅ Paid" if item["paid"] else "⏳ Unpaid"
                    st.write(f"- {item['chore']}: **${item['value']:.2f}** ({status})")
else:
    st.write("No family profiles logged yet.")
