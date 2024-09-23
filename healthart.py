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
            metric_prompts.append(f"Depict strain ({strain}%) with compact, intertwined lines.")
        if 'hrv' in additional_metrics:
            hrv = additional_metrics['hrv']
            metric_prompts.append(f"Visualize HRV ({hrv}) with fluctuating rhythms in the artwork.")

    # Compile the full prompt
    full_prompt = base_prompt + " " + color_prompt + " " + " ".join(pattern_prompt)
    if metric_prompts:
        full_prompt += " " + " ".join(metric_prompts)

    logging.debug(f"AI Art Generation Prompt: {full_prompt}")

    # Call OpenAI's API to generate the image
    try:
        response = client.Image.create(
            prompt=full_prompt,
            n=1,
            size="512x512"
        )
        image_url = response['data'][0]['url']
        logging.debug(f"Generated Image URL: {image_url}")

        # Fetch the image content
        image_resp = requests.get(image_url)
        image_resp.raise_for_status()
        image_bytes = image_resp.content

        # Encode image in base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        return image_base64

    except Exception as e:
        logging.error(f"Error generating AI art: {e}")
        return None

def generate_state():
    return secrets.token_urlsafe(16)

def main():
    st.title("Health Art Generator")

    # Initialize session state variables
    if 'oauth_state' not in st.session_state:
        st.session_state.oauth_state = ''
    if 'oauth_token' not in st.session_state:
        st.session_state.oauth_token = None

    # Retrieve query parameters
    query_params = st.query_params

    if 'code' in query_params and 'state' in query_params:
        received_code = query_params['code'][0]
        received_state = query_params['state'][0]

        if not received_state:
            st.error("State parameter is missing.")
            logging.error("State parameter is missing in the callback.")
        elif received_state != st.session_state.oauth_state:
            st.error("Invalid state parameter. Potential CSRF attack detected.")
            logging.error(f"Invalid state parameter: received {received_state}, expected {st.session_state.oauth_state}")
            st.session_state.oauth_token = None
        else:
            try:
                # Exchange authorization code for access token
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
            if not st.session_state.oauth_state:
                # Generate and store state
                oauth_state = generate_state()
                st.session_state.oauth_state = oauth_state
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

                # Optional: Uncomment the following lines if you want to redirect automatically
                # Ensure proper indentation and string encapsulation

                # import streamlit.components.v1 as components
                # components.html(
                #     f"""
                #     <script>
                #         window.location.href = '{auth_url}';
                #     </script>
                #     """,
                #     height=0,
                # )

    else:
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

        # Optional: Logout button
        if st.session_state.oauth_token:
            if st.button("Logout"):
                st.session_state.oauth_token = None
                st.session_state.oauth_state = ''
                st.success("Logged out successfully.")

if __name__ == "__main__":
    main()