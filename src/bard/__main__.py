"""CLI Entrypoint and Onboarding Flow for Bard."""

from __future__ import annotations

import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from rich.console import Console
from rich.panel import Panel

from bard.config import BardConfig
from bard.spotify_client import SpotifyClient, generate_pkce_pair
from bard.audio_engine import AudioEngine
from bard.ui.app import BardApp

console = Console()


def run_oauth_flow(config: BardConfig, client: SpotifyClient) -> bool:
    """Run local loopback server and open browser for one-click OAuth login."""
    verifier, challenge = generate_pkce_pair()
    state = "bard_auth_state"
    auth_code_holder = {"code": None, "error": None}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if "callback" in self.path:
                from urllib.parse import parse_qs, urlparse
                query = parse_qs(urlparse(self.path).query)
                if "code" in query:
                    auth_code_holder["code"] = query["code"][0]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    html = """
                    <html>
                    <body style="background:#13141C;color:#FF7A00;font-family:sans-serif;text-align:center;padding:50px;">
                        <h1>✦ BARD AUTHENTICATED ✦</h1>
                        <p style="color:#A6ADC8;">You may now return to your terminal.</p>
                    </body>
                    </html>
                    """
                    self.wfile.write(html.encode("utf-8"))
                else:
                    auth_code_holder["error"] = query.get("error", ["Unknown error"])[0]
                    self.send_response(400)
                    self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Quiet logging

    server = HTTPServer(("127.0.0.1", 8888), CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    auth_url = client.get_auth_url(challenge, state)
    console.print("\n[#FF7A00 bold]Opening browser for Spotify Authorization...[/]")
    console.print(f"[#6C7086]If it doesn't open automatically, visit:\n{auth_url}[/]\n")
    webbrowser.open(auth_url)

    server_thread.join(timeout=60)
    server.server_close()

    if auth_code_holder["code"]:
        success = client.exchange_code_for_token(auth_code_holder["code"], verifier)
        if success:
            console.print("[#A6E3A1 bold]✓ Successfully logged into Spotify![/]\n")
            return True
    return False


def main() -> None:
    """Main launcher."""
    config = BardConfig()
    client = SpotifyClient(config)

    # 1. First-Run Setup: Client ID
    if not config.client_id:
        welcome_text = (
            "[#FF7A00 bold]Welcome to Bard — The Arcane Terminal Spotify Player[/]\n\n"
            "[#A6ADC8]To stream and control your music, Spotify requires a free Client ID from:\n"
            "[#FFD166 underline]https://developer.spotify.com/dashboard[/]\n\n"
            "Redirect URI to register: [#FFFFFF bold]http://127.0.0.1:8888/callback[/]"
        )
        console.print(Panel(welcome_text, border_style="#FF7A00", title="✦ ❖ BARD SETUP ❖ ✦"))
        client_id_input = console.input("[#FF7A00 bold]Enter your Spotify Client ID: [/]").strip()
        if not client_id_input:
            console.print("[#FF4D4D]Client ID cannot be empty. Exiting.[/]")
            sys.exit(1)
        config.client_id = client_id_input
        config.save()

    # 2. First-Run Setup: OAuth Login
    if config.is_token_expired():
        if not config.refresh_token or not client.refresh_access_token():
            console.print("[#FF7A00]Spotify login required.[/]")
            ok = run_oauth_flow(config, client)
            if not ok:
                console.print("[#FF4D4D]Authentication failed or timed out. Please try again.[/]")
                sys.exit(1)

    # 3. Audio Engine Check
    engine = AudioEngine(device_name=config.device_name)
    if engine.is_installed():
        engine.start()
    else:
        # Informative notice if standalone librespot binary isn't in bin/
        console.print(
            f"[#FFAF00]Note: Background streaming engine (librespot) not found in {engine.binary_path}.[/]\n"
            "[#6C7086]Bard will run as a Spotify Connect controller for your existing active devices.[/]\n"
            "[#6C7086]You can place 'librespot' in that folder anytime to enable direct audio output.[/]\n"
        )
        time.sleep(1)

    # 4. Launch Textual App
    app = BardApp(config, client)
    app.run()


if __name__ == "__main__":
    main()
