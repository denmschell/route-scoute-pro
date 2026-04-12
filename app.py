import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Page Config
st.set_page_config(page_title="Route Scoute Pro", layout="wide")
st.title("Route Scoute Pro 🚗")
st.write("Generate an optimized open house driving route.")

# Securely load API Keys
REPLIERS_KEY = st.secrets["REPLIERS_API_KEY"]
MAPBOX_KEY = st.secrets["MAPBOX_API_KEY"]

# Input Form
with st.form("input_form"):
    col1, col2 = st.columns(2)
    with col1:
        zip_code = st.text_input("Zip Code", value="99201")
    with col2:
        target_date = st.date_input("Date")
    
    submit = st.form_submit_button("Generate Optimized Route")

if submit:
    if not zip_code:
        st.error("Please enter a Zip Code.")
    else:
        with st.spinner("Fetching MLS data and optimizing route..."):
            try:
                # 1. Fetch Data from Repliers API
                formatted_date = target_date.strftime("%Y-%m-%d")
                
                headers = {"REPLIERS-API-KEY": REPLIERS_KEY}
                repliers_url = f"https://api.repliers.io/listings?zip={zip_code}&minOpenHouseDate={formatted_date}&maxOpenHouseDate={formatted_date}&status=A"
                
                response = requests.get(repliers_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                listings = data.get("listings", [])
                
                if not listings:
                    st.warning(f"No open houses found for {zip_code} on {formatted_date}.")
                else:
                    # Parse and format the raw MLS data
                    houses = []
                    valid_coords = []
                    
                    for item in listings:
                        address = item.get("address", {})
                        full_address = f"{address.get('streetNumber', '')} {address.get('streetName', '')}, {address.get('city', '')}"
                        
                        # Extract Open House Times
                        open_houses = item.get("openHouses", [{}])
                        start_time = open_houses[0].get("startTime", "N/A") if open_houses else "N/A"
                        end_time = open_houses[0].get("endTime", "N/A") if open_houses else "N/A"
                        
                        # Calculate Duration if times exist
                        duration = "N/A"
                        if start_time != "N/A" and end_time != "N/A":
                            fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
                            try:
                                t1 = datetime.strptime(start_time, fmt)
                                t2 = datetime.strptime(end_time, fmt)
                                duration = str(t2 - t1)
                                start_time = t1.strftime("%H:%M")
                                end_time = t2.strftime("%H:%M")
                            except:
                                pass

                        details = item.get("details", {})
                        list_price = item.get("listPrice", 0)
                        
                        lat = item.get("map", {}).get("latitude")
                        lon = item.get("map", {}).get("longitude")
                        
                        if lat and lon:
                            valid_coords.append(f"{lon},{lat}")

                        houses.append({
                            "Start Time": start_time,
                            "End Time": end_time,
                            "Duration": duration,
                            "Address": full_address.strip(),
                            "DOM": item.get("daysOnMarket", "N/A"),
                            "Current Price": f"${list_price:,.0f}",
                            "Price Change +/-": "N/A", # Often requires historical query, set to N/A for strictly 1+1=2 current query
                            "Agent & Brokerage": f"{item.get('agents', [{}])[0].get('name', 'Unknown')} - {item.get('office', {}).get('name', 'Unknown')}"
                        })

                    # 2. Optimize Route using Mapbox API
                    if len(valid_coords) > 1 and len(valid_coords) <= 12:
                        coord_string = ";".join(valid_coords)
                        mapbox_url = f"https://api.mapbox.com/optimized-trips/v1/mapbox/driving/{coord_string}?access_token={MAPBOX_KEY}"
                        
                        route_resp = requests.get(mapbox_url)
                        route_resp.raise_for_status()
                        route_data = route_resp.json()
                        
                        # Sort our dataframe based on Mapbox's optimized waypoint index
                        waypoints = route_data.get("waypoints", [])
                        sorted_houses = [None] * len(houses)
                        
                        for idx, wp in enumerate(waypoints):
                            original_index = wp.get("waypoint_index")
                            sorted_houses[original_index] = houses[idx]
                            
                        # Clean up any missed mappings
                        houses = [h for h in sorted_houses if h is not None]

                    elif len(valid_coords) > 12:
                        st.warning("Mapbox optimization is limited to 12 waypoints per request on standard tier. Displaying unoptimized list.")

                    # 3. Display Output and CSV Download
                    df = pd.DataFrame(houses)
                    st.success("Route Optimized!")
                    st.dataframe(df, use_container_width=True)
                    
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Route as CSV",
                        data=csv,
                        file_name=f"route_scoute_{zip_code}_{formatted_date}.csv",
                        mime="text/csv",
                    )

            except Exception as e:
                st.error(f"An error occurred: {e}")
