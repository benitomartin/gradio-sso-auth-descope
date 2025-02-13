import gradio as gr
from flask import Flask, request, redirect
from descope import DescopeClient, DeliveryMethod, AuthException
import os
from dotenv import load_dotenv
from threading import Thread
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Descope Client Setup
PROJECT_ID = os.getenv("PROJECT_ID")
if not PROJECT_ID:
    raise ValueError("PROJECT_ID environment variable is not set")

descope_client = DescopeClient(project_id=PROJECT_ID)

# Flask app setup
app = Flask(__name__)

# Constants for URLs
GRADIO_PORT = 7860
FLASK_PORT = 5000
BASE_URL = f"http://127.0.0.1:{GRADIO_PORT}"
FLASK_URL = f"http://127.0.0.1:{FLASK_PORT}"

# Function to send magic link
def send_magic_link(email):
    try:
        # Generate magic link via Descope's API
        descope_client.magiclink.sign_up_or_in(
            method=DeliveryMethod.EMAIL,
            login_id=email,
            uri=f"{FLASK_URL}/verify-magic"  # Redirect URI for magic link verification
        )
        return f"Magic link sent to {email}! Please check your inbox."
    except Exception as e:
        return f"Error sending magic link: {str(e)}"

# Function to start SSO flow
def start_sso_flow(tenant_id):
    logger.info(f"Starting SSO flow for tenant ID: {tenant_id}")
    
    if not tenant_id:
        logger.error("Tenant ID is missing")
        return gr.update(), "Please provide a tenant ID."

    try:
        return_url = f"{FLASK_URL}/verify-sso"
        logger.info(f"Configured return URL: {return_url}")
                
        # Start SSO flow
        sso_response = descope_client.sso.start(tenant=tenant_id, return_url=return_url)
        logger.info("SSO flow initiated successfully")
        logger.debug(f"SSO Response: {sso_response}")
        
        return gr.update(value=""), "SSO flow started. Please continue with Okta authentication."
            
    except AuthException as error:
        logger.error(f"Authentication failed: {error.error_message}")
        return gr.update(), f"Authentication Error: {error.error_message}"
    except Exception as e:
        logger.error(f"Unexpected error during SSO flow: {str(e)}", exc_info=True)
        return gr.update(), f"Error: {str(e)}"

# Function to start OAuth flow
def start_oauth_flow():
    try:
        return_url = f"{FLASK_URL}/verify-oauth"
        logger.info(f"Configured return URL: {return_url}")
        
        # Start OAuth flow      
        oauth_response = descope_client.oauth.start(provider="google", return_url=return_url)
        logger.info("OAuth flow initiated successfully")
        logger.debug(f"OAuth Response: {oauth_response}")

        return "OAuth flow started. Please continue with Google authentication."
            
    except AuthException as error:
        logger.error(f"Authentication failed: {error.error_message}")
        return f"Authentication Error: {error.error_message}"
    except Exception as e:
        logger.error(f"Unexpected error during OAuth flow: {str(e)}", exc_info=True)
        return f"Error: {str(e)}"

@app.route('/verify-magic')
def verify_magic_link():
    token = request.args.get('t')

    if not token:
        return "Error: Token is missing from the URL", 400

    try:
        # Verify the token with Descope
        user_response = descope_client.magiclink.verify(token)
        session_token = user_response.get('sessionToken')

        if not session_token:
            raise AuthException("Failed to retrieve session token.")

        # Redirect to Gradio app with session token
        return redirect(f'{BASE_URL}/?auth_type=magic&session_token={session_token}')

    except AuthException as e:
        return f"Authentication error: {str(e)}", 400
    except Exception as e:
        return f"Error verifying magic link: {str(e)}", 500

@app.route('/verify-sso')
def verify_sso():
    code = request.args.get('code')
    error = request.args.get('error')
    error_description = request.args.get('error_description')
    
    logger.info(f"Received SSO callback. Code present: {bool(code)}")
    
    if error or error_description:
        logger.error(f"SSO Error: {error} - {error_description}")
        return f"Authentication Error: {error_description}", 400
    
    if not code:
        logger.error("Missing code parameter in callback")
        return "Error: Missing code parameter.", 400

    try:
        # Exchange the code for session tokens
        jwt_response = descope_client.sso.exchange_token(code)
        
        session_token = jwt_response["sessionToken"].get("jwt")
        refresh_token = jwt_response["refreshSessionToken"].get("jwt")

        if not session_token or not refresh_token:
            logger.error("Missing tokens in response")
            return "Error: Invalid token response", 400

        logger.info("Session validated and tokens extracted")
        # Redirect to Gradio interface with session tokens
        return redirect(f'{BASE_URL}/?auth_type=sso&session_token={session_token}&refresh_token={refresh_token}')
    
    except Exception as e:
        logger.error(f"Token exchange failed: {str(e)}", exc_info=True)
        return f"Error: {str(e)}", 400

