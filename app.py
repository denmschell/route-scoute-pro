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
        with st.spinner("Executing Deep Search... This takes ~15 seconds."):
            try:
                houses = []
                valid_coords = []
                system_errors = []

                for zcode in zip_list:
                    # STEP 1: Search
                    search_url = "https://real-estate101.p.rapidapi.com/api/search"
                    headers = {"x-rapidapi-host": "real-estate101.p.rapidapi.com", "x-rapidapi-key": RAPID_KEY}
                    search_resp = requests.get(search_url, headers=headers, params={"location": zcode, "isOpenHousesOnly": "true"})
                    
                    if search_resp.status_code == 200:
                        results = search_resp.json().get("results", [])
                        
                        for item in results[:8]: # Limit to 8 houses for stability
                            zpid = item.get("id")
                            z_url = item.get("detailUrl")
                            
                            # STEP 2: Deep Dive (Try two different endpoints)
                            # Primary: property-info
                            info_url = "https://real-estate101.p.rapidapi.com/api/property"
                            info_resp = requests.get(info_url, headers=headers, params={"propertyId": zpid})
                            
                            time.sleep(1) # Crucial: prevent API blocking
                            
                            start_t, end_t, agent_broker = "N/A", "N/A", "N/A"
                            
                            if info_resp.status_code == 200:
                                details = info_resp.json()
                                
                                # Extraction
                                schedule = details.get("openHouseSchedule", details.get("openHouses", []))
                                if not schedule and "resoFacts" in details:
                                    schedule = details["resoFacts"].get("openHouseSchedule", [])
                                
                                if schedule and isinstance(schedule, list):
                                    start_t = str(schedule[0].get("startTime", "N/A"))
                                    end_t = str(schedule[0].get("endTime", "N/A"))

                                attr = details.get("attributionInfo", {})
                                agent_broker = details.get("brokerageName", attr.get("brokerName", "N/A"))
                            else:
                                system_errors.append(f"Deep Search failed for {zpid} with Error: {info_resp.status_code}")

                            # Map Data
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
                                    "DOM": item.get("daysOnZillow", "N/A"),
                                    "Agent/Brokerage": agent_broker
                                })
                
                if houses:
                    # STEP 3: Optimized Routing
                    if len(valid_coords) > 1:
                        route_url = f"https://api.mapbox.com/optimized-trips/v1/mapbox/driving/{';'.join(valid_coords[:12])}?access_token={MAPBOX_KEY}"
                        r_resp = requests.get(route_url)
                        if r_resp.status_code == 200:
                            waypoints = r_resp.json().get("waypoints", [])
                            # SORT logic: use the 'waypoint_index' to reorder the houses list
                            houses = [houses[wp['waypoint_index']] for wp in sorted(waypoints, key=lambda x: x['waypoint_index'])]
                            st.success("Route optimized based on drive distance!")

                    st.dataframe(pd.DataFrame(houses), use_container_width=True)
                else:
                    st.warning("No open houses found. Check the System Errors below.")

                with st.expander("🛠️ System Log / Error Tracker"):
                    st.write("If times are missing, tell me which error code appears here:")
                    st.write(system_errors)

            except Exception as e:
                st.error(f"Error: {e}")
