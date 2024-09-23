import streamlit as st
from requests_oauthlib import OAuth2Session
import requests
import logging
from openai import OpenAI, OpenAIError, APIError, APIConnectionError, RateLimitError
import base64

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# WHOOP API Configuration
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
REDIRECT_URI = 'https://healthartv1.streamlit.app/callback'
AUTH_URL = 'https://api.prod.whoop.com/oauth/oauth2/auth'
TOKEN_URL = 'https://api.prod.whoop.com/oauth/oauth2/token'
API_BASE_URL = 'https://api.prod.whoop.com/developer'

# OpenAI API Configuration
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def token_updater(token):
    st.session_state['oauth_token'] = token

def get_whoop_session():
    token = st.session_state.get('oauth_token')
    if not token:
        return None
    return OAuth2Session(
        CLIENT_ID,
        token=token,
        auto_refresh_url=TOKEN_URL,
        auto_refresh_kwargs={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        },
        token_updater=token_updater
    )

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

def main():
    st.title("Health Art Generator")

    # Check for OAuth callback
    query_params = st.experimental_get_query_params()
    if 'code' in query_params:
        try:
            code = query_params['code'][0]
            whoop = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI)
            token = whoop.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, code=code)
            st.session_state['oauth_token'] = token
            st.success("Successfully authenticated with WHOOP!")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error during authentication: {str(e)}")
            logging.error(f"Authentication error: {str(e)}")
            st.session_state['oauth_token'] = None

    if 'oauth_token' not in st.session_state:
        st.session_state['oauth_token'] = None

    if st.session_state['oauth_token'] is None:
        st.write("Please log in to WHOOP to continue.")
        if st.button("Log in"):
            whoop = OAuth2Session(
                CLIENT_ID,
                redirect_uri=REDIRECT_URI, 
                scope=['read:profile', 'read:recovery', 'read:workout', 'read:sleep']
            )
            authorization_url, state = whoop.authorization_url(AUTH_URL)
            st.session_state['oauth_state'] = state
            st.write(f"Authorization URL: {authorization_url}")
            st.markdown(f"[Click here to authorize]({authorization_url})")
    else:
        whoop = get_whoop_session()
        if not whoop:
            st.write("Failed to get WHOOP session. Please log in again.")
            st.session_state['oauth_token'] = None
            st.experimental_rerun()

        try:
            recovery_resp = whoop.get(f"{API_BASE_URL}/v1/recovery")
            recovery_resp.raise_for_status()
            recovery_data = recovery_resp.json()
            logging.debug(f"Recovery data: {recovery_data}")
        except Exception as e:
            logging.error(f"Error fetching recovery data: {str(e)}")
            st.write("Failed to fetch recovery data.")
            return

        try:
            recovery_score = recovery_data['records'][0]['score']['recovery_score']
            logging.debug(f"Recovery Score: {recovery_score}")
        except (KeyError, IndexError) as e:
            logging.error(f"Error extracting recovery score: {str(e)}")
            st.write("Failed to extract recovery score.")
            return

        art_base64 = generate_ai_art(recovery_score)

        if art_base64 is None:
            logging.error("Failed to generate AI art.")
            st.write("Failed to generate AI art.")
            return

        st.image(f"data:image/png;base64,{art_base64}", caption="Generated AI Art")
        st.write(f"Recovery Score: {recovery_score}")

if __name__ == "__main__":
    main()
