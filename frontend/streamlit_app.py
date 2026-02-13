import streamlit as st
import requests
import json
import uuid
import os

# [CHANGE 1a] Move this to the TOP of the file (after imports/config)
def fetch_current_user():
    """Updates session state with the logged-in user's real ID."""
    try:
        if not st.session_state.token:
            return

        # Decode JWT (Middle part)
        token_parts = st.session_state.token.split('.')
        if len(token_parts) > 1:
            payload_part = token_parts[1] + '=' * (-len(token_parts[1]) % 4)
            import base64
            payload = json.loads(base64.b64decode(payload_part).decode('utf-8'))

            # Get ID (Standard JWT claims usually have 'sub' or 'id')
            real_id = payload.get("id") or payload.get("sub")

            if real_id:
                # Handle "CUST-001" vs 121 format
                if str(real_id).isdigit():
                     st.session_state.customer_id = int(real_id)
                st.toast(f"✅ Verified Identity: {real_id}")

    except Exception as e:
        # Don't break the app, just log
        print(f"User ID Error: {e}")

# [CHANGE] Update this function to RETURN the list instead of setting state directly
def fetch_user_conversations():
    """Fetches list of all conversations for the sidebar."""
    try:
        if not st.session_state.token:
            return []

        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        response = requests.get(
            f"{API_BASE_URL}/customers/{st.session_state.customer_id}/conversations",
            headers=headers,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            conversations = data.get("conversations", [])
            # Sort by last_updated (Newest first)
            conversations.sort(key=lambda x: x.get("last_updated", ""), reverse=True)
            return conversations
        return []

    except Exception as e:
        st.error(f"Failed to fetch chats: {e}")
        return []

# [CHANGE 1b] Add this function to find the REAL conversation
def restore_latest_conversation():
    """Finds the user's most recent conversation and restores it."""
    try:
        if not st.session_state.token:
            return

        headers = {"Authorization": f"Bearer {st.session_state.token}"}

        # 1. Ask API: "What conversations does this user have?"
        response = requests.get(
            f"{API_BASE_URL}/customers/{st.session_state.customer_id}/conversations",
            headers=headers,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            conversations = data.get("conversations", [])

            if conversations:
                # 2. Pick the most recent one (Sort by last_updated)
                # Assuming backend sends ISO format dates, string sort works for ISO
                conversations.sort(key=lambda x: x.get("last_updated", ""), reverse=True)

                last_conv = conversations[0]
                st.session_state.conversation_id = last_conv["conversation_id"]
                st.toast(f"📂 Restored Chat #{st.session_state.conversation_id}")
            else:
                # 3. If no history, generate a NEW persistent ID
                st.session_state.conversation_id = int(str(uuid.uuid4().int)[:6])
                st.toast("🆕 Starting New Conversation")

    except Exception as e:
        st.error(f"Failed to restore session: {e}")



def load_chat_history():
    """Fetches chat history from the backend and populates session state."""
    try:
        if not st.session_state.token or not st.session_state.conversation_id:
            return

        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        # Use the existing endpoint in messages.py
        response = requests.get(
            f"{API_BASE_URL}/conversations/{st.session_state.conversation_id}/history",
            headers=headers,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            history = data.get("history", [])

            # Clear and rebuild Streamlit chat
            st.session_state.messages = []
            for msg in history:
                # Map backend roles to streamlit roles
                role = "user" if msg["role"] == "user" else "assistant"
                st.session_state.messages.append({
                    "role": role,
                    "content": msg["content"]
                })

    except Exception as e:
        st.error(f"Failed to load history: {e}")

# ============================================================
# CONFIGURATION
# ============================================================
# Docker: "http://web:8000/api/v1" | Local: "http://localhost:8000/api/v1"
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")

PAGE_TITLE = "FCA Compliant AI Banking Agent"
PAGE_ICON = "🏦"

st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="wide")

# ============================================================
# SESSION STATE SETUP
# ============================================================
if "token" not in st.session_state:
    st.session_state.token = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "customer_id" not in st.session_state:
    st.session_state.customer_id = 121
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "debug_info" not in st.session_state:
    st.session_state.debug_info = {}



# Add this function BEFORE login()
def fetch_active_conversation():
    """
    Enforces SINGLE conversation per user.
    1. Fetches existing conversations.
    2. If found, picks the most recent one.
    3. If none, generates a NEW one and sets it.
    """
    try:
        headers = {"Authorization": f"Bearer {st.session_state.token}"}

        # 1. Get all conversations
        response = requests.get(
            f"{API_BASE_URL}/customers/{st.session_state.customer_id}/conversations",
            headers=headers,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            conversations = data.get("conversations", [])

            if conversations:
                # Sort by last_updated (Newest first) to stick to the active thread
                conversations.sort(key=lambda x: x.get("last_updated", ""), reverse=True)
                active_id = conversations[0]["conversation_id"]
                st.session_state.conversation_id = active_id
                st.toast(f"📂 Resumed Conversation #{active_id}")
            else:
                # Create NEW ID only if none exist
                new_id = int(str(uuid.uuid4().int)[:6])
                st.session_state.conversation_id = new_id
                st.toast(f"🆕 Started New Conversation #{new_id}")

    except Exception as e:
        st.error(f"Failed to sync conversation: {e}")

# ============================================================
# AUTHENTICATION FUNCTIONS
# ============================================================
def login(username, password):
    """Exchanges credentials for a JWT token."""
    try:
        # [FIX] We must strip '/api/v1' because the Auth endpoint is at the root level (/auth/login)
        # 1. Get the root URL (http://web:8000 or http://localhost:8000)
        root_url = API_BASE_URL.replace("/api/v1", "")

        # 2. Attempt Login
        response = requests.post(
            f"{root_url}/auth/login",  # <--- Use root_url, NOT API_BASE_URL
            data={"username": username, "password": password},
            timeout=5
        )

        # 3. Handle Success
        if response.status_code == 200:
            data = response.json()
            st.session_state.token = data.get("access_token")
            # [FIX] Update Customer ID from Token immediately
            fetch_current_user()



            # [CHANGE] Auto-select the newest chat
            fetch_active_conversation()


            #  Load history immediately after login
            load_chat_history()
            st.success("Login Successful! 🔓")
            st.rerun()
        else:
            st.error(f"Login Failed: {response.text}")

    except Exception as e:
        st.error(f"Connection Error: {e}")

def logout():
    """Clear session state."""
    st.session_state.token = None
    st.session_state.messages = []
    st.session_state.customer_id = None # [FIX] Clear the ID
    st.session_state.conversation_id = None # [FIX] Clear the Chat ID
    st.rerun()

# ============================================================
# VIEW 1: LOGIN SCREEN
# ============================================================
if not st.session_state.token:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.title(f"{PAGE_ICON} Agent Login")
        st.markdown("Please sign in to access the secure banking terminal.")

        with st.form("login_form"):
            # Default test credentials pre-filled for convenience
            uid = st.text_input("Email / User ID", value="yellis@example.org")
            pwd = st.text_input("Password", type="password", value="password123")

            submitted = st.form_submit_button("Secure Login 🔒")

            if submitted:
                if not uid or not pwd:
                    st.warning("Please enter both ID and Password.")
                else:
                    login(uid, pwd)

        st.info("💡 Default Test Creds: `james.bond@mi6.gov.uk` / `password123`")

    # Stop execution here if not logged in
    st.stop()

# ============================================================
# VIEW 2: MAIN APP (Only visible if logged in)
# ============================================================

# --- SIDEBAR: NAVIGATION & DEBUG ---
with st.sidebar:
    st.header(f"{PAGE_ICON} History")

    # Add Visible Debug Info
    st.divider()
    st.markdown("### 🕵️ Debug Info")
    st.write(f"**Logged-in ID:** `{st.session_state.customer_id}`")
    st.write(f"**Conversation ID:** `{st.session_state.conversation_id}`")
    st.divider()

    # Check if we have an active conversation
    if st.session_state.conversation_id:
        st.info(f"💬 Active Chat ID: **{st.session_state.conversation_id}**")

        # "Clear History" mimics starting over, but maintains the single-thread concept
        if st.button("🗑️ Clear History (Start Over)", use_container_width=True):
            # Generate new ID to start fresh
            st.session_state.conversation_id = int(str(uuid.uuid4().int)[:6])
            st.session_state.messages = []
            st.rerun()

    else:
        st.warning("No active conversation.")

    st.divider()

    # Logout
    if st.button("🚪 Logout", use_container_width=True):
        logout()

# --- CHAT INTERFACE ---
st.title(f"{PAGE_ICON} AI Support Agent")
st.caption(f"Logged in as: **{st.session_state.customer_id}** | Protected by Lakera & Presidio")

# Display History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat Input
if prompt := st.chat_input("How can I help you today?"):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call Backend
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("⏳ *Thinking...*")

        try:
            headers = {
                "Authorization": f"Bearer {st.session_state.token}",
                "Content-Type": "application/json"
            }
            payload = {
                "message": prompt,
                "customer_id": st.session_state.customer_id,
                "conversation_id": st.session_state.conversation_id
            }


            response = requests.post(
                f"{API_BASE_URL}/messages/process",
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                bot_reply = data.get("response", "Error: No response")

                new_id = data.get("conversation_id")
                if new_id and new_id != st.session_state.conversation_id:
                     st.session_state.conversation_id = new_id
                message_placeholder.markdown(bot_reply)
                st.session_state.messages.append({"role": "assistant", "content": bot_reply})

                st.session_state.debug_info = data
                st.rerun() # Update sidebar
            elif response.status_code == 401:
                st.error("Session Expired. Please logout and login again.")
            else:
                st.error(f"Error {response.status_code}: {response.text}")

        except Exception as e:
            st.error(f"Connection Error: {e}")
