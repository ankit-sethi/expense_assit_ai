import os
import socket
from dotenv import load_dotenv

load_dotenv()


def _resolve_db_host(host: str) -> str:
    try:
        socket.getaddrinfo(host, None)
        return host
    except socket.gaierror:
        return "localhost"


_db_host = _resolve_db_host(os.getenv('DB_HOST', 'localhost'))

DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{_db_host}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
