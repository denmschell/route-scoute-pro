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
    else:
        with st.spinner("Fetching listings and extracting specific Open House times..."):
            try:
                houses = []
                valid_coords = []
                raw_info_responses = [] # Added back for debugging the 2nd API call
                
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
                                info_qs = {"zpid": property_id} 
                                
                                info_resp = requests.get(info_url, headers=headers, params=info_qs)
                                
                                start_time = "N/A"
                                end_time = "N/A"
                                date_matches = False
                                
                                if info_resp.status_code == 200:
                                    info_data = info_resp.json()
                                    raw_info_responses.append(info_data) # Save for our debug log
                                    
                                    # Convert the entire property dump to a string to aggressively check for dates
                                    info_str = json.dumps(info_data).lower()
                                    
                                    if not selected_dates or any(target_date in
