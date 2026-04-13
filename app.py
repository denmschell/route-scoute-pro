import streamlit as st
import requests
import pandas as pd
import json
import time

# Page Config
st.set_page_config(page_title="Route Scoute Pro", layout="wide")
st.title("Route Scoute Pro 🚗")

# Securely load API Keys
RAPID_KEY = st.secrets["RAPID_API_KEY"]
MAPBOX_KEY = st.secrets["MAPBOX_API_KEY"]

with st.form("input_form"):
    st.write("### Zip Code Search")
    zip_input = st.text_input("Enter Zip Codes (separate by commas)", value="")
    
    col1, col2, col3 = st.columns(3)
    with col1: date_1 = st.date_input("Date Option 1", value=None)
    with col2: date_2 = st.date_input("Date Option 2", value=None)
    with col3: date_3 = st.date_input("Date Option 3", value=None)
    
    submit = st.form_submit_button("Generate Full Data Route")

if submit:
    zip_list = [z.strip() for z in zip_input.split(",") if z.strip()]
    selected_dates = [d.strftime("%Y-%m-%d") for d in [date_1, date_2, date_3] if d]
            
    if not zip_list:
        st.error("Please enter at least one Zip Code.")
    else:
        with st.spinner("Step 1: Searching... Step 2: Fetching Times..."):
            try:
                houses = []
                valid_coords = []
                system_errors = []

                for zcode in zip_list:
                    # STEP 1: Search for IDs
                    search_url = "https://real-estate101.p.rapidapi.com/api/search"
                    headers = {"x-rapidapi-host": "real-estate101.p.rapidapi.com", "x-rapidapi-key": RAPID_KEY}
                    search_resp = requests.get(search_url, headers=headers, params={"location": zcode, "isOpenHousesOnly": "true"})
                    
                    if search_resp.status_code == 200:
                        results = search_resp.json().get("results", [])
                        
                        for item in results[:6]: # Limited to 6 for speed & stability
                            zpid = item.get("id")
                            z_url = item.get("detailUrl")
                            
                            # STEP 2: Deep Dive (Trying the Property-Info endpoint)
                            info_url = "https://real-estate101.p.rapidapi.com/api/property-info"
                            info_resp = requests.get(info_url, headers=headers, params={"propertyId": zpid})
                            
                            # If the ID search fails, try searching by the URL as a backup
                            if info_resp.status_code != 200:
                                backup_url = "https://real-estate101.p.rapidapi.com/api/search/byurl"
                                info_resp = requests.get(backup_url, headers=headers, params={"url": z_url})
                            
                            time.sleep(1.5) # Extra delay to ensure the server processes the request
                            
                            start_t, end_t, broker = "N/A", "N/A", "N/A"
                            
                            if info_resp.status_code == 200:
                                details = info_resp.json()
                                # Try to find the schedule
                                schedule = details.get("openHouseSchedule", details.get("openHouses", []))
                                if schedule and isinstance(schedule, list):
                                    start_t = str(schedule[0].get("startTime", "N/A"))
                                    end_t = str(schedule[0].get("endTime", "N/A"))
                                
                                # Try to find the broker
                                broker = details.get("brokerageName", details.get("attributionInfo", {}).get("brokerName", "N/A"))
                            else:
                                system_errors.append(f"Failed {zpid}: Error {info_resp.status_code}")

                            addr = item.get("address", {})
                            full_addr = f"{addr.get('street')}, {addr.get('city')}, {addr.get('state')} {addr.get('zipcode')}"
                            lat_lon = item.get("latLong", {})
                            
                            if lat_lon.get("latitude"):
                                valid_coords.append(f"{lat_lon['longitude']},{lat_lon['latitude']}")
                                houses.append({
                                    "Start Time": start_t,
                                    "End Time": end_t,
                                    "Address": full_addr,
                                    "Price": item.get("price", "N/A"),
                                    "Agent/Brokerage": broker
                                })
                
                if houses:
                    # STEP 3: Route Re-ordering
                    if len(valid_coords) > 1:
                        route_url = f"https://api.mapbox.com/optimized-trips/v1/mapbox/driving/{';'.join(valid_coords[:1
