import gradio as gr
import os
from dotenv import load_dotenv
from descope import DescopeClient, AuthException
from flask import Flask, request, redirect
from threading import Thread
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Descope Client Setup
PROJECT_ID = os.getenv("PROJECT_ID")
if not PROJECT_ID:
    raise ValueError("PROJECT_ID environment variable is not set")

descope_client = DescopeClient(project_id=PROJECT_ID)

# Flask app setup
app_flask = Flask(__name__)

def start_sso_flow(tenant_id):
    """Start the SSO authentication flow for a specific tenant"""
    logger.info(f"Starting SSO flow for tenant ID: {tenant_id}")
    
    if not tenant_id:
        logger.error("Tenant ID is missing")
        return gr.update(), "Please provide a tenant ID."

    try:
        return_url = "http://127.0.0.1:7863/handle-sso"
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

@app_flask.route('/handle-sso', methods=['GET'])
def handle_sso():
    """Handle the redirect from Descope with the 'code' parameter"""
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
        logger.info("Attempting to exchange code for tokens")
        jwt_response = descope_client.sso.exchange_token(code)
        
        session_token = jwt_response["sessionToken"].get("jwt")
        refresh_token = jwt_response["refreshSessionToken"].get("jwt")
        
        custom_jwt = descope_client.validate_session(session_token)
        print(f"Session Token Validated: {custom_jwt}")

        if not session_token or not refresh_token:
            logger.error("Missing tokens in response")
            return "Error: Invalid token response", 400

        logger.info("Session validated and tokens extracted")
        # Redirect to Gradio interface with session tokens
        return redirect(f'http://127.0.0.1:7864/?success=true&session_token={session_token}&refresh_token={refresh_token}')
    
    except Exception as e:
        logger.error(f"Token exchange failed: {str(e)}", exc_info=True)
        return f"Error: {str(e)}", 400


def get_token_and_update_state(stored_state: gr.BrowserState, request: gr.Request):
    """
    Function to handle token capture and state updates
    Takes only stored_state as input to comply with Gradio's requirements
    Uses the request context internally
    """
    try:
        # Get current request context
        query_params = dict(request.query_params)
        print(query_params)
        if query_params:
            # Extract token from query parameters
            session_token = query_params.get('session_token')
            refresh_token = query_params.get('refresh_token')

            if session_token and refresh_token:
                
                stored_state[0] = session_token
                stored_state[1] = refresh_token

                
                print(f"session_token state: {stored_state[0]}")    # If there's a session token stored, show main page             
                print(f"refresh_token state: {stored_state[1]}")    # If there's a session token stored, show main page

                return (
                    gr.update(visible=False),  # Hide login page
                    gr.update(visible=True),   # Show main page
                    f"Successfully logged in!",  # Success message
                    stored_state  # Updated state
                )
    except Exception as e:
        print(f"Error processing request: {e}")
        
        # Default return if no token or error
    return load_stored_session(stored_state)


# Function to create the login page
def create_login_page():
    with gr.Column(visible=True) as login_page:
        gr.Markdown("## Okta SSO Authentication")
        tenant_input = gr.Textbox(label="Tenant ID", placeholder="Enter your Okta tenant ID")
        sso_button = gr.Button("Start SSO Authentication")
        sso_message_output = gr.Textbox(label="Status", interactive=False)
    return login_page, tenant_input, sso_button, sso_message_output

# Function to create the main application page
def create_main_page():
    with gr.Column(visible=False) as main_page:
        gr.Markdown("## Authentication Successful!")
        session_token_output = gr.Textbox(label="Session Token", interactive=False)
        refresh_token_output = gr.Textbox(label="Refresh Token", interactive=False)
        logout_button = gr.Button("Logout")

    return main_page, logout_button

# Function to load stored session and handle UI visibility
def load_stored_session(stored_state):
    print(f"Stored State: {stored_state}")    # If there's a session token stored, show main page
    if stored_state[0] != "":  # If session_token exists
        return (
            gr.update(visible=False),  # Hide login page
            gr.update(visible=True),   # Show main page
            f"Welcome back!",  # User is logged in
            stored_state
        )
    return (
        gr.update(visible=True),      # Show login page
        gr.update(visible=False),     # Hide main page
        "",                           # Clear message
        stored_state
    )


# Function to handle user logout
def logout_user(stored_state: gr.BrowserState):
    # Clear session and reset the UI to login page
    stored_state = ['', '']
    
    print(f"session_token state: {stored_state[0]}")
    print(f"refresh_token state: {stored_state[1]}")

    # Redirect to the login page with no token in the URL
    return (
        gr.update(visible=True),       # Show login page
        gr.update(visible=False),      # Hide main page
        "You have been logged out.",   # Show logout message
        stored_state,                  # Clear the session token
    )
    
def create_app():
    with gr.Blocks() as app:
        # BrowserState stores the session token
        stored_state = gr.BrowserState(["", ""])

        # Create pages and components
        login_page, tenant_input, sso_button, sso_message_output = create_login_page()
        main_page, logout_button = create_main_page()

        # Handle sending the magic link
        sso_button.click(
            fn=start_sso_flow,
            inputs=[tenant_input],
            outputs=[tenant_input, sso_message_output]
        )

        # Handle page load/refresh and token capture
        app.load(
            fn=get_token_and_update_state,
            inputs=[stored_state],
            outputs=[login_page, main_page, sso_message_output, stored_state]
        )
        
        # Handle logout button click
        logout_button.click(
            fn=logout_user,
            inputs=[stored_state],
            outputs=[login_page, main_page, sso_message_output, stored_state]
        )

    return app
        

if __name__ == "__main__":
    # Start Flask server in a separate thread without debug mode
    flask_thread = Thread(target=lambda: app_flask.run(host='127.0.0.1', port=7863, debug=False, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start Gradio app
    logger.info("Starting Gradio interface")

    gradio_app = create_app()
    gradio_app.launch(server_name="127.0.0.1", server_port=7864, share=False)
