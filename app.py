import base64
from datetime import datetime
import json
import time
import requests
import streamlit as st

# --- CONFIG ---
st.set_page_config(page_title="Chore Tracker", page_icon="🧹", layout="centered")

PRESET_CHORES = {
    "🛋️ Common Space Reset (Clutter put away)": 1.00,
    "🛌 Personal Room Tidy (Bed made, floor clear)": 1.00,
    "🧺 Partial Laundry Service (Wash, Dry, Fold OR Put Away)": 1.00,
    "🍽️ Dishwasher (Load or Empty)": 2.00,
    "🗑️ Take Out Trash/Recycling": 2.00,
    "🎛️ Microwave (Clean Inside & Out)": 2.00,
    "🧼 High-Touch Sanitize (Knobs, remotes, switches)": 2.00,
    "🪶 Dusting & Wiping Shared Living Spaces": 3.00,
    "🧹 Vacuuming": 3.00,
    "🧺 Full Laundry Service (Wash, Dry, Fold & Put Away)": 4.00,
    "🧊 Fridge Cleanout & Organize": 4.00,
    "🍳 Cook a Family Meal": 4.00,
    "🧽 Clean Kitchen (dishes and all surfaces)": 4.00,
    "🧹 Vacuum & Mop Downstairs or Upstairs": 6.00,
    "🧼 Deep Clean Bathroom (Toilet/Sink/Shower)": 8.00,
    "🚗 Wash Car": 10.00,
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
    
    # 💡 FIX: If the save is successful, update our local SHA key with GitHub's new one
    if response.status_code in [200, 201]:
        res_json = response.json()
        if "content" in res_json and "sha" in res_json["content"]:
            st.session_state.file_sha = res_json["content"]["sha"]
        return True
    else:
        st.error(f"GitHub Sync Failed: {response.text}")
        return False

def prune_old_history(data):
    current_time = datetime.now()
    updated = False
    
    for person, info in data["people"].items():
        clean_history = []
        for item in info.get("history", []):
            status = item.get("status")
            keep_item = True
            
            # 1. Prune Denied entries after 30 days
            if status == "Denied" and "timestamp" in item:
                try:
                    entry_date = datetime.strptime(item["timestamp"], "%m/%d/%y at %I:%M %p")
                    if (current_time - entry_date).days > 30:
                        keep_item = False
                        updated = True
                except ValueError:
                    pass
                    
            # 2. Prune individual Paid chores after 30 days
            elif status == "Paid" and "paid_timestamp" in item:
                try:
                    pay_date = datetime.strptime(item["paid_timestamp"], "%m/%d/%y at %I:%M %p")
                    if (current_time - pay_date).days > 30:
                        keep_item = False
                        updated = True
                except ValueError:
                    pass
            
            # Note: Items with status "Payout" are explicitly skipped here so they are NEVER pruned.
            if keep_item:
                clean_history.append(item)
                
        info["history"] = clean_history
        
    if updated:
        save_data_to_github(data, st.session_state.file_sha)


# --- INITIALIZE DATA & SESSION STATE ---
if "data" not in st.session_state or "file_sha" not in st.session_state:
    data, file_sha = load_data_from_github()
    st.session_state.data = data
    st.session_state.file_sha = file_sha
    
    if st.session_state.data and "people" in st.session_state.data:
        prune_old_history(st.session_state.data)

if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

data = st.session_state.data
file_sha = st.session_state.file_sha
all_people = list(data["people"].keys())

st.title("🧹 Chore & Payment Tracker")


# --- ACTION HANDLERS ---
def handle_submission(who, chore_name, value):
    if chore_name and chore_name != "➕ Custom Chore..." and value > 0:
        chore_id = str(int(time.time()))
        timestamp = datetime.now().strftime("%m/%d/%y at %I:%M %p")
        
        st.session_state.data["people"][who]["history"].append(
            {
                "id": chore_id, 
                "chore": chore_name, 
                "value": value, 
                "status": "Pending",
                "timestamp": timestamp
            }
        )
        if save_data_to_github(st.session_state.data, st.session_state.file_sha):
            st.session_state.submit_success = f"Submitted '{chore_name}' for {who}! Waiting for approval."
            del st.session_state.data
    else:
        st.session_state.submit_error = "Please ensure the chore has a description and a value greater than $0."


def handle_approval(person, chore_id, approved=True):
    for chore in st.session_state.data["people"][person]["history"]:
        if chore.get("id") == chore_id:
            if approved:
                chore["status"] = "Approved"
                st.session_state.data["people"][person]["balance"] += chore["value"]
            else:
                chore["status"] = "Denied"
            break
    save_data_to_github(st.session_state.data, st.session_state.file_sha)


def handle_deletion(person, item_id):
    history_list = st.session_state.data["people"][person]["history"]
    for item in history_list:
        if item.get("id", item["chore"]) == item_id:
            if item.get("status") == "Approved":
                st.session_state.data["people"][person]["balance"] -= item["value"]
            history_list.remove(item)
            break
    save_data_to_github(st.session_state.data, st.session_state.file_sha)


# --- DISPLAY STATUS ALERTS ---
if "submit_success" in st.session_state:
    st.success(st.session_state.submit_success)
    del st.session_state.submit_success

if "submit_error" in st.session_state:
    st.error(st.session_state.submit_error)
    del st.session_state.submit_error


# --- SIDEBAR: AUTHENTICATION & MANAGEMENT ---
st.sidebar.header("🔒 Admin Portal")
if not st.session_state.is_admin:
    with st.sidebar.expander("🔑 Admin Login"):
        pwd_input = st.text_input("Enter Password:", type="password")
        if st.button("Login"):
            if pwd_input == st.secrets["ADMIN_PASSWORD"]:
                st.session_state.is_admin = True
                st.rerun()
            else:
                st.error("Incorrect password.")
else:
    st.sidebar.success("🔓 Logged in as Admin")
    if st.sidebar.button("Log Out"):
        st.session_state.is_admin = False
        st.rerun()

st.sidebar.markdown("---")

if st.session_state.is_admin:
    st.sidebar.header("👤 Manage Family")
    new_person = st.sidebar.text_input("Add New Person:").strip()
    if st.sidebar.button("Add Person"):
        if new_person and new_person not in all_people:
            st.session_state.data["people"][new_person] = {"balance": 0.0, "history": []}
            if save_data_to_github(st.session_state.data, st.session_state.file_sha):
                st.sidebar.success(f"Added {new_person}!")
                del st.session_state.data
                st.rerun()
        elif new_person in all_people:
            st.sidebar.warning("Name already exists.")


# --- SECTION 1: LOG A CHORE ---
st.header("💰 Log a Chore")
if all_people:
    who = st.selectbox("Who did it?", all_people)
    
    # 💡 FIX 1: Show prices directly inside the dropdown selection list
    dropdown_options = []
    for chore, price in PRESET_CHORES.items():
        if chore == "➕ Custom Chore...":
            dropdown_options.append(chore)
        else:
            dropdown_options.append(f"{chore} — ${price:.2f}")

    selected_display = st.selectbox(
        "Select or search a preset job:", 
        options=dropdown_options
    )
    
    # Extract the original dictionary key back out to handle the logic properly
    if " — $" in selected_display:
        selected_preset = selected_display.split(" — $")[0]
    else:
        selected_preset = selected_display
    
    col1, col2 = st.columns([2, 1])
    if selected_preset == "➕ Custom Chore..." or selected_preset is None:
        with col1:
            chore_name = st.text_input("Chore Description:", placeholder="e.g., Cleaned windows", key="custom_chore_input")
        with col2:
            value = st.number_input("Payout ($)", min_value=0.0, value=0.00, step=0.50, format="%.2f", key="custom_payout_input")
    else:
        chore_name = selected_preset
        default_val = PRESET_CHORES[selected_preset]
        value = default_val
        
        # 💡 FIX 2: Aligned the text layout vertically so they sit on the same baseline
        with col1:
            st.markdown("**Chore Description:**")
            st.caption("") # Acts as a clean visual vertical spacer
            st.write(chore_name)
        with col2:
            st.markdown("**Payout ($):**")
            st.markdown(f"### ${value:.2f}")
            
        st.write("")


# --- SECTION 2: BALANCES ---
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
                if st.session_state.is_admin:
                    if st.button(f"Pay {person}", key=f"pay_{person}"):
                        current_balance = info["balance"]
                        timestamp_payout = datetime.now().strftime("%m/%d/%y at %I:%M %p")
                        
                        # 1. Flip active approved chores to Paid
                        for c in st.session_state.data["people"][person]["history"]:
                            if c.get("status") == "Approved":
                                c["status"] = "Paid"
                                c["paid_timestamp"] = timestamp_payout
                        
                        # 2. Inject the permanent, protected Payout Receipt line item
                        st.session_state.data["people"][person]["history"].append({
                            "id": f"pay_{int(time.time())}",
                            "chore": "💰 Paid Out Total Balance",
                            "value": current_balance,
                            "status": "Payout",
                            "timestamp": timestamp_payout
                        })
                        
                        # 3. Reset running tab balance
                        st.session_state.data["people"][person]["balance"] = 0.0
                        
                        save_data_to_github(st.session_state.data, st.session_state.file_sha)
                        st.toast(f"Paid {person}!")
                        del st.session_state.data
                        st.rerun()
                else:
                    st.write("⏳ Awaiting Payment")
            else:
                st.write("✨ Settled")

        if info["history"]:
            # 🔍 Separate chores from receipts using list comprehensions
            all_items = info.get("history", [])
            chore_items = [item for item in all_items if item.get("status") != "Payout"]
            payout_items = [item for item in all_items if item.get("status") == "Payout"]

            # --- EXPANDER 1: CHORE HISTORY ---
            with st.expander(f"📋 View {person}'s Chore History"):
                if chore_items:
                    for item in reversed(chore_items):
                        status = item.get("status", "Approved")
                        time_stamp = item.get("timestamp", "Prior Entry")
                        
                        if status == "Pending":
                            status_str = "⏳ Pending"
                        elif status == "Approved":
                            status_str = "🟢 Approved"
                        elif status == "Denied":
                            status_str = "❌ Denied"
                        else:
                            payout_time = item.get("paid_timestamp", "")
                            status_str = f"✅ Paid {payout_time}".strip()
                            
                        h_col1, h_col2 = st.columns([4, 1])
                        with h_col1:
                            st.write(f"**{item['chore']}** — ${item['value']:.2f}")
                            st.caption(f"Logged: {time_stamp} | Status: {status_str}")
                        with h_col2:
                            if st.session_state.is_admin:
                                item_id = item.get("id", item['chore'])
                                st.button("🗑️", key=f"del_{item_id}_{person}", help="Permanently Delete Entry", on_click=handle_deletion, args=(person, item_id))
                else:
                    st.write("No chore history to show right now.")

            # --- EXPANDER 2: PAYMENT HISTORY ---
            with st.expander(f"💵 View {person}'s Payment History"):
                if payout_items:
                    for item in reversed(payout_items):
                        h_col1, h_col2 = st.columns([4, 1])
                        with h_col1:
                            # Clean receipt format showing the amount and exact payout date
                            st.write(f"**{item['chore']}** — ${item['value']:.2f}")
                            st.caption(f"Cleared On: {item['timestamp']}")
                        with h_col2:
                            if st.session_state.is_admin:
                                item_id = item.get("id")
                                # Allows you to manually strike down a wrong payment entry if needed
                                st.button("🗑️", key=f"del_receipt_{item_id}_{person}", help="Delete Payment Receipt Record", on_click=handle_deletion, args=(person, item_id))
                else:
                    st.write("✨ No payments have been logged yet.")
else:
    st.write("No family profiles logged yet.")


# --- SECTION 3: APPROVAL QUEUE (ADMIN RESTRICTED) ---
if st.session_state.is_admin:
    st.markdown("---")
    st.header("🛡️ Admin Approvals")
    pending_chores = []

    for person, info in data["people"].items():
        for chore in info.get("history", []):
            if chore.get("status") == "Pending":
                pending_chores.append((person, chore))

    if pending_chores:
        for person, chore in pending_chores:
            c_col1, c_col2, c_col3 = st.columns([2, 1, 1.5])
            with c_col1:
                st.write(f"**{person}**: {chore['chore']}")
                st.caption(f"Submitted: {chore.get('timestamp', 'N/A')}")
            with c_col2:
                st.write(f"${chore['value']:.2f}")
            with c_col3:
                btn_app, btn_deny = st.columns(2)
                with btn_app:
                    st.button("👍", key=f"app_{chore['id']}", help="Approve", on_click=handle_approval, args=(person, chore['id'], True))
                with btn_deny:
                    st.button("👎", key=f"deny_{chore['id']}", help="Deny", on_click=handle_approval, args=(person, chore['id'], False))
    else:
        st.write("✅ No chores waiting for approval right now.")
