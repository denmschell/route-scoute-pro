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
    zip_codes_input = st.text_input("Zip Codes (separate by commas)", value="99223")
    submit = st.form_submit_button("Fetch & Optimize")

if submit:
    zip_list = [z.strip() for z in zip_codes_input.split(",") if z.strip()]
    
    if not zip_list:
        st.error("Please enter at least one Zip Code.")
    else:
        with st.spinner("Connecting to Realtime Scraper API..."):
            try:
                houses = []
                valid_coords = []
                raw_api_responses = [] 
                
                for zcode in zip_list:
                    url = "https://real-estate101.p.rapidapi.com/api/search"
                    # The API handles the Open House filter on its end
                    querystring = {"location": zcode, "isOpenHousesOnly": "true"}
                    headers = {
                        "x-rapidapi-host": "real-estate101.p.rapidapi.com",
                        "x-rapidapi-key": RAPID_KEY
                    }
                    
                    response = requests.get(url, headers=headers, params=querystring)
                    
                    if response.status_code == 200:
                        data = response.json()
                        raw_api_responses.append(data)
                        
                        # Based on your debug log, the data lives inside "results"
                        props = data.get("results", [])
                        
                        for item in props:
                            # Verify it's an open house based on the API's flag
                            sub_type = item.get("listingSubType", {})
                            if sub_type.get("is_openHouse", False):
                                
                                # Extract Address from nested dictionary
                                addr_dict = item.get("address", {})
                                street = addr_dict.get("street", "")
                                city = addr_dict.get("city", "")
                                state = addr_dict.get("state", "")
                                zip_c = addr_dict.get("zipcode", "")
                                full_address = f"{street}, {city}, {state} {zip_c}".strip(", ")
                                
                                price = item.get("price", "N/A")
                                dom = item.get("daysOnZillow", "N/A")
                                
                                # Map coordinates from nested dictionary
                                lat_long = item.get("latLong", {})
                                lat = lat_long.get("latitude")
                                lon = lat_long.get("longitude")
                                
                                if lat and lon:
                                    coord_str = f"{lon},{lat}"
                                    if coord_str not in valid_coords: 
                                        valid_coords.append(coord_str)
                                        
                                        houses.append({
                                            "Start Time": "Check Listing", # API omits specific times in this view
                                            "End Time": "Check Listing",
                                            "Address": full_address if full_address else "Unknown Address",
                                            "Saves/Likes": "N/A",
                                            "DOM": dom,
                                            "Current Price": price,
                                            "Agent & Brokerage": "Check Listing" # API omits agent info in this view
                                        })
                    else:
                        st.error(f"API Error {response.status_code} for {zcode}")
                
                if houses:
                    st.success(f"Found {len(houses)} Open Houses!")
                    
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
                    st.warning("No open houses found in that zip code.")

            except Exception as e:
                st.error(f"An error occurred: {e}")