@app.route('/verify-oauth')
def verify_oauth():
    code = request.args.get('code')
    error = request.args.get('error')
    error_description = request.args.get('error_description')
    
    logger.info(f"Received OAuth callback. Code present: {bool(code)}")
    
    if error or error_description:
        logger.error(f"OAuth Error: {error} - {error_description}")
        return f"Authentication Error: {error_description}", 400
    
    if not code:
        logger.error("Missing code parameter in callback")
        return "Error: Missing code parameter.", 400

    try:
        # Exchange the code for session tokens
        logger.info("Attempting to exchange code for tokens")
        jwt_response = descope_client.oauth.exchange_token(code)
        
        session_token = jwt_response["sessionToken"].get("jwt")
        refresh_token = jwt_response["refreshSessionToken"].get("jwt")
        
        if not session_token or not refresh_token:
            logger.error("Missing tokens in response")
            return "Error: Invalid token response", 400

        logger.info("Session validated and tokens extracted")
        # Redirect to Gradio interface with session tokens
        return redirect(f'{BASE_URL}/?auth_type=oauth&session_token={session_token}&refresh_token={refresh_token}')
    
    except Exception as e:
        logger.error(f"Token exchange failed: {str(e)}", exc_info=True)
        return f"Error: {str(e)}", 400

def get_token_and_update_state(stored_state: gr.BrowserState, request: gr.Request):
    try:
        query_params = dict(request.query_params)
        if query_params:
            auth_type = query_params.get('auth_type')
            session_token = query_params.get('session_token')
            refresh_token = query_params.get('refresh_token')

            if session_token:
                stored_state[0] = session_token
                stored_state[1] = refresh_token if refresh_token else ""
                stored_state[2] = auth_type if auth_type else "magic"

                return (
                    gr.update(visible=False),  # Hide login page
                    gr.update(visible=True),   # Show main page
                    f"Successfully logged in via {stored_state[2]}!",
                    stored_state
                )
                
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        
    return load_stored_session(stored_state)

def create_login_page():
    with gr.Column(visible=True) as login_page:
        gr.Markdown("## Authentication Options")
        
        with gr.Tab("Magic Link"):
            email = gr.Textbox(label="Enter your email")
            magic_link_button = gr.Button("Send Magic Link")
            magic_link_message = gr.Textbox(label="Status", interactive=False)
            
        with gr.Tab("SSO"):
            tenant_input = gr.Textbox(label="Tenant ID", placeholder="Enter your Okta tenant ID")
            sso_button = gr.Button("Start SSO Authentication")
            sso_message = gr.Textbox(label="Status", interactive=False)
            
        with gr.Tab("OAuth"):
            gr.Markdown("## Google OAuth Authentication")
            oauth_button = gr.Button("Sign in with Google")
            oauth_message = gr.Textbox(label="Status", interactive=False)
            
    return login_page, email, magic_link_button, magic_link_message, tenant_input, sso_button, sso_message, oauth_button, oauth_message

def create_main_page():
    with gr.Column(visible=False) as main_page:
        gr.Markdown("## Welcome to the Main Page")
        gr.Markdown("You have successfully logged in!")
        gr.Textbox(label="Example Feature", value="This is the main application page")
        logout_button = gr.Button("Logout")
    return main_page, logout_button

def load_stored_session(stored_state):
    if stored_state[0]:  # If session_token exists
        auth_type = stored_state[2] if stored_state[2] else "unknown"
        return (
            gr.update(visible=False),  # Hide login page
            gr.update(visible=True),   # Show main page
            f"Welcome back! ({auth_type} authentication)",
            stored_state
        )
    return (
        gr.update(visible=True),      # Show login page
        gr.update(visible=False),     # Hide main page
        "",                           # Clear message
        stored_state
    )

def logout_user(stored_state: gr.BrowserState):
    stored_state[0] = ""  # Clear session token
    stored_state[1] = ""  # Clear refresh token
    stored_state[2] = ""  # Clear auth type

    return (
        gr.update(visible=True),       # Show login page
        gr.update(visible=False),      # Hide main page
        "You have been logged out.",   # Show logout message
        stored_state
    )

def create_app():
    with gr.Blocks() as app:
        # BrowserState stores [session_token, refresh_token, auth_type]
        stored_state = gr.BrowserState(["", "", ""])

        # Create pages and components
        login_page, email, magic_link_button, magic_link_message, tenant_input, sso_button, sso_message, oauth_button, oauth_message = create_login_page()
        main_page, logout_button = create_main_page()

        # Handle magic link authentication
        magic_link_button.click(
            fn=send_magic_link,
            inputs=[email],
            outputs=[magic_link_message]
        )

        # Handle SSO authentication
        sso_button.click(
            fn=start_sso_flow,
            inputs=[tenant_input],
            outputs=[tenant_input, sso_message]
        )

        # Handle OAuth authentication
        oauth_button.click(
            fn=start_oauth_flow,
            inputs=[],
            outputs=[oauth_message]
        )

        # Handle page load/refresh and token capture
        app.load(
            fn=get_token_and_update_state,
            inputs=[stored_state],
            outputs=[login_page, main_page, magic_link_message, stored_state]
        )

        # Handle logout button click
        logout_button.click(
            fn=logout_user,
            inputs=[stored_state],
            outputs=[login_page, main_page, magic_link_message, stored_state]
        )

    return app

if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = Thread(target=lambda: app.run(host="127.0.0.1", port=FLASK_PORT, debug=False, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()

    # Start Gradio app
    logger.info("Starting Gradio interface")
    gradio_app = create_app()
    gradio_app.launch(server_name="127.0.0.1", server_port=GRADIO_PORT, share=False)