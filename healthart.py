import streamlit as st
from streamlit_oauth import OAuth2Component
import requests
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

# Load OAuth configuration from secrets
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]
AUTH_URL = st.secrets["AUTH_URL"]
TOKEN_URL = st.secrets["TOKEN_URL"]
REFRESH_TOKEN_URL = st.secrets["REFRESH_TOKEN_URL"]
REVOKE_TOKEN_URL = st.secrets["REVOKE_TOKEN_URL"]
SCOPE = st.secrets["SCOPE"]
API_BASE_URL = st.secrets["API_BASE_URL"]

def generate_ai_art(recovery_score, additional_metrics):
    """
    Placeholder function to generate AI art based on WHOOP data.
    Replace this with your actual implementation.
    """
    # Example: Return a base64-encoded image string
    return None  # Replace with actual AI art generation logic

def main():
    st.title("HealthArt - WHOOP OAuth Integration")
    
    # Initialize OAuth2Component
    oauth2 = OAuth2Component(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        authorize_url=AUTH_URL,
        token_url=TOKEN_URL,
        refresh_url=REFRESH_TOKEN_URL,
        revoke_url=REVOKE_TOKEN_URL,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE
    )
    
    # Check if the user is authenticated
    if 'oauth_token' not in st.session_state:
        # If not authenticated, show the authorize button
        result = oauth2.authorize_button("Authorize with WHOOP")
        if result and 'access_token' in result:
            st.session_state.oauth_token = result.get('access_token')
            st.success("Successfully authenticated with WHOOP!")
            logging.debug(f"Access Token: {st.session_state.oauth_token}")
    else:
        # If authenticated, display token details and provide options
        st.write("You are already authenticated.")
        
        # Display the access token (for debugging purposes)
        # In production, avoid displaying sensitive information
        st.json({"access_token": st.session_state['oauth_token']})
        
        # Fetch WHOOP data and generate AI art
        try:
            # Use the access token to fetch WHOOP data
            headers = {
                'Authorization': f"Bearer {st.session_state.oauth_token}"
            }
            logging.debug(f"Fetching WHOOP data with headers: {headers}")
            recovery_resp = requests.get(f"{API_BASE_URL}/v1/recovery", headers=headers)
            recovery_resp.raise_for_status()
            recovery_data = recovery_resp.json()
            logging.debug(f"Recovery data: {recovery_data}")
    
            # Extract recovery score
            if 'records' in recovery_data and len(recovery_data['records']) > 0:
                recovery_score = recovery_data['records'][0]['score']['recovery_score']
                logging.debug(f"Recovery Score: {recovery_score}")
            else:
                st.error("No recovery data available.")
                logging.error("No recovery data found in the response.")
                recovery_score = None
    
            # Optionally, extract additional metrics if available
            additional_metrics = {}
            if 'records' in recovery_data and len(recovery_data['records']) > 0:
                metrics = recovery_data['records'][0].get('metrics', {})
                additional_metrics = {
                    key: value for key, value in metrics.items() if key in ['sleep_quality', 'strain', 'hrv']
                }
    
            # Generate AI art based on recovery score and additional metrics
            if recovery_score is not None:
                art_base64 = generate_ai_art(recovery_score, additional_metrics)
    
                if art_base64 is None:
                    st.write("Failed to generate AI art.")
                else:
                    st.image(f"data:image/png;base64,{art_base64}", caption="Generated AI Art")
                    st.write(f"**Recovery Score:** {recovery_score}")
            else:
                st.write("Cannot generate AI art without a valid recovery score.")
    
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching WHOOP data: {str(e)}")
            logging.error(f"Error fetching WHOOP data: {str(e)}")
        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")
            logging.error(f"Unexpected error: {str(e)}")
        
        # Logout functionality
        if st.button("Logout"):
            oauth2.revoke_token(st.session_state['oauth_token'])
            del st.session_state.oauth_token
            st.success("Logged out successfully.")
            st.experimental_set_query_params()
    
if __name__ == "__main__":
    main()