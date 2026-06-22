import base64
import json
import requests
import streamlit as st

# --- CONFIG ---
st.set_page_config(page_title="Chore Tracker", page_icon="🧹", layout="centered")

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
all_people = list(data["people"].keys())

st.title("🧹 Chore & Payment Tracker")

# --- SECTION 1: LOG A CHORE ---
st.header("💰 Log a Chore")
if all_people:
    who = st.selectbox("Who did it?", all_people)
    
    selected_preset = st.pills(
        "Select a preset job:", 
        options=list(PRESET_CHORES.keys()), 
        default="🧹 Vacuuming"
    )
    
    col1, col2 = st.columns([2, 1])
    with col1:
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
            "Payout ($)", min_value=0.0, value=default_val, step=0.50, format="%.2f", disabled=is_disabled
        )

    if st.button("Submit for Approval", type="primary"):
        if chore_name and chore_name != "➕ Custom Chore..." and value > 0:
            # We add it to history with status "Pending" and do NOT add it to the balance yet
            import time
            chore_id = str(int(time.time())) # unique timestamp ID to easily track/delete it
            data["people"][who]["history"].append(
                {"id": chore_id, "chore": chore_name, "value": value, "status": "Pending"}
            )
            if save_data_to_github(data, file_sha):
                st.success(f"Submitted '{chore_name}' for {who}! Waiting for approval.")
                st.rerun()
        else:
            st.error("Please ensure the chore has a description and a value greater than $0.")
else:
    st.info("👈 Start by adding a family member in the sidebar!")

st.markdown("---")


# --- SECTION 2: APPROVAL QUEUE (ADMIN) ---
st.header("🛡️ Admin Approvals")
pending_chores = []

# Gather all pending items across all family profiles
for person, info in data["people"].items():
    for chore in info.get("history", []):
        if chore.get("status") == "Pending":
            pending_chores.append((person, chore))

if pending_chores:
    for person, chore in pending_chores:
        c_col1, c_col2, c_col3 = st.columns([2, 1, 1.5])
        with c_col1:
            st.write(f"**{person}**: {chore['chore']}")
        with c_col2:
            st.write(f"${chore['value']:.2f}")
        with c_col3:
            # Inline action buttons with unique keys
            btn_app, btn_deny = st.columns(2)
            with btn_app:
                if st.button("👍", key=f"app_{chore['id']}", help="Approve"):
                    chore["status"] = "Approved"
                    data["people"][person]["balance"] += chore["value"]
                    if save_data_to_github(data, file_sha):
                        st.rerun()
            with btn_deny:
                if st.button("👎", key=f"deny_{chore['id']}", help="Deny"):
                    chore["status"] = "Denied"
                    if save_data_to_github(data, file_sha):
                        st.rerun()
else:
    st.write("✅ No chores waiting for approval right now.")

st.markdown("---")


# --- SECTION 3: BALANCES & HISTORY REMOVAL ---
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
                    for c in info["history"]:
                        if c.get("status") == "Approved":
                            c["status"] = "Paid"
                    if save_data_to_github(data, file_sha):
                        st.toast(f"Paid {person}!")
                        st.rerun()
            else:
                st.write(" Settled")

        # History view with an absolute Delete button
        if info["history"]:
            with st.expander(f"View {person}'s History & Manage"):
                for item in reversed(info.get("history", [])):
                    status = item.get("status", "Approved")
                    
                    # Style based on status
                    if status == "Pending":
                        status_str = "⏳ Pending"
                    elif status == "Approved":
                        status_str = "🟢 Approved (Unpaid)"
                    elif status == "Denied":
                        status_str = "❌ Denied"
                    else:
                        status_str = "✅ Paid"
                        
                    h_col1, h_col2 = st.columns([4, 1])
                    with h_col1:
                        st.write(f"- {item['chore']}: **${item['value']:.2f}** ({status_str})")
                    with h_col2:
                        # Give a trash can button to entirely clear a chore entry
                        # Ensure we assign fallback structural IDs if running on older json entries
                        item_id = item.get("id", item['chore'])
                        if st.button("🗑️", key=f"del_{item_id}_{person}", help="Permanently Delete Entry"):
                            # If we delete an approved chore, subtract its value from their balance
                            if status == "Approved":
                                data["people"][person]["balance"] -= item["value"]
                            
                            info["history"].remove(item)
                            if save_data_to_github(data, file_sha):
                                st.rerun()
else:
    st.write("No family profiles logged yet.")

# Sidebar Settings
st.sidebar.header("👤 Manage Family")
new_person = st.sidebar.text_input("Add New Person:").strip()
if st.sidebar.button("Add Person"):
    if new_person and new_person not in all_people:
        data["people"][new_person] = {"balance": 0.0, "history": []}
        if save_data_to_github(data, file_sha):
            st.sidebar.success(f"Added {new_person}!")
            st.rerun()
