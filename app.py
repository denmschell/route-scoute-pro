import streamlit as st
import requests
import pandas as pd
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
    # Multiple Zip Codes
    zip_codes_input = st.text_input("Zip Codes (separate by commas)", value="99201, 99202")
    
    # 3 Date Options
    col1, col2, col3 = st.columns(3)
    with col1: date_1 = st.date_input("Date Option 1", value=None)
    with col2: date_2 = st.date_input("Date Option 2", value=None)
    with col3: date_3 = st.date_input("Date Option 3", value=None)
    
    submit = st.form_submit_button("Generate Optimized Route")

if submit:
    zip_list = [z.strip() for z in zip_codes_input.split(",") if z.strip()]
    
    # Collect all selected dates
    selected_dates = []
    for d in [date_1, date_2, date_3]:
        if d:
            selected_dates.append(d.strftime("%Y-%m-%d"))
            
    if not zip_list:
        st.error("Please enter at least one Zip Code.")
    elif not selected_dates:
         st.error("Please select at least one Date.")
    else:
        with st.spinner("Fetching data and optimizing route..."):
            try:
                houses = []
                valid_coords = []
                
                # 1. Fetch Data from RapidAPI for each Zip Code
                for zcode in zip_list:
                    url = "https://us-housing-market-data1.p.rapidapi.com/propertyExtendedSearch"
                    querystring = {"location": zcode, "status_type": "ForSale", "isOpenHousesOnly": "true"}
                    headers = {
                        "X-RapidAPI-Key": RAPID_KEY,
                        "X-RapidAPI-Host": "us-housing-market-data1.p.rapidapi.com"
                    }
                    
                    response = requests.get(url, headers=headers, params=querystring)
                    
                    if response.status_code == 200:
                        data = response.json()
                        props = data.get("props", [])
                        
                        for item in props:
                            # Extract basic info
                            address = item.get("address", "Unknown Address")
                            price = item.get("price", 0)
                            dom = item.get("daysOnZillow", "N/A")
                            agent = item.get("brokerName", "Unknown Broker")
                            
                            lat = item.get("latitude")
                            lon = item.get("longitude")
                            
                            # Filter based on Open House Dates selected by the user
                            open_house_data = item.get("openHouseDetails", [])
                            for oh in open_house_data:
                                oh_date_str = oh.get("openHouseDate", "") # e.g. "2026-04-18"
                                
                                # Check if this open house matches any of our 3 dates
                                if any(target_date in oh_date_str for target_date in selected_dates):
                                    start_time = oh.get("openHouseStartTime", "N/A")
                                    end_time = oh.get("openHouseEndTime", "N/A")
                                    
                                    if lat and lon:
                                        coord_str = f"{lon},{lat}"
                                        if coord_str not in valid_coords: # Basic deduplication
                                            valid_coords.append(coord_str)
                                            
                                            houses.append({
                                                "Start Time": start_time,
                                                "End Time": end_time,
                                                "Start-End": f"{start_time} - {end_time}",
                                                "Address": address,
                                                "Saves/Likes": "N/A",
                                                "DOM": dom,
                                                "Current Price": f"${price:,.0f}",
                                                "Agent & Brokerage": agent
                                            })
                
                if not houses:
                    st.warning("No open houses found matching your exact zip codes and dates.")
                else:
                    # 2. Optimize Route using Mapbox API
                    if len(valid_coords) > 1 and len(valid_coords) <= 12:
                        coord_string = ";".join(valid_coords)
                        mapbox_url = f"https://api.mapbox.com/optimized-trips/v1/mapbox/driving/{coord_string}?access_token={MAPBOX_KEY}"
                        
                        route_resp = requests.get(mapbox_url)
                        route_resp.raise_for_status()
                        route_data = route_resp.json()
                        
                        waypoints = route_data.get("waypoints", [])
                        sorted_houses = [None] * len(houses)
                        
                        for idx, wp in enumerate(waypoints):
                            original_index = wp.get("waypoint_index")
                            sorted_houses[original_index] = houses[idx]
                            
                        houses = [h for h in sorted_houses if h is not None]

                    elif len(valid_coords) > 12:
                        st.warning("Mapbox optimization is limited to 12 waypoints per request. Displaying unoptimized list.")

                    # 3. Display Output and CSV Download
                    df = pd.DataFrame(houses)
                    st.success("Route Optimized!")
                    st.dataframe(df, use_container_width=True)
                    
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Route as CSV",
                        data=csv,
                        file_name=f"route_scoute_optimized.csv",
                        mime="text/csv",
                    )

            except Exception as e:
                st.error(f"An error occurred: {e}")
