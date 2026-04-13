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
    st.write("### Search Parameters")
    loc_input = st.text_input("Location (e.g. spokane-wa or 99223)", value="spokane-wa")
    
    col1, col2, col3 = st.columns(3)
    with col1: date_1 = st.date_input("Date Option 1", value=None)
    with col2: date_2 = st.date_input("Date Option 2", value=None)
    with col3: date_3 = st.date_input("Date Option 3", value=None)
    
    submit = st.form_submit_button("Fetch Times & Optimize Route")

if submit:
    loc_list = [l.strip() for l in loc_input.split(",") if l.strip()]
    selected_dates = [d.strftime("%Y-%m-%d") for d in [date_1, date_2, date_3] if d]
            
    if not loc_list:
        st.error("Please enter a Location.")
    else:
        with st.spinner("Extracting schedules for 40+ properties..."):
            try:
                houses = []
                valid_coords = []
                debug_log = [] 
                
                for loc in loc_list:
                    # STEP 1: Search for IDs
                    search_url = "https://real-estate101.p.rapidapi.com/api/search"
                    headers = {"x-rapidapi-host": "real-estate101.p.rapidapi.com", "x-rapidapi-key": RAPID_KEY}
                    search_resp = requests.get(search_url, headers=headers, params={"location": loc, "isOpenHousesOnly": "true"})
                    
                    if search_resp.status_code == 200:
                        results = search_resp.json().get("results", [])
                        
                        for item in results:
                            zpid = item.get("id")
                            
                            # STEP 2: Get deep info (Times/Dates)
                            # Using the specific 'property' endpoint seen in your screenshot
                            info_url = "https://real-estate101.p.rapidapi.com/api/property"
                            info_resp = requests.get(info_url, headers=headers, params={"propertyId": zpid})
                            
                            if info_resp.status_code == 200:
                                details = info_resp.json()
                                
                                # Look for open house schedules in the deep data
                                # Zillow scrapers usually hide this in 'openHouseSchedule' or 'attributionInfo'
                                schedule = details.get("openHouseSchedule", [])
                                
                                found_matching_date = False
                                start_t, end_t = "N/A", "N/A"

                                # If no dates selected, we take all. If dates selected, we filter.
                                if not selected_dates:
                                    found_matching_date = True
                                else:
                                    for event in schedule:
                                        # Match 2026-04-18 style dates
                                        if any(d in str(event) for d in selected_dates):
                                            found_matching_date = True
                                            start_t = event.get("startTime", "N/A")
                                            end_t = event.get("endTime", "N/A")
                                            break

                                if found_matching_date:
                                    addr = item.get("address", {})
                                    full_addr = f"{addr.get('street')}, {addr.get('city')}, {addr.get('state')} {addr.get('zipcode')}"
                                    lat_lon = item.get("latLong", {})
                                    
                                    if lat_lon.get("latitude") and lat_lon.get("longitude"):
                                        valid_coords.append(f"{lat_lon['longitude']},{lat_lon['latitude']}")
                                        
                                        houses.append({
                                            "Start Time": start_t,
                                            "End Time": end_t,
                                            "Address": full_addr,
                                            "DOM": item.get("daysOnZillow", "N/A"),
                                            "Price": item.get("price", "N/A"),
                                            "Agent": item.get("brokerName", "N/A")
                                        })
                            else:
                                debug_log.append(f"Failed to get details for {zpid}: {info_resp.status_code}")
                
                if houses:
                    # STEP 3: Mapbox Routing
                    if len(valid_coords) > 1:
                        route_url = f"https://api.mapbox.com/optimized-trips/v1/mapbox/driving/{';'.join(valid_coords[:12])}?access_token={MAPBOX_KEY}"
                        r_resp = requests.get(route_url)
                        if r_resp.status_code == 200:
                            waypoints = r_resp.json().get("waypoints", [])
                            houses = [houses[wp['waypoint_index']] for wp in sorted(waypoints, key=lambda x: x['waypoint_index'])]
                            st.success("Route optimized for drive time!")

                    st.dataframe(pd.DataFrame(houses), use_container_width=True)
                    st.download_button("Download CSV", pd.DataFrame(houses).to_csv(index=False), "route.csv", "text/csv")
                else:
                    st.warning("No properties matched your specific dates. Try leaving dates blank to see all.")

                with st.expander("View System Log"):
                    st.write(debug_log)

            except Exception as e:
                st.error(f"Error: {e}")
