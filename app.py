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
        with st.spinner("Finding houses and extracting schedules... this takes ~15 seconds."):
            try:
                houses = []
                valid_coords = []
                system_log = []

                for zcode in zip_list:
                    # STEP 1: Search for IDs
                    search_url = "https://real-estate101.p.rapidapi.com/api/search"
                    headers = {
                        "x-rapidapi-host": "real-estate101.p.rapidapi.com", 
                        "x-rapidapi-key": RAPID_KEY
                    }
                    search_resp = requests.get(search_url, headers=headers, params={"location": zcode, "isOpenHousesOnly": "true"})
                    
                    if search_resp.status_code == 200:
                        results = search_resp.json().get("results", [])
                        
                        for item in results[:8]: # Limit for speed
                            zpid = item.get("id")
                            z_url = item.get("detailUrl")
                            
                            # STEP 2: Deep Dive (Using property-info endpoint)
                            # We are trying the specific property-info endpoint as per your playground screenshot
                            info_url = "https://real-estate101.p.rapidapi.com/api/property-info"
                            info_resp = requests.get(info_url, headers=headers, params={"zpid": zpid})
                            
                            time.sleep(1.2) # Prevent API Rate Limiting
                            
                            start_t, end_t, agent_broker = "N/A", "N/A", "N/A"
                            
                            if info_resp.status_code == 200:
                                details = info_resp.json()
                                # Extraction logic for times
                                schedule = details.get("openHouseSchedule", [])
                                if not schedule and "resoFacts" in details:
                                    schedule = details["resoFacts"].get("openHouseSchedule", [])
                                
                                if schedule and isinstance(schedule, list):
                                    start_t = str(schedule[0].get("startTime", "N/A"))
                                    end_t = str(schedule[0].get("endTime", "N/A"))
                                
                                # Extraction logic for brokerage
                                attr = details.get("attributionInfo", {})
                                agent_broker = details.get("brokerageName", attr.get("brokerName", "N/A"))
                                system_log.append(f"SUCCESS: {zpid}")
                            else:
                                system_log.append(f"FAILED: {zpid} (Error {info_resp.status_code})")

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
                                    "Agent/Brokerage": agent_broker
                                })
                    else:
                        st.error(f"Search failed for {zcode}: {search_resp.status_code}")

                if houses:
                    # STEP 3: Route Re-ordering via Mapbox
                    if len(valid_coords) > 1:
                        # Fixed syntax on this line
                        coords_joined = ";".join(valid_coords[:12])
                        mapbox_url = f"https://api.mapbox.com/optimized-trips/v1/mapbox/driving/{coords_joined}?access_token={MAPBOX_KEY}"
                        
                        r_resp = requests.get(mapbox_url)
                        if r_resp.status_code == 200:
                            waypoints = r_resp.json().get("waypoints", [])
                            # Re-order houses into driving sequence
                            optimized_list = [None] * len(houses)
                            for wp in waypoints:
                                original_idx = wp['location_index']
                                new_sequence_idx = wp['waypoint_index']
                                optimized_list[new_sequence_idx] = houses[original_idx]
                            
                            houses = [h for h in optimized_list if h is not None]
                            st.success("Driving route perfectly optimized!")

                    st.dataframe(pd.DataFrame(houses), use_container_width=True)
                    st.download_button("Download Route CSV", pd.DataFrame(houses).to_csv(index=False), "route.csv", "text/csv")
                else:
                    st.warning("No open houses found for those zip codes.")

                with st.expander("🛠️ Final System Log"):
                    st.write(system_log)

            except Exception as e:
                st.error(f"App Error: {e}")
