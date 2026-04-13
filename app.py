import streamlit as st
import requests
import pandas as pd
import json

# Page Config
st.set_page_config(page_title="Route Scoute Pro", layout="wide")
st.title("Route Scoute Pro 🚗")
st.write("Optimized Open House Route")

# Securely load API Keys from Streamlit Secrets
RAPID_KEY = st.secrets["RAPID_API_KEY"]
MAPBOX_KEY = st.secrets["MAPBOX_API_KEY"]

with st.form("input_form"):
    st.write("### Zip Code Search")
    zip_input = st.text_input("Enter Zip Codes (separate by commas)", value="")
    submit = st.form_submit_button("Generate Optimized Route")

if submit:
    zip_list = [z.strip() for z in zip_input.split(",") if z.strip()]
            
    if not zip_list:
        st.error("Please enter at least one Zip Code.")
    else:
        with st.spinner("Fetching listings and optimizing drive path..."):
            try:
                houses = []
                coords = []
                
                for zcode in zip_list:
                    url = "https://real-estate101.p.rapidapi.com/api/search"
                    headers = {
                        "x-rapidapi-host": "real-estate101.p.rapidapi.com", 
                        "x-rapidapi-key": RAPID_KEY
                    }
                    params = {"location": zcode, "isOpenHousesOnly": "true"}
                    
                    resp = requests.get(url, headers=headers, params=params)
                    
                    if resp.status_code == 200:
                        results = resp.json().get("results", [])
                        for item in results:
                            addr = item.get("address", {})
                            full_addr = f"{addr.get('street')}, {addr.get('city')}, {addr.get('state')} {addr.get('zipcode')}"
                            lat_lon = item.get("latLong", {})
                            lat, lon = lat_lon.get("latitude"), lat_lon.get("longitude")
                            
                            if lat and lon:
                                coords.append(f"{lon},{lat}")
                                houses.append({
                                    "Address": full_addr,
                                    "Price": item.get("price", "N/A"),
                                    "DOM": item.get("daysOnZillow", "N/A"),
                                    "Agent/Brokerage": item.get("brokerName", "N/A"),
                                    "Link": item.get("detailUrl", "N/A")
                                })

                if houses:
                    # MAPBOX OPTIMIZATION
                    if len(coords) > 1:
                        # Limit to 12 stops for Mapbox Free Tier
                        route_coords = ";".join(coords[:12])
                        mapbox_url = f"https://api.mapbox.com/optimized-trips/v1/mapbox/driving/{route_coords}"
                        route_resp = requests.get(mapbox_url, params={"access_token": MAPBOX_KEY})
                        
                        if route_resp.status_code == 200:
                            waypoints = route_resp.json().get("waypoints", [])
                            # Re-order the list based on the optimal driving sequence
                            optimized_list = [None] * len(waypoints)
                            for wp in waypoints:
                                optimized_list[wp['waypoint_index']] = houses[wp['location_index']]
                            houses = [h for h in optimized_list if h is not None]
                            st.success("Drive route optimized!")

                    # Output
                    df = pd.DataFrame(houses)
                    st.dataframe(df, use_container_width=True)
                    st.download_button("Download CSV", df.to_csv(index=False), "route.csv", "text/csv")
                else:
                    st.warning("No open houses found in these zip codes today.")

            except Exception as e:
                st.error(f"Error: {e}")
