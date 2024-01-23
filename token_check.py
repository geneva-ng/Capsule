'''
The sole purpose of this script is to catch the need to re-login to Google when user clicks "Make Another".
Having these quick error-handling things here is faster than running all of logic.py just for there to be an error
in the first few lines. 
'''


import os
import spotipy
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import json

def load_google_credentials(creds_file):
    with open(creds_file, 'r') as infile:
        creds_data = json.load(infile)
        return Credentials(**creds_data)
    

def main():
    print('RUNNING token_checker.PY')

    # CHECK FOR SPOTIFY API CALL ACCESS
    token = os.getenv('SPOTIFY_ACCESS_TOKEN')
    if not token:
        print("Spotify access token is missing.")
        exit(2)
    
    # LOCAL SPOTIFY SETUP
    sp = spotipy.Spotify(auth=token)
    username = sp.current_user()['display_name'] #get username

    # Check number of liked songs
    results = sp.current_user_saved_tracks(limit=1)  # Get just the total count
    total_liked_songs = results['total']
    if total_liked_songs < 50:
        print(f"User {username} has less than 50 liked songs.")
        exit(3)
   
    # LOCAL GCAL SETUP
    service = None
    creds_file = os.getenv('GOOGLE_CREDENTIALS_FILE')
    google_calendar_timezone = os.getenv('GOOGLE_CALENDAR_TIMEZONE')
    if creds_file and google_calendar_timezone:
        try:
            creds = load_google_credentials(creds_file)
            service = build('calendar', 'v3', credentials=creds)
        except Exception as e:
            print(f"Error setting up Google Calendar service: {e}")
    if service is None:
        print("Error: Google Calendar service setup failed.")
        exit(1)

if __name__ == '__main__':
    main()
