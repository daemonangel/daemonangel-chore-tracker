import base64
import json
import requests
import streamlit as st

# --- CONFIG ---
st.set_page_config(page_title="Chore Tracker", page_icon="🧹", layout="centered")

# --- GITHUB API HELPER FUNCTIONS ---
TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = st.secrets["REPO_NAME"]
PATH = st.secrets["FILE_PATH"]
URL = f"https://api.github.com/repos/{REPO}/contents/{PATH}"
HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}


def load_data_from_github():
    """Fetches the JSON file from GitHub and extracts its content and sha."""
    response = requests.get(URL, headers=HEADERS)
    if response.status_code == 200:
        file_data = response.json()
        # GitHub returns contents in base64 encoding
        content = base64.b64decode(file_data["content"]).decode("utf-8")
        return json.loads(content), file_data["sha"]
    elif response.status_code == 404:
        # File doesn't exist yet, return fresh structure
        return {"people": {}}, None
    else:
        st.error(f"Failed to fetch data from GitHub: {response.text}")
        return {"people": {}}, None


def save_data_to_github(data, sha=None):
    """Commits the updated JSON file structure back to the GitHub repo."""
    content_str = json.dumps(data, indent=4)
    content_bytes = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

    payload = {"message": "Update chore data via Streamlit", "content": content_bytes}
    if sha:
        payload["sha"] = sha

    response = requests.put(URL, headers=HEADERS, json=payload)
    if response.status_code in [200, 201]:
        return True
    else:
        st.error(f"Failed to save data to GitHub: {response.text}")
        return False


# --- INITIALIZE DATA ---
data, file_sha = load_data_from_github()

st.title("🧹 Daemonangel Chore Tracker")
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
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col1:
        who = st.selectbox("Who did it?", all_people)
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
            if save_data_to_github(data, file_sha):
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

        # Optional Expandable History
        if info["history"]:
            with st.expander(f"View {person}'s History"):
                for item in reversed(info["history"]):
                    status = "✅ Paid" if item["paid"] else "⏳ Unpaid"
                    st.write(f"- {item['chore']}: **${item['value']:.2f}** ({status})")
else:
    st.write("No family profiles logged yet.")
