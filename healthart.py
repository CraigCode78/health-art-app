import streamlit as st
import requests
import logging
from openai import OpenAI
import secrets
import base64

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# WHOOP API Configuration
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
REDIRECT_URI = 'https://healthartv1.streamlit.app/'  # Ensure this matches the WHOOP developer portal
AUTH_URL = 'https://api.prod.whoop.com/oauth/oauth2/auth'
TOKEN_URL = 'https://api.prod.whoop.com/oauth/oauth2/token'
API_BASE_URL = 'https://api.prod.whoop.com/developer'

# OpenAI API Configuration
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def generate_ai_art(recovery_score, additional_metrics=None):
    """
    Generate abstract AI art based on health data using OpenAI's DALL-E.

    Args:
        recovery_score (float): The primary recovery score (0-100).
        additional_metrics (dict): Optional additional health metrics.

    Returns:
        str: Base64-encoded image data or None if generation fails.
    """
    # Base prompt structure
    base_prompt = "Create an abstract digital artwork representing health data with the following elements:"

    # Color representation based on recovery score
    if recovery_score > 80:
        color_prompt = f"Dominant colors are vibrant greens and blues, representing high recovery ({recovery_score}% recovery score)."
    elif recovery_score > 50:
        color_prompt = f"Mix of warm yellows and cool blues, balancing moderate recovery ({recovery_score}% recovery score)."
    else:
        color_prompt = f"Subdued reds and greys dominate, indicating low recovery ({recovery_score}% recovery score)."

    # Pattern and shape elements
    pattern_prompt = [
        "Incorporate flowing, organic shapes to represent flexibility and adaptability.",
        "Use repeating geometric patterns, with their regularity affected by the recovery score.",
        f"{'Dense' if recovery_score > 70 else 'Sparse'} network of interconnected lines symbolizing bodily systems.",
        f"Abstract {'circular' if recovery_score > 60 else 'angular'} forms representing energy levels."
    ]

    # Additional metric representations
    metric_prompts = []
    if additional_metrics:
        if 'sleep_quality' in additional_metrics:
            sleep_quality = additional_metrics['sleep_quality']
            metric_prompts.append(f"Represent sleep quality ({sleep_quality}%) with {'smooth' if sleep_quality > 70 else 'jagged'} wave-like patterns.")
        if 'strain' in additional_metrics:
            strain = additional_metrics['strain']
            metric_prompts.append(f"Illustrate physical strain ({strain}/21) with {'bold' if strain > 15 else 'subtle'} textural elements.")
        if 'hrv' in additional_metrics:
            hrv = additional_metrics['hrv']
            metric_prompts.append(f"Depict heart rate variability ({hrv} ms) using {'intricate' if hrv > 50 else 'simple'} fractal-like structures.")

    # Combine all elements into a final prompt
    final_prompt = f"{base_prompt} {color_prompt} {' '.join(pattern_prompt)} {' '.join(metric_prompts)} The overall composition should be harmonious yet dynamic, clearly reflecting the health status through abstract visual elements."

    # Use OpenAI's DALL-E to generate the art
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=final_prompt,
            n=1,
            size="1024x1024",
            quality="standard",
            response_format="b64_json"
        )
        logging.debug(f"OpenAI response: {response}")
        image_data = response.data[0].b64_json
        return image_data
    except Exception as e:
        logging.error(f"Error generating art: {str(e)}")
        return None

def generate_state():
    return secrets.token_urlsafe(16)

def main():
    st.title("Health Art Generator")

    # Initialize session state
    if 'oauth_state' not in st.session_state:
        st.session_state.oauth_state = generate_state()
    if 'oauth_token' not in st.session_state:
        st.session_state.oauth_token = None

    # Retrieve query parameters
    query_params = st.query_params

    # Handle OAuth callback
    if 'code' in query_params and 'state' in query_params:
        received_state = query_params['state'][0]
        expected_state = st.session_state.get('oauth_state')

        if received_state != expected_state:
            st.error("Invalid state parameter. Potential CSRF attack detected.")
            logging.error("Invalid state parameter")
            st.session_state.oauth_token = None
        else:
            try:
                code = query_params['code'][0]
                token_data = {
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': REDIRECT_URI,
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET
                }
                token_response = requests.post(TOKEN_URL, data=token_data)
                token_response.raise_for_status()
                token = token_response.json()
                st.session_state.oauth_token = token
                st.success("Successfully authenticated with WHOOP!")
                st.rerun()  # Trigger a rerun to update the UI
            except requests.exceptions.RequestException as e:
                st.error(f"Error during authentication: {str(e)}")
                logging.error(f"Authentication error: {str(e)}")
                if hasattr(e, 'response') and e.response is not None:
                    logging.error(f"Response content: {e.response.content}")
                st.session_state.oauth_token = None

    # If not authenticated, show login button
    if st.session_state.oauth_token is None:
        st.write("Please log in to WHOOP to continue.")
        if st.button("Log in"):
            # Regenerate state for each login attempt to enhance security
            st.session_state.oauth_state = generate_state()
            auth_url = (
                f"{AUTH_URL}?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&state={st.session_state.oauth_state}"
            )
            st.markdown(f"[Click here to authorize]({auth_url})")
    else:
        # Proceed with fetching WHOOP data and generating art
        try:
            access_token = st.session_state.oauth_token['access_token']
            headers = {"Authorization": f"Bearer {access_token}"}
            
            recovery_resp = requests.get(f"{API_BASE_URL}/v1/recovery", headers=headers)
            recovery_resp.raise_for_status()
            recovery_data = recovery_resp.json()
            logging.debug(f"Recovery data: {recovery_data}")

            # Extract recovery score
            recovery_score = recovery_data['records'][0]['score']['recovery_score']
            logging.debug(f"Recovery Score: {recovery_score}")

            # Optionally, extract additional metrics if available
            additional_metrics = {}
            if 'records' in recovery_data and len(recovery_data['records']) > 0:
                metrics = recovery_data['records'][0].get('metrics', {})
                additional_metrics = {
                    key: value for key, value in metrics.items() if key in ['sleep_quality', 'strain', 'hrv']
                }

            # Generate AI art based on recovery score and additional metrics
            art_base64 = generate_ai_art(recovery_score, additional_metrics)

            if art_base64 is None:
                st.write("Failed to generate AI art.")
            else:
                st.image(f"data:image/png;base64,{art_base64}", caption="Generated AI Art")
                st.write(f"Recovery Score: {recovery_score}")

        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching WHOOP data: {str(e)}")
            logging.error(f"Error fetching WHOOP data: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logging.error(f"Response content: {e.response.content}")
        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")
            logging.error(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    main()
