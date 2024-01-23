#for spotify
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.oauth2 import SpotifyOAuth

#for firebase
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

#for datetime conversion functions
from timezone import timezone_dict
from datetime import datetime, timedelta
from dateutil import parser, tz
import pytz
import random

#for google
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import json

#for openai
import openai
from dotenv import load_dotenv
import os
from nlp import generate, prepare, process

load_dotenv()


def format_date_for_google_calendar(date_str, calendar_timezone):

    '''
    Formats a date string to UTC in RFC3339 format for Google Calendar API calls.

    date_str (string): datetime the format "2022-09-13T19:11:26-5:00"
    calendar_timezone (string): Google timezone label (dictionary of all options timezone.py)
    '''

    local_dt = parser.parse(date_str)
    local_tz = tz.gettz(calendar_timezone)
    local_dt = local_dt.astimezone(local_tz)
    utc_dt = local_dt.astimezone(tz.UTC)
    return utc_dt.isoformat()

def spot_to_gcal_date(date, timezone):

    '''
    Converts Spotify date format to Google-calendar compatible date format. 

    date (datetime): date data from Spotify API call
    timezone (string): Google Calendar timzeone label (dictionary of options in timezone.py)
    '''

    spotify_date_format = "%Y-%m-%dT%H:%M:%SZ"
    date_obj = datetime.strptime(date, spotify_date_format)
    utc = pytz.utc
    date_obj = utc.localize(date_obj)

    if timezone in timezone_dict:
        timezone_offset = timezone_dict[timezone]
    else:
        raise ValueError("Timezone not found in timezone_dict")

    hours_offset = int(timezone_offset.split(':')[0])
    minutes_offset = int(timezone_offset.split(':')[1])
    offset_delta = timedelta(hours=hours_offset, minutes=minutes_offset)
    target_timezone = pytz.FixedOffset(offset_delta.total_seconds() // 60)
    target_date_obj = date_obj.astimezone(target_timezone)
    formatted_date = target_date_obj.strftime("%Y-%m-%dT%H:%M:%S")
    formatted_timezone_offset = f"{offset_delta.days * 24 + offset_delta.seconds // 3600:02d}:{abs(offset_delta.seconds // 60 % 60):02d}"
    return f"{formatted_date}{formatted_timezone_offset}"

def load_google_credentials(creds_file):
    with open(creds_file, 'r') as infile:
        creds_data = json.load(infile)
        return Credentials(**creds_data)

def gcal_event_fetch(service, start, end, calendar_timezone):
    """Fetch events from Google Calendar between start and end dates."""
    # Format the start and end dates for the Google Calendar API
    time_min = format_date_for_google_calendar(start, calendar_timezone)
    time_max = format_date_for_google_calendar(end, calendar_timezone)

    # Fetch events within the defined time window
    events_result = service.events().list(
        calendarId='primary', timeMin=time_min, timeMax=time_max,
        maxResults=10, singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])

    # Process and return the events
    if not events:
        return []
    else:
        return [(event['start'].get('dateTime', event['start'].get('date')), event['summary']) for event in events]

def parse_date_part(date_str):

    '''
    Extracts the date and timezone from a full date string. 
    
    date_str (string): datetime in the format "2022-09-13T19:11:26-5:00"
    '''

    date_part, timezone = date_str.rsplit('-', 1)
    return datetime.fromisoformat(date_part), '-' + timezone

def generate_random_date(start_str, end_str):

    '''
    Generate a random date between start and end date strings.

    start_str (string): datetime in the format "2022-09-13T19:11:26-5:00", lower bound for random date generation
    end_str (string): same format as above, upper bound 
    '''

    start_date, timezone = parse_date_part(start_str)
    end_date, _ = parse_date_part(end_str)
    delta_days = (end_date - start_date).days
    random_days = random.randint(0, delta_days)
    random_date = start_date + timedelta(days=random_days)
    return f"{random_date.strftime('%Y-%m-%d')}T00:00:00{timezone}"


