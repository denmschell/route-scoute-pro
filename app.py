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
    submit = st.form_submit_button("Fetch Live Zillow Data")

if submit:
    zip_list = [z.strip() for z in zip_codes_input.split(",") if z.strip()]
    
    if not zip_list:
        st.error("Please enter at least one Zip Code.")
    else:
        with st.spinner("Fetching raw Zillow data..."):
            try:
                houses = []
                raw_api_responses = [] # Store raw data for debugging
                
                for zcode in zip_list:
                    url = "https://us-housing-market-data1.p.rapidapi.com/propertyExtendedSearch"
                    # Broadened search to catch everything for sale
                    querystring = {"location": zcode, "status_type": "ForSale"} 
                    headers = {
                        "X-RapidAPI-Key": RAPID_KEY,
                        "X-RapidAPI-Host": "us-housing-market-data1.p.rapidapi.com"
                    }
                    
                    response = requests.get(url, headers=headers, params=querystring)
                    
                    if response.status_code == 200:
                        data = response.json()
                        props = data.get("props", [])
                        raw_api_responses.append(data) # Save for our debug view
                        
                        for item in props:
                            # Let's aggressively look for ANY sign of an open house in the raw JSON
                            json_str = json.dumps(item).lower()
                            if "open" in json_str or "house" in json_str: 
                                address = item.get("address", "Unknown Address")
                                price = item.get("price", 0)
                                agent = item.get("brokerName", "Unknown Broker")
                                
                                houses.append({
                                    "Address": address,
                                    "Current Price": f"${price:,.0f}",
                                    "Agent & Brokerage": agent,
                                    "Raw API String": str(item)[:150] + "..." # Snippet to see what it contains
                                })
                
                if houses:
                    st.success("Found properties mentioning Open Houses!")
                    df = pd.DataFrame(houses)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.warning("Still no open houses found. The API might be blocking the request or missing data.")

                # DEBUG EXPANDER - This is the crucial part
                with st.expander("🛠️ Debug: Show Raw API Data (Click to Expand)"):
                    st.write("This is exactly what the Zillow API is returning to us behind the scenes:")
                    st.json(raw_api_responses)

            except Exception as e:
                st.error(f"An error occurred: {e}")
