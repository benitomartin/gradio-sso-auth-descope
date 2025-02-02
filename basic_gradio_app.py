import gradio as gr

# Function to simulate login
def login(email, password):

    if email == "user@example.com" and password == "password123":
        return f"Welcome, {email}!"
    else:
        return "Invalid email or password. Please try again."

# Create a Gradio Blocks app
with gr.Blocks() as app:
    gr.Markdown("# Login Page")
    gr.Markdown("Enter your email and password to log in.")
    
    with gr.Row():
        email_input = gr.Textbox(label="Your E-Mail", placeholder="Enter your email")
        password_input = gr.Textbox(label="Password", placeholder="Enter your password", type="password")

        output = gr.Textbox(label="Response", interactive=False)
    
    login_button = gr.Button("Login")
    login_button.click(fn=login, inputs=[email_input, password_input], outputs=output)

# Launch the app
if __name__ == "__main__":
    app.launch()
