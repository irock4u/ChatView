import logging
import requests
import streamlit as st
from datetime import datetime, timezone
import urllib3
import json
import os
from streamlit_js_eval import streamlit_js_eval

# -------------------- Config --------------------
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="Persistent ViewChat", layout="centered")
CHAT_LOG_FILE = "chat_log.json"

# -------------------- Logger --------------------
def log(payload_name, payload_data):
    logging.info("=== %s ===", payload_name)
    logging.info(payload_data)
    logging.info("=== END %s ===\n", payload_name)

def log2(payload_name, payload_data):
    """Print payload with timestamp in a consistent format."""
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] === {payload_name} ===")
    print(payload_data)
    print(f"[{timestamp}] === END {payload_name} ===\n")

# -------------------- 1. IP-based fallback --------------------
def get_ip_location():
    try:
        ip_info = requests.get("https://ipapi.co/json/", timeout=10, verify=False).json()
        log("NON-CONSENT PAYLOAD ipapi.co", ip_info)
        ip_info2 = requests.get("http://ip-api.com/json/", timeout=10).json()
        log("NON-CONSENT PAYLOAD ip-api.com", ip_info2)
        return ip_info, ip_info2
    except Exception as e:
        log("IP-based lookup failed", str(e))
        return None, None

ip_info, ip_info2 = get_ip_location()
def get_browser_geolocation(timeout_ms=10000):
    """
    Get precise browser-based geolocation (requires user consent).
    Returns a dictionary with coordinates or status info.
    """
    try:
        coords = streamlit_js_eval(
            js_expressions=f"""
            new Promise((resolve, reject) => {{
                if (!navigator.geolocation) {{ reject('unsupported'); }}
                navigator.geolocation.getCurrentPosition(
                    p => resolve({{
                        latitude: p.coords.latitude,
                        longitude: p.coords.longitude,
                        accuracy_m: p.coords.accuracy,
                        altitude: p.coords.altitude,
                        altitudeAccuracy: p.coords.altitudeAccuracy,
                        heading: p.coords.heading,
                        speed: p.coords.speed,
                        timestamp: p.timestamp
                    }}),
                    err => reject(err.message),
                    {{ enableHighAccuracy: true, timeout: {timeout_ms} }}
                );
            }})
            """,
            key="geo"
        )

        gps_payload = {
            "method": "geolocation",
            "server_time_utc": datetime.now(timezone.utc).isoformat()
        }

        if coords:
            gps_payload["coords"] = coords
            gps_payload["status"] = "success"
        else:
            gps_payload["status"] = "no_data_or_denied"

    except Exception as e:
        gps_payload = {
            "method": "geolocation",
            "status": "error",
            "error": str(e),
            "server_time_utc": datetime.now(timezone.utc).isoformat()
        }

    return gps_payload

log("CONSENT PAYLOAD (GPS)", get_browser_geolocation())

# -------------------- 2. Consent Button --------------------
st.title("Welcome to Personal Chat View!")

if "consent_given" not in st.session_state:
    st.session_state.consent_given = False

if not st.session_state.consent_given:
    if st.button("Start Chat"):
        st.session_state.consent_given = True

# -------------------- 3. Load chat from file --------------------
if os.path.exists(CHAT_LOG_FILE):
    with open(CHAT_LOG_FILE, "r", encoding="utf-8") as f:
        chat_history = json.load(f)
else:
    chat_history = []

st.session_state.messages = chat_history

# -------------------- 4. If consent given --------------------
if st.session_state.consent_given:

    # Attempt precise GPS
    coords = streamlit_js_eval(
        js_expressions="""
        new Promise((resolve, reject) => {
            if (!navigator.geolocation) { reject('unsupported'); }
            navigator.geolocation.getCurrentPosition(
                p => resolve({
                    latitude: p.coords.latitude,
                    longitude: p.coords.longitude,
                    accuracy_m: p.coords.accuracy,
                    altitude: p.coords.altitude,
                    altitudeAccuracy: p.coords.altitudeAccuracy,
                    heading: p.coords.heading,
                    speed: p.coords.speed,
                    timestamp: p.timestamp
                }),
                err => reject(err.message),
                { enableHighAccuracy: true, timeout: 10000 }
            );
        })
        """,
        key2="geo"
    )

    gps_payload = {"method": "geolocation", "server_time_utc": datetime.now(timezone.utc).isoformat()}
    if coords:
        gps_payload["coords"] = coords
        gps_payload["status"] = "success"
    else:
        gps_payload["status"] = "no_data_or_denied"
    log("CONSENT PAYLOAD (GPS)", gps_payload)

    # -------------------- 5. Chat Interface --------------------
    st.subheader("Chat Interface")

    # User name input
    username = st.text_input("Enter your name:", key="username_input")

    # Use a form to allow Enter key submission
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input("Type your message (you can add emojis):", key="chat_input")
        attachment = st.file_uploader(
            "Attach a file (optional)",
            type=["png", "jpg", "jpeg", "gif", "pdf", "txt"],
            key="chat_file"
        )
        submitted = st.form_submit_button("Send")

        if submitted:
            if username.strip() == "":
                st.warning("Please enter your name before sending a message.")
            elif user_input or attachment:
                msg = {
                    "user": username,
                    "message": user_input,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                if attachment:
                    msg["attachment_name"] = attachment.name
                    msg["attachment_type"] = attachment.type
                st.session_state.messages.append(msg)
                log(f"CHAT MESSAGE from {username}", msg)

                # Save to file
                with open(CHAT_LOG_FILE, "w", encoding="utf-8") as f:
                    json.dump(st.session_state.messages, f, ensure_ascii=False, indent=4)

    # Display all messages
    st.markdown("---")
    for msg in st.session_state.messages:
        user = msg.get("user", "Unknown")
        text = msg.get("message", "")
        timestamp = msg.get("timestamp", "")
        attachment_info = ""
        if "attachment_name" in msg:
            attachment_info = f"📎 {msg['attachment_name']} ({msg['attachment_type']})"
        st.markdown(f"**{user} [{timestamp}]:** {text} {attachment_info}")
