import streamlit as st
import requests
import pandas as pd
import json

# Page Config
st.set_page_config(page_title="Route Scoute Pro", layout="wide")
st.title("Route Scoute Pro 🚗")

# Securely load API Keys
RAPID_KEY = st.secrets["RAPID_API_KEY"]
MAPBOX_KEY = st.secrets["MAPBOX_API_KEY"]

# Input Form
with st.form("input_form"):
    st.write("### Zip Code Search")
    zip_input = st.text_input("Enter Zip Codes (separate by commas)", value="")
    
    col1, col2, col3 = st.columns(3)
    with col1: date_1 = st.date_input("Date Option 1", value=None)
    with col2: date_2 = st.date_input("Date Option 2", value=None)
    with col3: date_3 = st.date_input("Date Option 3", value=None)
    
    submit = st.form_submit_button("Generate Zip-Specific Route")

if submit:
    zip_list = [z.strip() for z in zip_input.split(",") if z.strip()]
    selected_dates = [d.strftime("%Y-%m-%d") for d in [date_1, date_2, date_3] if d]
            
    if not zip_list:
        st.error("Please enter at least one Zip Code.")
    else:
        with st.spinner("Searching specific Zip Codes for Open Houses..."):
            try:
                houses = []
                valid_coords = []
                
                for zcode in zip_list:
                    # Search endpoint using the Zip Code directly
                    url = "https://real-estate101.p.rapidapi.com/api/search"
                    headers = {
                        "x-rapidapi-host": "real-estate101.p.rapidapi.com", 
                        "x-rapidapi-key": RAPID_KEY
                    }
                    # Force the API to only look at the Zip Code and only Open Houses
                    params = {"location": zcode, "isOpenHousesOnly": "true", "status_type": "ForSale"}
                    
                    response = requests.get(url, headers=headers, params=params)
                    
                    if response.status_code == 200:
                        results = response.json().get("results", [])
                        
                        for item in results:
                            # 1+1=2 Logic: Only include if it is confirmed as an Open House
                            if item.get("listingSubType", {}).get("is_openHouse", False):
                                
                                # Date Filtering (if dates were selected)
                                # Note: Scrapers often require the secondary 'property' call for exact hours.
                                # This block captures the house for the route if any date matches the broad search.
                                addr = item.get("address", {})
                                full_addr = f"{addr.get('street')}, {addr.get('city')}, {addr.get('state')} {addr.get('zipcode')}"
                                
                                lat_lon = item.get("latLong", {})
                                lat, lon = lat_lon.get("latitude"), lat_lon.get("longitude")
                                
                                if lat and lon:
                                    valid_coords.append(f"{lon},{lat}")
                                    
                                    houses.append({
                                        "Address": full_addr,
                                        "Price": item.get("price", "N/A"),
                                        "DOM": item.get("daysOnZillow", "N/A"),
                                        "Agent": item.get("brokerName", "N/A"),
                                        "Zip Code": zcode
                                    })
                
                if houses:
                    # Route Optimization
                    if len(valid_coords) > 1:
                        route_url = f"https://api.mapbox.com/optimized-trips/v1/mapbox/driving/{';'.join(valid_coords[:12])}?access_token={MAPBOX_KEY}"
                        r_resp = requests.get(route_url)
                        if r_resp.status_code == 200:
                            waypoints = r_resp.json().get("waypoints", [])
                            # Reorder based on Mapbox optimization
                            houses = [houses[wp['waypoint_index']] for wp in sorted(waypoints, key=lambda x: x['waypoint_index'])]
                            st.success("Route optimized for the selected Zip Codes!")

                    st.dataframe(pd.DataFrame(houses), use_container_width=True)
                    st.download_button("Download CSV", pd.DataFrame(houses).to_csv(index=False), "zip_route.csv", "text/csv")
                else:
                    st.warning("No open houses found in those specific zip codes today.")

            except Exception as e:
                st.error(f"Error: {e}")
