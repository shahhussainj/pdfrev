"""
Run this script ONCE on your local machine to generate a session string.
You'll paste the output into Render.com as an environment variable.

Install first:
    pip install telethon

Then run:
    python generate_session.py
"""

from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID   = input("Enter your API_ID (from my.telegram.org): ").strip()
API_HASH = input("Enter your API_HASH (from my.telegram.org): ").strip()

with TelegramClient(StringSession(), int(API_ID), API_HASH) as client:
    session_string = client.session.save()

print("\n✅ Your session string (copy this exactly):")
print(session_string)
print("\nPaste this as TELEGRAM_SESSION_STRING in Render.com environment variables.")
