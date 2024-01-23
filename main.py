'''
This is my first attempt at trying to integrate the more successful spotify oauth flow into the 
frontend-equipped main.py flask app. 
'''

# Misc imports
from flask import Flask, session, request, redirect, url_for, render_template, jsonify, flash
import os
from dotenv import load_dotenv
import json
import subprocess

# FOR GOOGLE OAUTH
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# API imports
from spotipy.oauth2 import SpotifyOAuth
from google_auth_oauthlib.flow import Flow as GoogleFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# FOR SPOTIFY OAUTH 
cache_dir = '.spotify_caches'
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

load_dotenv()

app = Flask(__name__) 
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# Spotify OAuth2 setup
os.environ['SPOTIPY_CLIENT_ID'] = os.getenv('SPOTIFY_CLIENT_ID')
os.environ['SPOTIPY_CLIENT_SECRET'] = os.getenv('SPOTIFY_CLIENT_SECRET')
os.environ['SPOTIPY_REDIRECT_URI'] = os.getenv('SPOTIFY_REDIRECT_URI')
SPOTIFY_SCOPES = 'user-library-read playlist-modify-public'

# Google OAuth setup
GOOGLE_SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
GOOGLE_CLIENT_SECRET_FILE = os.getenv('GOOGLE_CLIENT_SECRET_FILE')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI')

def refresh_spotify_token():
    if 'spotify_token_info' in session:
        sp_oauth = SpotifyOAuth(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),  # Use the same redirect URI as in create_spotify_oauth
            scope=SPOTIFY_SCOPES)
        token_info = sp_oauth.refresh_access_token(session['spotify_token_info']['refresh_token'])
        session['spotify_token_info'] = token_info

        # Save the refreshed access token as an environment variable
        os.environ['SPOTIFY_ACCESS_TOKEN'] = token_info['access_token']

def refresh_google_token():
    if 'google_credentials' in session:
        creds = Credentials(**session['google_credentials'])
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            session['google_credentials'] = credentials_to_dict(creds)
            os.environ['GOOGLE_CREDENTIALS_FILE'] = 'google_creds.json'

def credentials_to_dict(credentials):
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}

def create_spotify_oauth():
    return SpotifyOAuth(
        scope='user-library-read playlist-modify-public',
        cache_path=f".spotify_caches/{session.get('uuid')}"  # Use the unique session identifier
    )

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login_spotify')
def login_spotify():
    if 'uuid' not in session:
        session['uuid'] = os.urandom(16).hex()  # Generate a random UUID
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/spotify_callback')
def spotify_callback():
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['auth_token'] = token_info['access_token']

    #new
    session['spotify_token_info'] = token_info
    os.environ['SPOTIFY_ACCESS_TOKEN'] = token_info['access_token']
    print("Access Token:", token_info['access_token'])

    return '''
    <html>
        <head><title>Spotify Authentication Success</title></head>
        <body>
            <script>
            window.opener.postMessage('spotify-auth-success', '*');
            window.close();
            </script>
        </body>
    </html>
    '''

@app.route('/login_google')
def login_google():
    flow = GoogleFlow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRET_FILE, 
        scopes=GOOGLE_SCOPES, 
        redirect_uri=GOOGLE_REDIRECT_URI)
    authorization_url, state = flow.authorization_url(
        access_type='offline', include_granted_scopes='true')
    session['google_state'] = state
    return redirect(authorization_url)

@app.route('/google_callback')
def google_callback():
    state = session['google_state']
    flow = GoogleFlow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRET_FILE,
        scopes=GOOGLE_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
        state=state)
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session['google_credentials'] = credentials_to_dict(credentials)

    # Initialize Google Calendar API service
    creds = Credentials(**session['google_credentials'])
    service = build('calendar', 'v3', credentials=creds)

    # TIMEZONE DETECTION: Fetch the timezone of the primary calendar
    calendar = service.calendars().get(calendarId='primary').execute()
    calendar_timezone = calendar['timeZone']

    # Save credentials to a file
    creds_data = credentials_to_dict(credentials)
    with open('google_creds.json', 'w') as outfile:
        json.dump(creds_data, outfile)

    # Set environment variables for logic.py
    os.environ['GOOGLE_CREDENTIALS_FILE'] = 'google_creds.json'
    os.environ['GOOGLE_CALENDAR_TIMEZONE'] = calendar_timezone

    # Execute logic.py
    subprocess.Popen(['python', 'logic.py'])

    return '''
    <html>
        <head><title>Google Authentication Success</title></head>
        <body>
            <script>
            window.opener.postMessage('google-auth-success', '*');
            window.close();
            </script>
        </body>
    </html>
    '''

@app.route('/make_playlist', methods=['POST'])
def make_playlist():
    refresh_spotify_token()
    refresh_google_token()

    token_check_process = subprocess.Popen(['python', 'token_check.py'])
    token_check_process.wait()

    if token_check_process.returncode == 0:
        subprocess.Popen(['python', 'logic.py'])
        return jsonify({"status": "success"})
    
    elif token_check_process.returncode == 1:
        return jsonify({"status": "error", "message": "Log into Google again, and this should work just fine."})
    
    elif token_check_process.returncode == 2:
        return jsonify({"status": "error", "message": "Log into Spotify again, then try this one more time."})
    
    elif token_check_process.returncode == 3:
        return jsonify({"status": "error", "message": "This works best if you have more than 50 songs on your Spotify Liked Songs playlist. Take some time to discover new music, then come back here when the time is right."})
    
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


'''
Adding two more routes to handle Privacy Policy and Delete My Data functionality, scheduled for March 2024
'''

if __name__ == '__main__':
    app.run(debug=True)  # Set debug=False in production
