import os
from flask import Flask, redirect, request, session, jsonify, url_for, render_template
from requests_oauthlib import OAuth2Session
import requests
import logging
from openai import OpenAI, OpenAIError, APIError, APIConnectionError, RateLimitError
import base64

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY')  # Updated to use environment variable

# WHOOP API Configuration
CLIENT_ID = os.environ.get('WHOOP_CLIENT_ID')  # Updated to use environment variable
CLIENT_SECRET = os.environ.get('WHOOP_CLIENT_SECRET')  # Updated to use environment variable
REDIRECT_URI = 'http://127.0.0.1:3030/callback'
AUTH_URL = 'https://api.prod.whoop.com/oauth/oauth2/auth'
TOKEN_URL = 'https://api.prod.whoop.com/oauth/oauth2/token'
API_BASE_URL = 'https://api.prod.whoop.com/developer'

# OpenAI API Configuration
# Note: API keys are hard-coded for testing purposes. Ensure to secure them in production.
client = OpenAI(api_key='OPENAI_API_KEY')

# Configure logging
logging.basicConfig(level=logging.DEBUG)

def token_updater(token):
    session['oauth_token'] = token

def get_whoop_session():
    token = session.get('oauth_token')
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    whoop = OAuth2Session(
        CLIENT_ID,
        redirect_uri=REDIRECT_URI, 
        scope=['read:profile', 'read:recovery', 'read:workout', 'read:sleep']
    )
    authorization_url, state = whoop.authorization_url(AUTH_URL)
    session['oauth_state'] = state
    logging.info(f"Authorization URL: {authorization_url}")
    logging.info(f"State: {state}")
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    whoop = OAuth2Session(
        CLIENT_ID,
        state=session.get('oauth_state'),
        redirect_uri=REDIRECT_URI
    )
    try:
        # Modify fetch_token to use client_secret_post by setting auth to None
        token = whoop.fetch_token(
            TOKEN_URL,
            authorization_response=request.url,
            include_client_id=True,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            method='POST',
            auth=None,  # Disable client_secret_basic
            state=session.get('oauth_state')
        )
    except Exception as e:
        logging.error(f"Error fetching token: {e}")
        return jsonify({"error": "Authentication failed"}), 500

    token_updater(token)
    return redirect(url_for('health_art'))

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

@app.route('/health_art')
def health_art():
    whoop = get_whoop_session()
    if not whoop:
        return redirect(url_for('login'))

    # Change the HTTP method from POST to GET as per WHOOP API documentation
    try:
        recovery_resp = whoop.get(f"{API_BASE_URL}/v1/recovery")
        recovery_resp.raise_for_status()
        recovery_data = recovery_resp.json()
        logging.debug(f"Recovery data: {recovery_data}")
    except Exception as e:
        logging.error(f"Error fetching recovery data: {str(e)}")
        return jsonify({"error": "Failed to fetch recovery data"}), 500

    # Extract the recovery score from the response
    try:
        recovery_score = recovery_data['records'][0]['score']['recovery_score']
        logging.debug(f"Recovery Score: {recovery_score}")
    except (KeyError, IndexError) as e:
        logging.error(f"Error extracting recovery score: {str(e)}")
        return jsonify({"error": "Failed to extract recovery score"}), 500

    # Generate the AI art
    art_base64 = generate_ai_art(recovery_score)

    if art_base64 is None:
        logging.error("Failed to generate AI art.")
        return jsonify({"error": "Failed to generate AI art"}), 500

    # Render the HTML template with the art and recovery score
    return render_template('health_art.html', recovery_score=recovery_score, art_base64=art_base64)

@app.route('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='favicon.ico'))

@app.errorhandler(404)
def page_not_found(e):
    logging.error(f"Page not found: {e}")
    return jsonify(error="Page not found"), 404

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"An unexpected error occurred: {e}")
    return jsonify(error=str(e)), 500

if __name__ == '__main__':
    app.run()