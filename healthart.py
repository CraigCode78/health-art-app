import streamlit as st
import requests
import logging
import secrets
import base64
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# WHOOP API Configuration
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
REDIRECT_URI = 'https://healthartv1.streamlit.app/'  # Ensure this matches WHOOP's developer portal

AUTH_URL = 'https://api.prod.whoop.com/oauth/oauth2/auth'
TOKEN_URL = 'https://api.prod.whoop.com/oauth/oauth2/token'
API_BASE_URL = 'https://api.prod.whoop.com/developer'

# OpenAI API Configuration
openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def generate_state():
    """Generate a secure random state string."""
    return secrets.token_urlsafe(16)

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
    additional_prompt = ""
    if additional_metrics:
        for key, value in additional_metrics.items():
            if key == 'sleep_quality':
                additional_prompt += f" Represent sleep quality with {'soothing' if value > 7 else 'restless'} tones.\n"
            elif key == 'strain':
                additional_prompt += f" Depict strain levels with {'intense' if value > 5 else 'mild'} textures.\n"
            elif key == 'hrv':
                additional_prompt += f" Illustrate HRV with {'complex' if value > 50 else 'simple'} patterns.\n"

    # Combine all prompts
    full_prompt = f"{base_prompt}\n{color_prompt}\n" + "\n".join(pattern_prompt) + "\n" + additional_prompt

    # Generate image using OpenAI's DALL-E
    try:
        response = openai_client.Image.create(
            prompt=full_prompt,
            n=1,
            size="512x512"
        )
        image_url = response['data'][0]['url']
        logging.debug(f"Generated image URL: {image_url}")

        # Fetch the image and encode it in base64
        image_resp = requests.get(image_url)
        image_resp.raise_for_status()
        image_base64 = base64.b64encode(image_resp.content).decode('utf-8')
        return image_base64

    except Exception as e:
        logging.error(f"Error generating AI art: {e}")
        return None

def main():
    # Initialize oauth_token if not present
    if 'oauth_token' not in st.session_state:
        st.session_state.oauth_token = None

    # Initialize oauth_states if not present
    if 'oauth_states' not in st.session_state:
        st.session_state.oauth_states = {}

    # Retrieve query parameters
    query_params = st.query_params

    # Handle OAuth callback
    if 'code' in query_params and 'state' in query_params:
        received_code = query_params.get('code', [None])[0]
        received_state = query_params.get('state', [None])[0]

        logging.debug(f"Received code: {received_code}")
        logging.debug(f"Received state: {received_state}")

        if not received_state:
            st.error("State parameter is missing.")
            logging.error("State parameter is missing in the callback.")
        elif received_state not in st.session_state.oauth_states:
            st.error("Invalid state parameter. Potential CSRF attack detected.")
            logging.error(f"Invalid state parameter: received {received_state}, expected one of {list(st.session_state.oauth_states.keys())}")
            st.session_state.oauth_token = None
        else:
            # Valid state; proceed to exchange code for token
            try:
                token_data = {
                    'grant_type': 'authorization_code',
                    'code': received_code,
                    'redirect_uri': REDIRECT_URI,
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET
                }
                logging.debug(f"Token request data: {token_data}")
                token_response = requests.post(TOKEN_URL, data=token_data)
                token_response.raise_for_status()
                token = token_response.json()
                st.session_state.oauth_token = token
                st.success("Successfully authenticated with WHOOP!")

                # Clean up used state
                del st.session_state.oauth_states[received_state]

                # Clear query parameters to prevent re-processing
                st.experimental_set_query_params()

            except requests.exceptions.RequestException as e:
                st.error(f"Error fetching token: {str(e)}")
                logging.error(f"Error fetching token: {str(e)}")
                if hasattr(e, 'response') and e.response is not None:
                    logging.error(f"Response content: {e.response.content}")
            except Exception as e:
                st.error(f"Unexpected error: {str(e)}")
                logging.error(f"Unexpected error: {str(e)}")

    # If not authenticated, show login button
    if not st.session_state.oauth_token:
        if st.button("Log in with WHOOP"):
            # Generate and store state
            oauth_state = generate_state()
            st.session_state.oauth_states[oauth_state] = True  # Mark state as valid
            logging.debug(f"Generated OAuth state: {oauth_state}")

            # Construct authorization URL
            auth_url = (
                f"{AUTH_URL}?"
                f"client_id={CLIENT_ID}&"
                f"response_type=code&"
                f"redirect_uri={REDIRECT_URI}&"
                f"state={oauth_state}"
            )
            logging.debug(f"Authorization URL: {auth_url}")

            # Provide a clickable link
            st.markdown(f"Please [authorize]({auth_url}) to continue.", unsafe_allow_html=True)

    else:
        st.write("You are already authenticated.")
        # Optional: Add logout functionality
        if st.button("Logout"):
            st.session_state.oauth_token = None
            st.success("Logged out successfully.")

        # Fetch WHOOP data and generate AI art
        try:
            # Use the access token to fetch WHOOP data
            headers = {
                'Authorization': f"Bearer {st.session_state.oauth_token['access_token']}"
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
            if hasattr(e, 'response') and e.response is not None:
                logging.error(f"Response content: {e.response.content}")
        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")
            logging.error(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    main()