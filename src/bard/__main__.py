"""CLI Entrypoint and Onboarding Flow for Bard."""

from __future__ import annotations

import sys
from rich.console import Console
from rich.panel import Panel

from bard.audio_engine import AudioEngine
from bard.audio_player import AudioPlayer
from bard.config import BardConfig
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


def main() -> None:
    """Main launcher."""
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
