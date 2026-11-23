"""CLI Entrypoint and Onboarding Flow for Bard."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from typing import Optional, Sequence

from rich.console import Console
from rich.panel import Panel

from bard import __version__
from bard.audio_engine import AudioEngine
from bard.audio_player import AudioPlayer
from bard.config import BardConfig
from bard.oauth import YTMusicOAuth
from bard.ui.app import BardApp
from bard.ytmusic_client import YTMusicClient, get_default_browser_auth_path

console = Console()


def ensure_audio_engine() -> bool:
    """Check for mpv binary and display friendly installation instructions if missing."""
    mpv_path = AudioEngine.find_mpv()
    if not mpv_path:
        console.print(
            Panel(
                "[#FF7A00 bold]mpv media player was not found on your system PATH.[/]\n\n"
                "[#A6ADC8]Bard requires headless mpv to stream high-fidelity YouTube Music.\n"
                "Please install mpv:\n"
                "  • Windows: [#FFD166]winget install mpv.net[/] or [#FFD166]choco install mpv[/]\n"
                "  • macOS:   [#FFD166]brew install mpv[/]\n"
                "  • Linux:   [#FFD166]sudo apt install mpv[/]\n",
                border_style="#FF7A00",
                title="✦ ❖ BARD AUDIO ENGINE ❖ ✦",
            )
        )
        return False
    return True


def run_device_login(oauth: Optional[YTMusicOAuth] = None) -> bool:
    """Initiate OAuth 2.0 Device Code flow, display verification code, and poll for approval."""
    if oauth is None:
        oauth = YTMusicOAuth()

    try:
        device_data = oauth.get_device_code()
    except Exception as e:
        console.print(f"[bold red]Failed to get device code:[/] {e}")
        return False

    if not device_data or not device_data.get("device_code") or not device_data.get("user_code"):
        console.print("[bold red]Invalid device code response from Google OAuth.[/]")
        return False

    verification_url = device_data.get("verification_url", "https://www.google.com/device")
    user_code = device_data["user_code"]
    device_code = device_data["device_code"]
    interval = device_data.get("interval", 5)

    console.print(
        Panel(
            f"[#A6ADC8]To link your YouTube Music account:\n\n"
            f"  1. Visit: [#FFD166 underline]{verification_url}[/]\n"
            f"  2. Enter code: [bold #FF7A00]{user_code}[/]\n\n"
            f"[#6C7086]Opening your browser automatically...[/]",
            border_style="#FF7A00",
            title="✦ ❖ YOUTUBE MUSIC DEVICE PAIRING ❖ ✦",
        )
    )

    try:
        webbrowser.open(verification_url)
    except Exception:
        pass

    with console.status("[#FFD166]Waiting for approval in your browser...[/]", spinner="dots"):
        token_data = oauth.poll_for_token(device_code, interval=interval)

    if token_data:
        oauth.save_tokens(token_data)
        console.print(
            Panel(
                "[bold #00E5FF]✦ Successfully authenticated with YouTube Music![/]\n\n"
                "[#A6ADC8]Your personal library, playlists, and liked songs are now unlocked in Bard.",
                border_style="#00E5FF",
                title="✦ ❖ PAIRING COMPLETE ❖ ✦",
            )
        )
        return True
    else:
        console.print("[bold red]Authorization timed out or was denied.[/]")
        return False


def _normalize_pasted_headers(raw: str) -> str:
    """Accept either raw HTTP headers or a browser 'Copy as cURL' snippet."""
    import re
    import shlex

    text = raw.strip()
    if not text:
        return ""

    if text.lower().startswith("curl "):
        # Handle bash (\) and Windows cmd (^) line continuations
        joined = re.sub(r"\s*[\\^]\s*\r?\n\s*", " ", text)
        # Unescape Windows cmd ^" / ^& / ^% sequences if present
        if '^"' in joined:
            joined = joined.replace('^"', '"').replace("^&", "&").replace("^%", "%")
        try:
            tokens = shlex.split(joined, posix=True)
        except ValueError:
            tokens = joined.split()

        header_lines: list[str] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in ("-H", "--header") and i + 1 < len(tokens):
                header_lines.append(tokens[i + 1])
                i += 2
            elif tok in ("-b", "--cookie") and i + 1 < len(tokens):
                header_lines.append(f"cookie: {tokens[i + 1]}")
                i += 2
            else:
                i += 1
        if header_lines:
            return "\n".join(header_lines)

    # Strip HTTP/2 pseudo-headers (:authority, :method, etc.) if pasted from Chrome DevTools
    cleaned_lines = [
        ln for ln in text.splitlines()
        if ln.strip() and not ln.lstrip().startswith(":")
    ]
    return "\n".join(cleaned_lines)


def _read_pasted_headers() -> str:
    """Read multi-line HTTP headers (or cURL) until EOF, 'DONE', or two consecutive blank lines."""
    lines: list[str] = []
    blank_streak = 0
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().upper() == "DONE":
            break
        if line.strip() == "":
            blank_streak += 1
            if lines and blank_streak >= 2:
                break
        else:
            blank_streak = 0
            lines.append(line)
    return _normalize_pasted_headers("\n".join(lines))


def run_browser_auth(browser_path: Optional[object] = None) -> bool:
    """Configure YouTube Music browser header auth (for YTM-only playlists)."""
    import json
    import ytmusicapi
    from ytmusicapi import YTMusic

    target = browser_path if browser_path is not None else get_default_browser_auth_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    console.print(
        Panel(
            "[#A6ADC8]To connect YouTube Music directly (music-only playlists):\n\n"
            "  1. Open [#FFD166 underline]https://music.youtube.com[/] while signed in\n"
            "  2. Open DevTools (F12) -> Network -> filter [#FFD166]browse[/]\n"
            "     (Click [#FFD166]Library[/] on the page if you don't see a [#FFD166]POST browse[/] request)\n"
            "  3. Right-click a [#FFD166]POST browse[/] request -> [#FFD166]Copy -> Copy as cURL (bash)[/]\n"
            "  4. Paste below, then press [#FFD166]Enter twice[/] (or type [#FFD166]DONE[/] + Enter)[/]",
            border_style="#FF7A00",
            title="✦ ❖ YOUTUBE MUSIC BROWSER AUTH ❖ ✦",
        )
    )
    try:
        headers_raw = _read_pasted_headers()
        if not headers_raw:
            console.print("[bold red]No headers provided.[/]")
            return False
        ytmusicapi.setup(filepath=str(target), headers_raw=headers_raw)

        # Normalize saved JSON so ytmusicapi always recognizes it as BROWSER auth
        if target.exists():
            data = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = {
                    k: v
                    for k, v in data.items()
                    if k.lower() not in ("content-encoding", "alt-used", "connection", "accept-encoding")
                }
                if "cookie" in {k.lower() for k in data} and "authorization" not in {k.lower() for k in data}:
                    data["authorization"] = "SAPISIDHASH 0_0"
                target.write_text(json.dumps(data, indent=2), encoding="utf-8")

                # Verify that YouTube Music actually accepts the session
                ytm = YTMusic(auth=data)
                pls = ytm.get_library_playlists(limit=5)
                if not pls:
                    console.print(
                        "[bold #FF7A00]⚠ Saved browser.json, but YouTube Music returned 0 playlists.[/]\n"
                        "[#A6ADC8]Make sure you copied headers from a signed-in POST /youtubei/v1/browse request on music.youtube.com.[/]"
                    )
                    return False

        console.print(f"[bold #00E5FF]✦ Verified & saved YouTube Music browser auth to {target}[/]")
        return True
    except Exception as exc:
        console.print(f"[bold red]Browser auth setup failed:[/] {exc}")
        return False


def run_device_logout(oauth: Optional[YTMusicOAuth] = None) -> bool:
    """Clear stored OAuth tokens and browser auth, resetting to anonymous client mode."""
    if oauth is None:
        oauth = YTMusicOAuth()
    oauth.clear_tokens()
    browser_path = oauth.token_path.parent / "browser.json"
    if browser_path.exists():
        try:
            browser_path.unlink()
        except Exception:
            pass
    console.print(
        Panel(
            "[#FF7A00]✦ Stored YouTube Music credentials cleared.[/]\n\n"
            "[#A6ADC8]Bard is now operating in unauthenticated / public mode.",
            border_style="#FF7A00",
            title="✦ ❖ LOGGED OUT ❖ ✦",
        )
    )
    return True


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Main launcher."""
    parser = argparse.ArgumentParser(
        prog="bard",
        description="Bard - Arcane Terminal YouTube Music Player",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"Bard v{__version__}",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Log in to YouTube Music via OAuth 2.0 device pairing",
    )
    parser.add_argument(
        "--auth-browser",
        action="store_true",
        help="Configure YouTube Music browser headers (music-only playlists)",
    )
    parser.add_argument(
        "--logout",
        action="store_true",
        help="Log out and clear stored YouTube Music credentials",
    )

    args = parser.parse_args(argv)

    if args.login:
        success = run_device_login()
        sys.exit(0 if success else 1)
        return

    if args.auth_browser:
        success = run_browser_auth()
        sys.exit(0 if success else 1)
        return

    if args.logout:
        success = run_device_logout()
        sys.exit(0 if success else 1)
        return

    config = BardConfig()
    if not ensure_audio_engine():
        sys.exit(1)

    client = YTMusicClient()
    player = AudioPlayer()

    app = None
    try:
        app = BardApp(config=config, client=client, player=player)
        app.run()
    finally:
        if player:
            try:
                player.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
