from dotenv import load_dotenv
import os

load_dotenv()

DB_URL = f"""
postgresql://{os.getenv('DB_USER')}:
{os.getenv('DB_PASSWORD')}@
{os.getenv('DB_HOST')}:
{os.getenv('DB_PORT')}/
{os.getenv('DB_NAME')}
""".replace("\n", "")

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
