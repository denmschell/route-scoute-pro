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
        with st.spinner("Finding houses and extracting schedules... this takes ~10 seconds."):
            try:
                houses = []
                valid_coords = []
                debug_deep_info = [] # To capture raw data for fixing N/A

                for zcode in zip_list:
                    search_url = "https://real-estate101.p.rapidapi.com/api/search"
                    headers = {"x-rapidapi-host": "real-estate101.p.rapidapi.com", "x-rapidapi-key": RAPID_KEY}
                    search_resp = requests.get(search_url, headers=headers, params={"location": zcode, "isOpenHousesOnly": "true"})
                    
                    if search_resp.status_code == 200:
                        results = search_resp.json().get("results", [])
                        
                        # Process first 10 for speed
                        for item in results[:10]:
                            zillow_url = item.get("detailUrl")
                            
                            # DEEP DIVE call
                            info_url = "https://real-estate101.p.rapidapi.com/api/search/byurl"
                            info_resp = requests.get(info_url, headers=headers, params={"url": zillow_url})
                            
                            time.sleep(0.5) # Slight delay to be safe

                            start_t, end_t, agent_broker = "N/A", "N/A", "N/A"
                            
                            if info_resp.status_code == 200:
                                details = info_resp.json()
                                if not debug_deep_info: debug_deep_info.append(details) # Grab first house for debug
                                
                                # AGGRESSIVE TIME SEARCH
                                # Checking all common Zillow scraper keys
                                schedule = details.get("openHouseSchedule", details.get("openHouses", []))
                                if not schedule and "resoFacts" in details:
                                    schedule = details["resoFacts"].get("openHouseSchedule", [])
                                
                                if schedule and isinstance(schedule, list):
                                    start_t = schedule[0].get("startTime", "N/A")
                                    end_t = schedule[0].get("endTime", "N/A")

                                # AGGRESSIVE AGENT/BROKER SEARCH
                                attr = details.get("attributionInfo", {})
                                agent_broker = details.get("brokerageName", details.get("brokerName", "N/A"))
                                if agent_broker == "N/A":
                                    agent_broker = attr.get("brokerName", attr.get("agentName", "N/A"))

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
                    # FIX: Correct Mapbox Waypoint Sequencing
                    if len(valid_coords) > 1:
                        route_url = f"https://api.mapbox.com/optimized-trips/v1/mapbox/driving/{';'.join(valid_coords[:12])}?access_token={MAPBOX_KEY}"
                        r_resp = requests.get(route_url)
                        if r_resp.status_code == 200:
                            # Waypoints are returned in the OPTIMIZED order
                            waypoints = r_resp.json().get("waypoints", [])
                            # Map original house data to its new optimized position
                            houses = [houses[wp['waypoint_index']] for wp in waypoints]
                            st.success("Route perfectly optimized!")

                    st.dataframe(pd.DataFrame(houses), use_container_width=True)
                else:
                    st.warning("No open houses found in these zip codes.")

                with st.expander("🛠️ Deep Debug (Raw Data for 1st House)"):
                    st.write("If you see N/A above, paste this data for me to inspect:")
                    st.json(debug_deep_info)

            except Exception as e:
                st.error(f"Error: {e}")
