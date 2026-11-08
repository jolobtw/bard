"""CLI Entrypoint and Onboarding Flow for Bard."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from typing import Optional, Sequence

from rich.console import Console
from rich.panel import Panel

from bard.audio_engine import AudioEngine
from bard.audio_player import AudioPlayer
from bard.config import BardConfig
from bard.oauth import YTMusicOAuth
from bard.ui.app import BardApp
from bard.ytmusic_client import YTMusicClient

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


def run_device_logout(oauth: Optional[YTMusicOAuth] = None) -> bool:
    """Clear stored OAuth tokens and reset to anonymous client mode."""
    if oauth is None:
        oauth = YTMusicOAuth()
    oauth.clear_tokens()
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
        "--login",
        action="store_true",
        help="Log in to YouTube Music via OAuth 2.0 device pairing",
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
