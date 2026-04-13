import streamlit as st
import requests
import pandas as pd
import json

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
    zip_codes_input = st.text_input("Zip Codes (separate by commas)", value="99208, 99218")
    
    col1, col2, col3 = st.columns(3)
    with col1: date_1 = st.date_input("Date Option 1", value=None)
    with col2: date_2 = st.date_input("Date Option 2", value=None)
    with col3: date_3 = st.date_input("Date Option 3", value=None)
    
    submit = st.form_submit_button("Fetch & Optimize")

if submit:
    zip_list = [z.strip() for z in zip_codes_input.split(",") if z.strip()]
    
    selected_dates = []
    for d in [date_1, date_2, date_3]:
        if d:
            # We save dates in a few formats just in case the API formats them weirdly
            selected_dates.append(d.strftime("%Y-%m-%d"))
            selected_dates.append(d.strftime("%-m/%-d/%Y"))
            
    if not zip_list:
        st.error("Please enter at least one Zip Code.")
    elif not selected_dates:
         st.error("Please select at least one Date.")
    else:
        with st.spinner("Connecting to Realtime Scraper API..."):
            try:
                houses = []
                valid_coords = []
                raw_api_responses = [] 
                
                for zcode in zip_list:
                    url = "https://real-estate101.p.rapidapi.com/api/search"
                    # Stripped out the junk, keeping only what we need
                    querystring = {"location": zcode, "isOpenHousesOnly": "true"}
                    headers = {
                        "x-rapidapi-host": "real-estate101.p.rapidapi.com",
                        "x-rapidapi-key": RAPID_KEY
                    }
                    
                    response = requests.get(url, headers=headers, params=querystring)
                    
                    if response.status_code == 200:
                        data = response.json()
                        raw_api_responses.append(data)
                        
                        # APIs hide the list of houses under different names. We will check the most common ones.
                        props = []
                        if isinstance(data, list):
                            props = data
                        elif isinstance(data, dict):
                            for key in ["properties", "data", "results", "props", "listings"]:
                                if key in data and isinstance(data[key], list):
                                    props = data[key]
                                    break
                        
                        for item in props:
                            item_str = json.dumps(item).lower()
                            
                            # Check if ANY of our dates exist anywhere in this property's data
                            if any(target_date.lower() in item_str for target_date in selected_dates):
                                
                                # Extract basic info (with fallbacks if the name is slightly different)
                                address = item.get("address", item.get("streetAddress", "Unknown Address"))
                                price = item.get("price", item.get("listPrice", 0))
                                agent = item.get("brokerName", "Unknown Broker")
                                dom = item.get("daysOnZillow", "N/A")
                                
                                # Map coordinates
                                lat = item.get("latitude", item.get("lat"))
                                lon = item.get("longitude", item.get("lon"))
                                
                                if lat and lon:
                                    coord_str = f"{lon},{lat}"
                                    if coord_str not in valid_coords: 
                                        valid_coords.append(coord_str)
                                        
                                        houses.append({
                                            "Start Time": "Check Listing", 
                                            "End Time": "Check Listing",
                                            "Address": address,
                                            "Saves/Likes": "N/A",
                                            "DOM": dom,
                                            "Current Price": f"${price:,.0f}" if isinstance(price, (int, float)) else price,
                                            "Agent & Brokerage": agent,
                                            "Raw Data Snippet": str(item)[:150] + "..."
                                        })
                    else:
                        st.error(f"API Error {response.status_code} for {zcode}")
                
                if houses:
                    st.success("Found properties and Dates Matched!")
                    
                    # Route Optimization Block
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
                            st.success("Route Optimized via Mapbox!")
                        else:
                            st.warning("Mapbox routing failed. Displaying unoptimized list.")

                    elif len(valid_coords) > 12:
                        st.warning("Mapbox optimization is limited to 12 waypoints per request. Displaying unoptimized list.")

                    # Output Table & CSV
                    df = pd.DataFrame(houses)
                    st.dataframe(df, use_container_width=True)
                    
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button("Download Route as CSV", data=csv, file_name="route_scoute_optimized.csv", mime="text/csv")
                else:
                    st.warning("No properties matched your dates, OR the API format didn't match. Check the debug log below.")

                # The Crucial Debug Log
                with st.expander("🛠️ Debug: Show Raw API Data (Click to Expand)"):
                    st.write("Look here to see how this specific API formats the data:")
                    st.json(raw_api_responses)

            except Exception as e:
                st.error(f"An error occurred: {e}")
