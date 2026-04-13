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
    zip_codes_input = st.text_input("Locations (Zip or City-State)", value="spokane-wa")
    
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
        st.error("Please enter at least one Location.")
    else:
        with st.spinner("Fetching listings and extracting specific Open House times..."):
            try:
                houses = []
                valid_coords = []
                debug_log = [] # Updated debug log
                
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
                        search_data = search_resp.json()
                        debug_log.append({"STEP 1: SEARCH RESPONSE FOR " + zcode: search_data})
                        results = search_data.get("results", [])
                        
                        for item in results:
                            sub_type = item.get("listingSubType", {})
                            if sub_type.get("is_openHouse", False):
                                property_id = item.get("id")
                                
                                # Call 2: Ping Property-Info for the exact Start/End Times
                                info_url = "https://real-estate101.p.rapidapi.com/api/property-info"
                                info_qs = {"zpid": property_id} 
                                
                                info_resp = requests.get(info_url, headers=headers, params=info_qs)
                                
                                start_time = "N/A"
                                end_time = "N/A"
                                date_matches = False
                                
                                if info_resp.status_code == 200:
                                    info_data = info_resp.json()
                                    debug_log.append({f"STEP 2: PROPERTY INFO FOR {property_id}": info_data})
                                    
                                    info_str = json.dumps(info_data).lower()
                                    
                                    if not selected_dates or any(target_date in info_str for target_date in selected_dates):
                                        date_matches = True
                                        
                                if date_matches: 
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
                                                "Start Time": start_time,
                                                "End Time": end_time,
                                                "Address": full_address,
                                                "Saves/Likes": "N/A",
                                                "DOM": dom,
                                                "Current Price": price,
                                                "Agent & Brokerage": "N/A"
                                            })
                
                if houses:
                    st.success(f"Extracted {len(houses)} Open Houses!")
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
                            st.success("Route perfectly optimized!")
                    df = pd.DataFrame(houses)
                    st.dataframe(df, use_container_width=True)
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button("Download Route as CSV", data=csv, file_name="route_scoute_optimized.csv", mime="text/csv")
                else:
                    st.warning("No open houses matched your exact date selections.")

                with st.expander("🛠️ Debug: Show Raw API Data (Click to Expand)"):
                    st.json(debug_log)

            except Exception as e:
                st.error(f"An error occurred: {e}")
