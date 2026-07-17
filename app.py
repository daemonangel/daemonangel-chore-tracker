import base64
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
    return response.status_code in [200, 201]


# --- INITIALIZE DATA & SESSION STATE ---
if "data" not in st.session_state or "file_sha" not in st.session_state:
    data, file_sha = load_data_from_github()
    st.session_state.data = data
    st.session_state.file_sha = file_sha

# Track login state persistently across user clicks
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

data = st.session_state.data
file_sha = st.session_state.file_sha
all_people = list(data["people"].keys())

st.title("🧹 Daemonangel Chore Tracker")

# --- ACTION HANDLERS ---
def handle_submission(who, chore_name, value):
    if chore_name and chore_name != "➕ Custom Chore..." and value > 0:
        chore_id = str(int(time.time()))
        st.session_state.data["people"][who]["history"].append(
            {"id": chore_id, "chore": chore_name, "value": value, "status": "Pending"}
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
    #del st.session_state.data
    st.rerun()


def handle_deletion(person, item_id):
    history_list = st.session_state.data["people"][person]["history"]
    for item in history_list:
        if item.get("id", item["chore"]) == item_id:
            if item.get("status") == "Approved":
                st.session_state.data["people"][person]["balance"] -= item["value"]
            history_list.remove(item)
            break
    save_data_to_github(st.session_state.data, st.session_state.file_sha)
    #del st.session_state.data
    st.rerun()


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

# Only show "Manage Family" profile creations if authenticated
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
    
    selected_preset = st.pills(
        "Select a preset job:", 
        options=list(PRESET_CHORES.keys()), 
        default="🧹 Vacuuming"
    )
    
    col1, col2 = st.columns([2, 1])
    with col1:
        if selected_preset == "➕ Custom Chore..." or selected_preset is None:
            chore_name = st.text_input("Chore Description:", placeholder="e.g., Cleaned windows", key="custom_chore_input")
            default_val = 0.00
            is_disabled = False
        else:
            chore_name = selected_preset
            default_val = PRESET_CHORES[selected_preset]
            # 💡 FIX: We use a dynamic key based on the selected preset name so Streamlit updates instantly
            st.text_input("Chore Description:", value=chore_name, disabled=True, key=f"disabled_{selected_preset}")
            is_disabled = True
            
    with col2:
        # 💡 FIX: We also make this key dynamic so the dollar value snaps to the new price instantly
        value = st.number_input(
            "Payout ($)", min_value=0.0, value=default_val, step=0.50, format="%.2f", disabled=is_disabled, key=f"payout_{selected_preset}"
        )

    st.button(
        "Submit for Approval", 
        type="primary", 
        on_click=handle_submission, 
        args=(who, chore_name, value)
    )
else:
    st.info("👈 An Admin needs to log in and add a family profile to begin!")

st.markdown("---")


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
            # Pay buttons now strictly check if you are logged in as admin
            if info["balance"] > 0:
                if st.session_state.is_admin:
                    if st.button(f"Pay {person}", key=f"pay_{person}"):
                        st.session_state.data["people"][person]["balance"] = 0.0
                        for c in st.session_state.data["people"][person]["history"]:
                            if c.get("status") == "Approved":
                                c["status"] = "Paid"
                        save_data_to_github(st.session_state.data, st.session_state.file_sha)
                        st.toast(f"Paid {person}!")
                        del st.session_state.data
                        st.rerun()
                else:
                    st.write("⏳ Awaiting Payment")
            else:
                st.write("✨ Settled")

        if info["history"]:
            with st.expander(f"View {person}'s History"):
                for item in reversed(info.get("history", [])):
                    status = item.get("status", "Approved")
                    
                    if status == "Pending":
                        status_str = "⏳ Pending"
                    elif status == "Approved":
                        status_str = "🟢 Approved"
                    elif status == "Denied":
                        status_str = "❌ Denied"
                    else:
                        status_str = "✅ Paid"
                        
                    if st.session_state.is_admin:
                        h_col1, h_col2 = st.columns([4, 1])
                        with h_col1:
                            st.write(f"- {item['chore']}: **${item['value']:.2f}** ({status_str})")
                        with h_col2:
                            item_id = item.get("id", item['chore'])
                            st.button("🗑️", key=f"del_{item_id}_{person}", help="Permanently Delete Entry", on_click=handle_deletion, args=(person, item_id))
                    else:
                        # Non-admins just see clean text line without the trash icon options
                        st.write(f"- {item['chore']}: **${item['value']:.2f}** ({status_str})")
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
