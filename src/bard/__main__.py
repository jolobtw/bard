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
    stop_event = threading.Event()

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

    class ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True

    server = None
    try:
        server = ReusableHTTPServer(("127.0.0.1", 8888), CallbackHandler)
        server.timeout = 0.5
    except Exception as e:
        console.print(f"[#FFD166]Note: Could not listen on port 8888 ({e}). Manual URL fallback will be available.[/]")

    def serve():
        while not stop_event.is_set() and not auth_code_holder["code"] and not auth_code_holder["error"]:
            if server:
                server.handle_request()

    if server:
        server_thread = threading.Thread(target=serve, daemon=True)
        server_thread.start()

    auth_url = client.get_auth_url(challenge, state)
    console.print("\n[#FF7A00 bold]Opening browser for Spotify Authorization...[/]")
    console.print(f"[#6C7086]If it doesn't open automatically, visit:\n{auth_url}[/]\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    # Wait up to 60 seconds for auto-redirect or allow manual input
    start_time = time.time()
    while time.time() - start_time < 60:
        if auth_code_holder["code"] or auth_code_holder["error"]:
            break
        time.sleep(0.5)

    stop_event.set()
    if server:
        try:
            server.server_close()
        except Exception:
            pass

    # Fallback: if auto-redirect did not capture the code, prompt user to paste redirected URL
    if not auth_code_holder["code"]:
        console.print("[#FFD166]If your browser opened the callback URL (http://127.0.0.1:8888/callback?code=...) but it didn't complete automatically:[/]")
        manual_input = console.input("[#FF7A00 bold]Paste the full redirected URL or code from your browser (or press Enter to cancel): [/]").strip()
        if manual_input:
            if "code=" in manual_input:
                from urllib.parse import parse_qs, urlparse
                query = parse_qs(urlparse(manual_input).query)
                if "code" in query:
                    auth_code_holder["code"] = query["code"][0]
            else:
                auth_code_holder["code"] = manual_input

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

    # 3. Audio Engine Background Streaming Daemon
    engine = AudioEngine(device_name=config.device_name, client_id=config.client_id)
    if engine.is_installed():
        if engine.start():
            import os
            exe_name = os.path.basename(engine.get_executable_path())
            console.print(f"[#A6E3A1 bold]✓ Standalone audio engine ({exe_name}) started in background.[/]")
            time.sleep(1.5)
    else:
        console.print(
            "[#FFAF00]Note: Standalone audio engine (librespot) not installed.[/]\n"
            "[#6C7086]Bard will stream through any active Spotify player (open Spotify on your Mac/PC or install librespot via 'brew install librespot').[/]\n"
        )
        time.sleep(1)

    # 4. Launch Textual App
    try:
        app = BardApp(config, client)
        app.run()
    finally:
        engine.stop()


if __name__ == "__main__":
    main()
