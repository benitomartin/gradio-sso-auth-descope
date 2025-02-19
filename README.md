# Gradio Application with Descope Authentication

<p align="center">
<img width="737" alt="cover" src="https://github.com/user-attachments/assets/32b657a3-0986-41d6-b44b-ec39288f85d7">
</p>

This repository contains a Gradio App that contains several authentication methods using Descope:

- Magic Link
- SSO with OIDC and Okta as IdP
- OAuth Social Login
- Custom Claims

# Set up your environment

Clone the repository and activate the environment from the project folder:

```bash
uv sync
source .venv/bin/activate
```

There are 4 Gradio apps, each one using a different authentication method:

- `basic_gradio_app.py`: basic app simulating login

- `magic_gradio_app.py`: app using Descope magic link

- `sso_gradio_app.py`: app using SSO and Okta for login authentication

- `social_gradio_app.py`: app using Google for login authentication

- `descope_gradio_app.py`: app using all auhentication methods

It has been created together with the following [blog](https://medium.com/@benitomartin/add-authentication-and-sso-to-your-gradio-app-19096dfdb297). You can follow he blog to create a Descope/Okta account and use the different authentication methods within the app.
