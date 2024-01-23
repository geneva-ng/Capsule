from flask import Flask, session, request, redirect, url_for
import os
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a strong secret key

# Spotify OAuth2 setup
os.environ['SPOTIPY_CLIENT_ID'] = os.getenv('SPOTIFY_CLIENT_ID')
os.environ['SPOTIPY_CLIENT_SECRET'] = os.getenv('SPOTIFY_CLIENT_SECRET')
os.environ['SPOTIPY_REDIRECT_URI'] = 'https://capsule-dev.ngrok.io/callback'

@app.route('/')
def index():
    if 'auth_token' in session:
        return 'Logged in with Spotify <a href="/logout">Logout</a>'
    return '<a href="/login">Login with Spotify</a>'

@app.route('/login')
def login():
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['auth_token'] = token_info['access_token']
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

def create_spotify_oauth():
    return SpotifyOAuth(
        scope='user-library-read playlist-modify-public',
        cache_path=session.get('uuid')
    )

if __name__ == '__main__':
    app.run(debug=True)  # Set debug=False in production
