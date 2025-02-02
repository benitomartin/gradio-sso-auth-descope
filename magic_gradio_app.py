import gradio as gr
from flask import Flask, request, redirect
from descope import DescopeClient, DeliveryMethod, AuthException
import os
from dotenv import load_dotenv
from threading import Thread

# Load environment variables
load_dotenv()

# Descope Client Setup
PROJECT_ID = os.getenv("PROJECT_ID")
descope_client = DescopeClient(project_id=PROJECT_ID)

app = Flask(__name__)

# Function to send the magic link
def send_magic_link(email):
    try:
        # Generate magic link via Descope's API
        descope_client.magiclink.sign_up_or_in(
            method=DeliveryMethod.EMAIL,
            login_id=email,
            uri="http://127.0.0.1:5000/verify"  # Redirect URI for Flask server
        )
        return f"Magic link sent to {email}! Please check your inbox."
    except Exception as e:
        return f"Error sending magic link: {str(e)}"

@app.route('/verify')
def verify_magic_link():
    token = request.args.get('t')

    if not token:
        return "Error: Token is missing from the URL", 400

    try:
        # Verify the token with Descope
        user_response = descope_client.magiclink.verify(token)
        
        print(f"User response: {user_response}")

        # Extract the session token from the Descope response
        session_token = user_response.get('sessionToken')

        if not session_token:
            raise AuthException("Failed to retrieve session token.")

        # Redirect to Gradio app with session token in URL
        return redirect(f'http://127.0.0.1:7860/?token={session_token}')

    except AuthException as e:
        return f"Authentication error: {str(e)}", 400
    except Exception as e:
        return f"Error verifying magic link: {str(e)}", 500
    
def get_token_and_update_state(stored_state: gr.BrowserState, request: gr.Request):
    """
    Function to handle token capture and state updates
    Takes only stored_state as input to comply with Gradio's requirements
    Uses the request context internally
    """
    
    try:
        # Get current request context
        query_params = dict(request.query_params)
 
        if query_params:
            # Extract token from query parameters
            token = query_params.get('token')
            if token:
                print(f"Token received: {token}")
                
                stored_state[0] = token
                
                print(f"stored state: {stored_state[0]}")    # If there's a session token stored, show main page

                return (
                    gr.update(visible=False),     # Hide login page
                    gr.update(visible=True),      # Show main page
                    f"Successfully logged in!",   # Success message
                    stored_state                  # Updated state
                )
                
    except Exception as e:
        print(f"Error processing request: {e}")
        
        # Default return if no token or error
    return load_stored_session(stored_state)



# Function to create the login page
def create_login_page():
    with gr.Column(visible=True) as login_page:
        gr.Markdown("## Login Page")
        email = gr.Textbox(label="Enter your email")
        send_button = gr.Button("Send Magic Link")
        login_message = gr.Textbox(label="Message", interactive=False)
    return login_page, email, send_button, login_message

# Function to create the main application page
def create_main_page():
    with gr.Column(visible=False) as main_page:
        gr.Markdown("## Welcome to the Main Page")
        gr.Markdown("You have successfully logged in!")
        gr.Textbox(label="Example Feature", value="This is the main application page")
        logout_button = gr.Button("Logout")
    return main_page, logout_button

# Function to load stored session and handle UI visibility
def load_stored_session(stored_state):


    if stored_state[0]:  # If session_token exists
        return (
            gr.update(visible=False),  # Hide login page
            gr.update(visible=True),   # Show main page
            f"Welcome back!",          # User is logged in
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
    stored_state[0] = {}
    print(f"stored state: {stored_state[0]}")

    # Redirect to the login page with no token in the URL
    return (
        gr.update(visible=True),       # Show login page
        gr.update(visible=False),      # Hide main page
        "You have been logged out.",   # Show logout message
        stored_state,                  # Clear the session token
    )

# Function to create the Gradio app and handle the UI flow
def create_app():
    with gr.Blocks() as app:
        # BrowserState stores the session token
        stored_state = gr.BrowserState([""])

        # Create pages and components
        login_page, email, send_button, login_message = create_login_page()
        main_page, logout_button = create_main_page()

        # Handle sending the magic link
        send_button.click(
            fn=send_magic_link,
            inputs=[email],
            outputs=[login_message]
        )

        # Handle page load/refresh and token capture
        app.load(
            fn=get_token_and_update_state,
            inputs=[stored_state],
            outputs=[login_page, main_page, login_message, stored_state]
        )

        # Handle logout button click
        logout_button.click(
            fn=logout_user,
            inputs=[stored_state],
            outputs=[login_page, main_page, login_message, stored_state]
        )

    return app

# Function to run the Gradio app
def run_gradio():
    gradio_app = create_app()
    gradio_app.launch()

if __name__ == "__main__":
    # Start Flask in a separate thread to handle /verify endpoint
    def run_flask():
        app.run(host="127.0.0.1", port=5000, use_reloader=False)

    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    # Start Gradio app in the main thread
    run_gradio()
