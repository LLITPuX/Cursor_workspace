import google.generativeai as genai
import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Load token directly to avoid importing settings/env complexity for this simple script helper
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_PATH = os.path.join(BASE_DIR, 'credentials', 'token.json')

if not os.path.exists(TOKEN_PATH):
    print(f"Error: Token not found at {TOKEN_PATH}")
    exit(1)

creds = Credentials.from_authorized_user_file(TOKEN_PATH, scopes=['https://www.googleapis.com/auth/generative-language.retriever.readonly', 'https://www.googleapis.com/auth/cloud-platform'])
if creds.expired and creds.refresh_token:
    creds.refresh(Request())

genai.configure(credentials=creds)

print("Listing available models...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Error listing models: {e}")
