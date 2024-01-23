from flask import Flask, request, redirect, session, url_for
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import os
import google.oauth2.credentials

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with your actual secret key

# Define the path to the client secret file
CLIENT_SECRET_FILE = 'client_secret_23911232907-puinl7m05r5boqk01bfuf1b9hn7rg2rs.apps.googleusercontent.com.json'

# Setup the Google OAuth2 Flow
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Only for development, remove in production
flow = Flow.from_client_secrets_file(
    CLIENT_SECRET_FILE,  # Path to your client secret file
    scopes=['https://www.googleapis.com/auth/calendar.readonly'],
    redirect_uri='https://capsule-dev.ngrok.io/callback')

@app.route('/')
def index():
    if 'credentials' not in session:
        return '<a href="/login">Login with Google</a>'
    return '<a href="/logout">Logout</a>'

@app.route('/login')
def login():
    authorization_url, state = flow.authorization_url(
        access_type='offline', include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    flow.fetch_token(authorization_response=request.url)
    
    if not session['state'] == request.args['state']:
        return 'State mismatch', 400

    credentials = flow.credentials
    session['credentials'] = credentials_to_dict(credentials)
    
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

def credentials_to_dict(credentials):
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}

if __name__ == '__main__':
    app.run(debug=True)  # Change debug to False in production
