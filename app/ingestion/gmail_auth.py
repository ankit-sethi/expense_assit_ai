import os, pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def get_gmail_service():

    creds = None

    try:
        # Load saved token if exists
        if os.path.exists('token.pkl'):
            with open('token.pkl', 'rb') as f:
                creds = pickle.load(f)

        # If no valid creds → authenticate
        if not creds or not creds.valid:

            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open('token.pkl', 'wb') as f:
                pickle.dump(creds, f)

        service = build('gmail', 'v1', credentials=creds)

        # ⭐ Real connection verification
        profile = service.users().getProfile(userId='me').execute()
        print(f"[GMAIL AUTH] Connected to: {profile.get('emailAddress')}")

        return service

    except Exception as e:
        print("[GMAIL AUTH ERROR]", e)
        raise
