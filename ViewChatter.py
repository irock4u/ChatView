import streamlit as st
import requests
import httpx
from datetime import datetime, timezone
from streamlit_js_eval import streamlit_js_eval
from streamlit_autorefresh import st_autorefresh

# -------------------- Config --------------------
st.set_page_config(page_title="Personal Chat View", layout="centered")

SUPABASE_URL = st.secrets["SUPABASE_URL"]  # e.g., https://xyz.supabase.co
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]  # service-role or anon key

CHAT_TABLE = "chat_messages"
VISIT_TABLE = "page_visits"
STORAGE_BUCKET = "chat_files"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# -------------------- Logger --------------------
def log(name, data):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] === {name} ===")
    print(data)
    print(f"[{timestamp}] === END {name} ===\n")

# --- Step 1: Fetch the user's real IP only once per refresh ---
# --- Step 1: Fetch the user's real IP (only once) ---
if "user_ip" not in st.session_state:
    st.session_state.user_ip = None  # initialize

ip_data = streamlit_js_eval(
    js_expressions="fetch('https://api.ipify.org?format=json').then(r => r.json())",
    key="real_ip_fetch"  # use a stable key, not timestamp
)

if ip_data and "ip" in ip_data and st.session_state.user_ip is None:
    st.session_state.user_ip = ip_data["ip"]
    log("Browser IP fetch", ip_data["ip"])

# convenience getter
def get_user_ip():
    return st.session_state.get("user_ip")

log("IP fetch", get_user_ip())

def get_ip_location():
    result = {}
    myips=get_user_ip()
    try:
        result["MyIp"] = myips
        r1 = requests.get("https://ipapi.co/json/", timeout=10, verify=False)
        if r1.status_code == 200 and r1.content.strip():
            result["ipapi"] = r1.json()
        else:
            result["ipapi"] = {"error": f"Failed with status {r1.status_code}"}

    except Exception as e:
        result["ipapi"] = {"error": str(e)}

    try:
        r2 = requests.get("http://ip-api.com/json/", timeout=10)
        if r2.status_code == 200 and r2.content.strip():
            result["ipapi2"] = r2.json()
        else:
            result["ipapi2"] = {"error": f"Failed with status {r2.status_code}"}
    except Exception as e:
        result["ipapi2"] = {"error": str(e)}

    try:
        r1 = requests.get(f"https://ipapi.co/{myips}/json/", timeout=10, verify=False)
        if r1.status_code == 200 and r1.content.strip():
            result["Realipapi"] = r1.json()
        else:
            result["Realipapi"] = {"error": f"Failed with status {r1.status_code}"}
    except Exception as e:
        result["Realipapi"] = {"error": str(e)}

    try:
        r2 = requests.get(f"http://ip-api.com/json/{myips}", timeout=10)
        if r2.status_code == 200 and r2.content.strip():
            result["Realipapi2"] = r2.json()
        else:
            result["Realipapi2"] = {"error": f"Failed with status {r2.status_code}"}
    except Exception as e:
        result["Realipapi2"] = {"error": str(e)}

    return result
# --- Step 3: Combine ---
ip_location = get_ip_location()
log("IP fetch", ip_location)

# -------------------- Browser Geolocation --------------------
def get_browser_geolocation(timeout_ms=10000):
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
            key="browser_geo_fetch"
        )
        payload = {"method": "geolocation", "server_time_utc": datetime.now(timezone.utc).isoformat()}
        if coords:
            payload["coords"] = coords
            payload["status"] = "success"
        else:
            payload["status"] = "no_data_or_denied"
    except Exception as e:
        payload = {"method": "geolocation", "status": "error", "error": str(e),
                   "server_time_utc": datetime.now(timezone.utc).isoformat()}
    return payload

# -------------------- Consent --------------------
st.title("Welcome to Personal Chat View!")
if "consent_given" not in st.session_state:
    st.session_state.consent_given = False

if not st.session_state.consent_given:
    if st.button("Start Chat"):
        st.session_state.consent_given = True

# -------------------- Log Page Visit --------------------
if "visit_logged" not in st.session_state:
    current_ip = get_ip_location()
    current_geo = "Later" #get_browser_geolocation()
    visit_payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ip_location": current_ip,
        "geo_location": current_geo
    }
    visit_url = f"{SUPABASE_URL}/rest/v1/{VISIT_TABLE}"
    try:
        with httpx.Client(verify=False) as client:
            client.post(visit_url, headers=HEADERS, json=visit_payload)
        st.session_state.visit_logged = True  # ensure only logged once per session   
    except Exception as e:
        st.warning(f"Failed to log page visit: {e}")   
        
    current_ip = get_ip_location()
    current_geo = get_browser_geolocation()
    visit_payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ip_location": current_ip,
        "geo_location": current_geo
    }
    visit_url = f"{SUPABASE_URL}/rest/v1/{VISIT_TABLE}"
    try:
        with httpx.Client(verify=False) as client:
            client.post(visit_url, headers=HEADERS, json=visit_payload)
        st.session_state.visit_logged = True  # ensure only logged once per session   
    except Exception as e:
        st.warning(f"Failed to log page visit: {e}")   

# -------------------- Fetch Chat --------------------
def fetch_chat():
    url = f"{SUPABASE_URL}/rest/v1/{CHAT_TABLE}?select=*&order=created_at.asc"
    try:
        with httpx.Client(verify=False) as client:
            r = client.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        log("Fetch chat failed", str(e))
        return []

st.session_state.messages = fetch_chat()

# -------------------- Chat Interface --------------------
if st.session_state.consent_given:
    st.subheader("Chat Interface")
    username = st.text_input("Enter your name:", key="username_input")

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
                # get fresh IP + geolocation per message
                msg_ip = get_ip_location()
                msg_geo = get_browser_geolocation()

                attachment_url = None
                attachment_name = None
                attachment_type = None

                if attachment:
                    file_bytes = attachment.read()
                    file_name = f"{datetime.now().timestamp()}_{attachment.name}"
                    storage_url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{file_name}"
                    with httpx.Client(verify=False) as client:
                        r = client.put(storage_url, headers={"Authorization": f"Bearer {SUPABASE_KEY}"},
                                       content=file_bytes)
                        if r.status_code in (200, 201):
                            attachment_url = f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{file_name}"
                    attachment_name = attachment.name
                    attachment_type = attachment.type

                new_msg = {
                    "username": username,
                    "message": user_input,
                    "attachment_name": attachment_name,
                    "attachment_url": attachment_url,
                    "attachment_type": attachment_type,
                    "ip_location": msg_ip,
                    "geo_location": msg_geo
                }

                insert_url = f"{SUPABASE_URL}/rest/v1/{CHAT_TABLE}"
                with httpx.Client(verify=False) as client:
                    client.post(insert_url, headers=HEADERS, json=new_msg)

                st.session_state.messages.append(new_msg)

    # -------------------- Display Messages --------------------
    st.markdown("---")
    for msg in st.session_state.messages:
        user = msg.get("username", "Unknown")
        text = msg.get("message", "")
        timestamp = msg.get("created_at", datetime.now(timezone.utc).isoformat())
        attachment_info = ""
        if msg.get("attachment_name") and msg.get("attachment_url"):
            attachment_info = f"📎 [{msg['attachment_name']}]({msg['attachment_url']})"
        st.markdown(f"**{user} [{timestamp}]:** {text} {attachment_info}")

    # -------------------- Auto-refresh --------------------
    st_autorefresh(interval=5000, key="chat_refresh")
