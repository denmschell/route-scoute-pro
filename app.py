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
        with st.spinner("Step 1: Finding Houses... Step 2: Extracting Times & Agents..."):
            try:
                houses = []
                valid_coords = []
                
                for zcode in zip_list:
                    url = "https://real-estate101.p.rapidapi.com/api/search"
                    headers = {"x-rapidapi-host": "real-estate101.p.rapidapi.com", "x-rapidapi-key": RAPID_KEY}
                    params = {"location": zcode, "isOpenHousesOnly": "true"}
                    
                    search_resp = requests.get(url, headers=headers, params=params)
                    
                    if search_resp.status_code == 200:
                        results = search_resp.json().get("results", [])
                        
                        # We process the first 10 results to keep it fast and safe
                        for item in results[:10]:
                            zillow_url = item.get("detailUrl")
                            
                            # DEEP DIVE: Get Times and Brokerage
                            info_url = "https://real-estate101.p.rapidapi.com/api/search/byurl"
                            info_resp = requests.get(info_url, headers=headers, params={"url": zillow_url})
                            
                            # Respect API limits
                            time.sleep(1) 

                            start_t, end_t, broker = "N/A", "N/A", "N/A"
                            
                            if info_resp.status_code == 200:
                                details = info_resp.json()
                                # Extract times from schedule
                                schedule = details.get("openHouseSchedule", [])
                                if schedule:
                                    start_t = schedule[0].get("startTime", "N/A")
                                    end_t = schedule[0].get("endTime", "N/A")
                                
                                # Extract Brokerage/Agent
                                broker = details.get("brokerageName", details.get("attributionInfo", {}).get("brokerName", "N/A"))

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
                                    "Agent/Brokerage": broker
                                })
                
                if houses:
                    # Mapbox Routing
                    if len(valid_coords) > 1:
                        route_url = f"https://api.mapbox.com/optimized-trips/v1/mapbox/driving/{';'.join(valid_coords[:12])}?access_token={MAPBOX_KEY}"
                        r_resp = requests.get(route_url)
                        if r_resp.status_code == 200:
                            waypoints = r_resp.json().get("waypoints", [])
                            houses = [houses[wp['waypoint_index']] for wp in sorted(waypoints, key=lambda x: x['waypoint_index'])]
                            st.success("Full data extracted and route optimized!")

                    st.dataframe(pd.DataFrame(houses), use_container_width=True)
                else:
                    st.warning("No open houses found.")

            except Exception as e:
                st.error(f"Error: {e}")
