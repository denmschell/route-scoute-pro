import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime

# Page Config
st.set_page_config(page_title="Route Scoute Pro", layout="wide")
st.title("Route Scoute Pro 🚗")
st.write("Generate an optimized open house driving route.")

# Securely load API Keys
RAPID_KEY = st.secrets["RAPID_API_KEY"]
MAPBOX_KEY = st.secrets["MAPBOX_API_KEY"]

# Input Form
with st.form("input_form"):
    st.write("### Search Parameters")
    zip_codes_input = st.text_input("Zip Codes (separate by commas)", value="99223")
    
    col1, col2, col3 = st.columns(3)
    with col1: date_1 = st.date_input("Date Option 1", value=None)
    with col2: date_2 = st.date_input("Date Option 2", value=None)
    with col3: date_3 = st.date_input("Date Option 3", value=None)
    
    submit = st.form_submit_button("Fetch Times & Optimize Route")

if submit:
    zip_list = [z.strip() for z in zip_codes_input.split(",") if z.strip()]
    
    selected_dates = []
    for d in [date_1, date_2, date_3]:
        if d:
            selected_dates.append(d.strftime("%Y-%m-%d"))
            
    if not zip_list:
        st.error("Please enter at least one Zip Code.")
    elif not selected_dates:
         st.error("Please select at least one Date.")
    else:
        with st.spinner("Fetching listings and extracting specific Open House times..."):
            try:
                houses = []
                valid_coords = []
                
                for zcode in zip_list:
                    # Call 1: Get the list of open houses
                    search_url = "https://real-estate101.p.rapidapi.com/api/search"
                    search_qs = {"location": zcode, "isOpenHousesOnly": "true"}
                    headers = {
                        "x-rapidapi-host": "real-estate101.p.rapidapi.com",
                        "x-rapidapi-key": RAPID_KEY
                    }
                    
                    search_resp = requests.get(search_url, headers=headers, params=search_qs)
                    
                    if search_resp.status_code == 200:
                        results = search_resp.json().get("results", [])
                        
                        for item in results:
                            sub_type = item.get("listingSubType", {})
                            if sub_type.get("is_openHouse", False):
                                property_id = item.get("id")
                                
                                # Call 2: Ping Property-Info for the exact Start/End Times
                                info_url = "https://real-estate101.p.rapidapi.com/api/property-info"
                                info_qs = {"zpid": property_id} # zpid is the standard parameter for Zillow IDs
                                
                                info_resp = requests.get(info_url, headers=headers, params=info_qs)
                                
                                start_time = "N/A"
                                end_time = "N/A"
                                date_matches = False
                                
                                if info_resp.status_code == 200:
                                    info_data = info_resp.json()
                                    open_house_events = info_data.get("openHouseSchedule", [])
                                    
                                    # Fallback if API structures it under a different key
                                    if not open_house_events and "resoFacts" in info_data:
                                        open_house_events = info_data.get("resoFacts", {}).get("openHouseSchedule", [])
                                        
                                    for event in open_house_events:
                                        event_start = event.get("startTime", "")
                                        event_end = event.get("endTime", "")
                                        
                                        # Check if this specific event falls on any of the user's 3 chosen dates
                                        if any(target_date in event_start for target_date in selected_dates):
                                            date_matches = True
                                            start_time = event_start
                                            end_time = event_end
                                            break
                                
                                # If the date matches OR we couldn't parse the deep info but know it's an open house
                                if date_matches or not selected_dates: 
                                    addr_dict = item.get("address", {})
                                    full_address = f"{addr_dict.get('street', '')}, {addr_dict.get('city', '')}, {addr_dict.get('state', '')} {addr_dict.get('zipcode', '')}".strip(", ")
                                    
                                    price = item.get("price", "N/A")
                                    dom = item.get("daysOnZillow", "N/A")
                                    
                                    lat_long = item.get("latLong", {})
                                    lat = lat_long.get("latitude")
                                    lon = lat_long.get("longitude")
                                    
                                    if lat and lon:
                                        coord_str = f"{lon},{lat}"
                                        if coord_str not in valid_coords: 
                                            valid_coords.append(coord_str)
                                            
                                            houses.append({
                                                "Start Time": start_time.split(" ")[1][:5] if " " in start_time else start_time,
                                                "End Time": end_time.split(" ")[1][:5] if " " in end_time else end_time,
                                                "Start-End": f"{start_time} to {end_time}",
                                                "Address": full_address,
                                                "Saves/Likes": "N/A",
                                                "DOM": dom,
                                                "Current Price": price,
                                                "Agent & Brokerage": "N/A"
                                            })
                
                if houses:
                    st.success(f"Extracted {len(houses)} Open Houses matching your dates!")
                    
                    # Call 3: Optimize Route using Mapbox API
                    if len(valid_coords) > 1 and len(valid_coords) <= 12:
                        coord_string = ";".join(valid_coords)
                        mapbox_url = f"https://api.mapbox.com/optimized-trips/v1/mapbox/driving/{coord_string}?access_token={MAPBOX_KEY}"
                        
                        route_resp = requests.get(mapbox_url)
                        if route_resp.status_code == 200:
                            route_data = route_resp.json()
                            waypoints = route_data.get("waypoints", [])
                            sorted_houses = [None] * len(houses)
                            
                            for idx, wp in enumerate(waypoints):
                                original_index = wp.get("waypoint_index")
                                sorted_houses[original_index] = houses[idx]
                                
                            houses = [h for h in sorted_houses if h is not None]
                            st.success("Route perfectly optimized for minimal drive time!")
                        else:
                            st.warning("Mapbox routing failed. Displaying unoptimized list.")

                    elif len(valid_coords) > 12:
                        st.warning("Mapbox optimization is limited to 12 waypoints per request. Displaying unoptimized list.")
                    elif len(valid_coords) == 1:
                        st.info("Only 1 property matched your dates. No routing necessary.")

                    # Output Table & CSV
                    df = pd.DataFrame(houses)
                    st.dataframe(df, use_container_width=True)
                    
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button("Download Route as CSV", data=csv, file_name="route_scoute_optimized.csv", mime="text/csv")
                else:
                    st.warning("No open houses matched your exact date selections. Try removing dates or checking upcoming weekends.")

            except Exception as e:
                st.error(f"An error occurred: {e}")
