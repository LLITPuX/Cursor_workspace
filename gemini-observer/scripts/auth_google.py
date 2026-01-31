import os.path
import json
import socket
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Scopes required for the Gemini API
SCOPES = ['https://www.googleapis.com/auth/generative-language.retriever.readonly',
          'https://www.googleapis.com/auth/cloud-platform']

def run_docker_friendly_flow(flow, port=8080):
    """
    Runs a local server that binds to 0.0.0.0 (for Docker) but uses localhost
    for the redirect URI (for Google Auth compliance).
    """
    
    # 1. Force the Redirect URI to be localhost (what Google expects)
    flow.redirect_uri = f"http://localhost:{port}/"
    
    # 2. Generate the Authorization URL
    auth_url, _ = flow.authorization_url(prompt='consent')
    
    print("\n----------------------------------------------------------------")
    print("OPEN THIS URL IN YOUR BROWSER:")
    print(auth_url)
    print("----------------------------------------------------------------\n")
    
    # 3. Start a temporary HTTP server
    # We use a list to capture the code from the inner class closure
    captured_code = []

    class OAuthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Parse the URL parameters
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            
            if 'code' in params:
                captured_code.append(params['code'][0])
                
                # Send a nice success message to the browser
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'''
                    <html><head><title>Auth Success</title></head>
                    <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: green;">Authentication Successful!</h1>
                    <p>You can close this window and return to your terminal.</p>
                    </body></html>
                ''')
            else:
                # Ignore other requests (like favicon.ico)
                self.send_response(404)
                self.end_headers()
            
        def log_message(self, format, *args):
            # Silence server logs to keep console clean
            pass

    # Bind to 0.0.0.0 to enable access from outside the container
    server = HTTPServer(('0.0.0.0', port), OAuthHandler)
    print(f"Waiting for authentication callback on port {port}...")
    
    # Loop until we capture the code
    while not captured_code:
        server.handle_request()
        
    server.server_close()
    
    # 4. Exchange the code for a token
    flow.fetch_token(code=captured_code[0])
    return flow.credentials

def authenticate_google():
    """
    Authenticates the user using Google OAuth 2.0.
    """
    creds = None
    
    # Determine paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    credentials_path = os.path.join(base_dir, 'credentials')
    
    if not os.path.exists(credentials_path):
        os.makedirs(credentials_path)

    client_secret_path = os.path.join(credentials_path, 'client_secret.json')
    token_path = os.path.join(credentials_path, 'token.json')

    if not os.path.exists(client_secret_path):
        print(f"Error: client_secret.json not found at {client_secret_path}")
        return

    # Check existing token
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Refresh or Create new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing access token...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}")
                print("Re-authenticating...")
                flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
                creds = run_docker_friendly_flow(flow)
        else:
            print("Starting new authentication flow...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            creds = run_docker_friendly_flow(flow)

        # Save the credentials
        print(f"Saving new token to {token_path}...")
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
        print("Authentication successful!")

if __name__ == '__main__':
    authenticate_google()