def main():
    
    print('RUNNING LOGIC.PY')

    '''
    Any error-handling/checking in here for Spotify and Google API access is now made obscelete by token_check.py
    '''

    # CHECK FOR SPOTIFY API CALL ACCESS
    token = os.getenv('SPOTIFY_ACCESS_TOKEN')
    if not token:
        print("Spotify access token is missing.")
        return
    
    # SPOTIFY SETUP - CURRENT ISSUE WITH AUTH PERMISSIONS
    sp = spotipy.Spotify(auth=token)
    username = sp.current_user()['display_name'] #get username
    print(F"CURRENT USER: {username}")

    # GCAL SETUP (incl. timezone + timeout handling)
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
        print("error")
        exit(1)
    
    # FIREBASE SETUP
    cred = credentials.Certificate('capsulev3-firebase-adminsdk-rc1r0-4e44de2827.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    # OPENAI SETUP
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key is None:
        raise ValueError("API key not found in .env file")
    openai.api_key = api_key


    # FUNCTION: check if user collection already exists 
    def collection_exists(db, collection_name):
        return any(db.collection(collection_name).limit(1).get())
    
    # FUNCTION: add song item to correct location in data hierarchy
    def add_song_db(collection_name, song_data):
        collection_ref = db.collection(collection_name)
        collection_ref.add(song_data)
    
    # FETCH 1000 SONGS (units of 50) + ADD EACH TO DATABASE
    if not collection_exists(db, username):
        total_songs = 1000
        offset = 0
        songs_added = 0
        while offset < total_songs:
            #0. Init Spotify playlist to reap from
            results = sp.current_user_saved_tracks(limit=50, offset=offset)

            for item in results['items']:
                #1. Locate song data needed 
                track = item['track']
                added_date = item['added_at']  

                #2. Convert the Spotify date to Gcal date format
                added_date = spot_to_gcal_date(added_date, google_calendar_timezone)

                #3. Prepare song data
                song_data = {
                    'addedDate': added_date,
                    'trackURI': track['uri']
                }

                #4. Add song data to database
                add_song_db(username, song_data)
                songs_added += 1

            #5. Update the offset
            offset += 50

            #6. break loop if finished (if less than 50 items left)
            if len(results['items']) < 50:
                break
    else:
        print(f"Collection '{username}' already exists in the database.")

    # PURE LOGIC
    playlistLength = 20

    #1. GET EARLIEST POSSIBLE DATE
    db_first_song = db.collection(username).order_by('addedDate', direction=firestore.Query.ASCENDING).limit(1).get()
    start = db_first_song[0].to_dict()['addedDate'] if db_first_song else None

    #2. GET LATEST POSSIBLE DATE BASED ON PLAYLIST LENGTH
    db_nth_song = db.collection(username).order_by('addedDate', direction=firestore.Query.DESCENDING).limit(playlistLength).get()
    end = db_nth_song[-1].to_dict()['addedDate'] if len(db_nth_song) == playlistLength else None

    #3. INITIAL rand_date DATE GENERATION
    rand_date = generate_random_date(start, end)

    #FIREBASE QUERY TO SELECT SONGS BASED ON rand_date DATE, RETURNS SONG BOOKEND DATES  
    def generate_song_selections(collection_name, target_date, playlistLength):
        # Query to find the song closest to the target date
        closest_song_query = db.collection(collection_name).where('addedDate', '>=', target_date).order_by('addedDate').limit(1).get()
        
        closest_song_date = None
        for doc in closest_song_query:
            closest_song_date = doc.to_dict()['addedDate']

        if closest_song_date is None:
            return [], None, None

        # Query to find the next songs after the closest song
        next_songs_query = db.collection(collection_name).where('addedDate', '>', closest_song_date).order_by('addedDate').limit(playlistLength).get()
        
        next_songs = [doc.to_dict() for doc in next_songs_query]
        tracks = [doc.to_dict()['trackURI'] for doc in next_songs_query]
        
        # Determine playlistStart and playlistEnd
        playlist_dates = [song['addedDate'] for song in next_songs]
        playlistStart = min(playlist_dates, default=None)
        playlistEnd = max(playlist_dates, default=None)

        return next_songs, playlistStart, playlistEnd, tracks
    
    #4. FIND PLAYLIST SELECTIONS + Date Bookends
    next_songs, playlistStart, playlistEnd, tracks = generate_song_selections(username, rand_date, playlistLength)
 
    # GCAL TIME WINDOW SEARCH
    def gcal_event_fetch(service, start, end, calendar_timezone):
        """Fetch events from Google Calendar between start and end dates."""
        # Format the start and end dates for the Google Calendar API
        time_min = format_date_for_google_calendar(start, calendar_timezone)
        time_max = format_date_for_google_calendar(end, calendar_timezone)

        # Fetch events within the defined time window
        events_result = service.events().list(
            calendarId='primary', timeMin=time_min, timeMax=time_max,
            maxResults=10, singleEvents=True, orderBy='startTime').execute()
        events = events_result.get('items', [])

        # Process and return the events
        if not events:
            print('No events found in the specified time range.')
            return []
        else:
            return [(event['start'].get('dateTime', event['start'].get('date')), event['summary']) for event in events]

    # WHILE-LOOP TO PROMISE GCAL EVENTS FOR EVERY PLAYLIST SELECTION
    events = []
    attempts = 0
    max_attempts = 10

    playlist_title = "Capsule"
    playlist_description = "NLP model in development to parse your Google Calendar events into a lovely little blurb to add here. Coming soon <3"

    while not events and attempts < max_attempts: 
        events = gcal_event_fetch(service, playlistStart, playlistEnd, google_calendar_timezone)  
        attempts += 1

        if events:

            # PACKAGE UP EVENT DESCRIPTIONS INTO ONE STRING FOR NLP PARSING LATER
            event_descriptions = ', '.join([event[1] for event in events])
            print(f"raw event descriptions: {event_descriptions}")

            # THIS IS WHERE YOU ADD THE NLP
            playlist_description = process(event_descriptions)
            # print(playlist_description)

        else:
            print("No events found. Trying again...")
            rand_date = generate_random_date(start, end)
            next_songs, playlistStart, playlistEnd, tracks = generate_song_selections(username, rand_date, playlistLength)

    if not events:

        # IF NO EVENTS, GIVE USER A PLAYLIST BUT NO DESCRIPTION (BC NOT POSSIBLE)
        playlist_description = "You don't have enough events on your calendar for this to work! Silly goose. Here's a playlist anyways."

    # EXPORT TRACK SELECTION TO SPOTIFY
    def create_playlist(sp, track_uris, title, description):
        """
        Create a Spotify playlist and add tracks to it.

        Parameters:
        sp (Spotify): The Spotify client object.
        track_uris (list): A list of track URIs to add to the playlist.
        title (str): The title of the playlist.
        description (str): The description of the playlist.
        """

        # Get the current user's Spotify ID
        user_id = sp.current_user()['id']

        # Create the playlist
        playlist = sp.user_playlist_create(user_id, title, public=True)
        playlist_id = playlist['id']

        # Set the playlist description
        sp.user_playlist_change_details(user_id, playlist_id, description=description)

        # Add tracks to the playlist
        sp.playlist_add_items(playlist_id, track_uris)

        return 
    
    print(f"FINAL DESCRIPTION: {playlist_description}")
    create_playlist(sp, tracks, playlist_title, playlist_description)


if __name__ == '__main__':
    main()
