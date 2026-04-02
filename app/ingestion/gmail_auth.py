import os, pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CREDENTIALS_PATH = os.path.join(_APP_DIR, 'credentials.json')
_TOKEN_PATH = os.path.join(_APP_DIR, 'token.pkl')


def get_gmail_service():

    creds = None

    try:
        if os.path.exists(_TOKEN_PATH):
            with open(_TOKEN_PATH, 'rb') as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:

            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    _CREDENTIALS_PATH, SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(_TOKEN_PATH, 'wb') as f:
                pickle.dump(creds, f)

        service = build('gmail', 'v1', credentials=creds)

        # ⭐ Real connection verification
        profile = service.users().getProfile(userId='me').execute()
        print(f"[GMAIL AUTH] Connected to: {profile.get('emailAddress')}")

        return service

    except Exception as e:
        print("[GMAIL AUTH ERROR]", e)
        raise
