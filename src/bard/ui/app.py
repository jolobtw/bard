"""Main Bard Textual Application."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding

from bard.config import BardConfig
from bard.spotify_client import SpotifyClient
from bard.ui.header import ArcaneHeader
from bard.ui.zen_stage import ZenStage
from bard.ui.curtain_drawer import CurtainDrawer


class BardApp(App):
    """The Arcane Terminal Spotify Player application."""

    CSS = """
    Screen {
        background: #13141C;
        layers: base overlay;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_playback", "Play/Pause", priority=True),
        Binding("tab", "toggle_drawer", "Playlists", priority=True),
        Binding("escape", "close_drawer", "Close", priority=True),
        Binding("n", "next_track", "Next"),
        Binding("p", "prev_track", "Previous"),
        Binding("+", "volume_up", "Vol +"),
        Binding("=", "volume_up", "Vol +", show=False),
        Binding("-", "volume_down", "Vol -"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, config: BardConfig, client: SpotifyClient):
        super().__init__()
        self.config = config
        self.client = client
        self.header_widget = ArcaneHeader(is_playing=False, device_name=self.config.device_name)
        self.stage_widget = ZenStage()
        self.drawer_widget = CurtainDrawer(self.client, on_play=self.handle_drawer_play)
        self.bard_device_id: Optional[str] = None
        self._sync_timer = None
        self._tick_timer = None

    def compose(self) -> ComposeResult:
        yield self.header_widget
        yield self.drawer_widget
        yield self.stage_widget

    def on_mount(self) -> None:
        """Start timers and fetch initial state."""
        self._tick_timer = self.set_interval(1.0, self.on_progress_tick)
        self._sync_timer = self.set_interval(8.0, self.sync_playback_state)
        self.sync_playback_state()
        self.locate_bard_device()

    def on_progress_tick(self) -> None:
        """Smooth 1s ticker for progress bar."""
        self.stage_widget.tick_progress(1000)

    def _is_tv_or_remote(self, device: Dict[str, Any]) -> bool:
        """Check if a device is a TV or remote cast device that must NEVER be targeted."""
        dev_type = (device.get("type") or "").upper()
        dev_name = (device.get("name") or "").lower()
        if dev_type in ("TV", "CASTVIDEO", "AUDIODONGLE"):
            return True
        if "tv" in dev_name or "television" in dev_name or "chromecast" in dev_name or "apple tv" in dev_name:
            return True
        return False

    def _wake_local_spotify(self) -> None:
        """Attempt to silently launch local desktop Spotify client in background."""
        import platform
        import subprocess
        sys_name = platform.system()
        try:
            if sys_name == "Darwin":  # macOS
                subprocess.Popen(["open", "-g", "-a", "Spotify"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys_name == "Windows":
                subprocess.Popen(["cmd", "/c", "start", "spotify:"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _scan_and_bind_local_device(self) -> Optional[str]:
        """Query devices and bind to a local player (Bard daemon or Computer). Never targets TVs."""
        if self.client.is_rate_limited():
            return self.bard_device_id
        devices = self.client.get_devices()
        local_target = None
        target_name = None

        # Filter out ANY TV or remote device immediately
        valid_devices = [d for d in devices if not self._is_tv_or_remote(d)]

        # Priority 1: Device named Bard (our standalone engine)
        for d in valid_devices:
            if d.get("name") == self.config.device_name:
                local_target = d.get("id")
                target_name = d.get("name")
                break

        # Priority 2: Computer device matching current machine's hostname/node
        if not local_target:
            import socket
            import platform
            local_identifiers = {
                socket.gethostname().lower(),
                platform.node().lower(),
                socket.gethostname().split(".")[0].lower(),
            }
            for d in valid_devices:
                if d.get("type") == "Computer":
                    name = d.get("name", "").lower()
                    if any(ident in name or name in ident for ident in local_identifiers if ident):
                        local_target = d.get("id")
                        target_name = d.get("name")
                        break

        # Priority 3: Any local device of type Computer (e.g. desktop Spotify)
        if not local_target:
            for d in valid_devices:
                if d.get("type") == "Computer":
                    local_target = d.get("id")
                    target_name = d.get("name")
                    break

        # STRICT ENFORCEMENT: Never target TV or remote devices.
        if local_target:
            self.bard_device_id = local_target
            self.client.transfer_playback(local_target, play=False)
        else:
            self.bard_device_id = None

        try:
            self.call_from_thread(self.stage_widget.set_device_name, target_name)
        except Exception:
            pass
        return local_target

    @work(thread=True)
    def locate_bard_device(self) -> None:
        """Background discovery of local Spotify Connect receiver."""
        self._scan_and_bind_local_device()

    @work(thread=True)
    def sync_playback_state(self) -> None:
        """Background sync of playback state from Spotify Web API."""
        if self.client.is_rate_limited():
            return
        # If we don't have a bound local player yet, keep scanning for one
        if not self.bard_device_id:
            self._scan_and_bind_local_device()
        state = self.client.get_playback()
        self.call_from_thread(self._apply_playback_state, state)

    def _apply_playback_state(self, state: Optional[Dict[str, Any]]) -> None:
        """Apply state to widgets on UI thread."""
        if state:
            is_playing = state.get("is_playing", False)
            device_name = state.get("device_name", self.config.device_name)
            self.header_widget.update_status(is_playing=is_playing, device_name=device_name)
            self.stage_widget.update_playback(state)
        else:
            self.header_widget.update_status(is_playing=False)
            self.stage_widget.update_playback(None)

    def action_toggle_drawer(self) -> None:
        """Toggle left curtain drawer."""
        self.drawer_widget.toggle()

    def action_close_drawer(self) -> None:
        """Close drawer if open."""
        if self.drawer_widget.is_open():
            self.drawer_widget.hide()
            self.stage_widget.focus()

    def action_quit(self) -> None:
        """Pause playback on the local device and exit."""
        if self.bard_device_id:
            try:
                self.client.pause(device_id=self.bard_device_id)
            except Exception:
                pass
        self.exit()

    @work(thread=True)
    def action_toggle_playback(self) -> None:
        """Play or pause playback."""
        if self.client.is_rate_limited():
            self.call_from_thread(
                self.notify,
                self.client.get_cooldown_message(),
                title="Spotify",
                severity="warning",
                timeout=6,
            )
            return

        state = self.stage_widget.playback_data
        if state and state.get("is_playing"):
            self.client.pause(device_id=self.bard_device_id)
        else:
            if not self.bard_device_id:
                self._scan_and_bind_local_device()

            if not self.bard_device_id:
                # Try waking local Spotify app
                self._wake_local_spotify()
                import time
                time.sleep(1.5)
                self._scan_and_bind_local_device()

            if not self.bard_device_id:
                hint = "Install librespot ('brew install librespot')" if platform.system() == "Darwin" else "Check that Bard's audio engine is running"
                msg = (
                    f"No Spotify player found on this computer!\n"
                    f"{hint} or open Spotify.\n"
                    f"(Never routing audio to TV or remote devices)."
                )
                self.call_from_thread(
                    self.notify,
                    msg,
                    title="Local Audio Required",
                    severity="warning",
                    timeout=7,
                )
                return

            success, err_msg = self.client.play(device_id=self.bard_device_id)
            if not success:
                # Provide clear, friendly guidance if Spotify doesn't have an active track loaded to resume
                if "no active device" in (err_msg or "").lower() or not (state and state.get("title")):
                    msg = "No music is currently queued to resume.\nPress [Tab] to pick a playlist and start playing!"
                else:
                    msg = err_msg or "Could not resume playback. Please pick a playlist from [Tab]."
                self.call_from_thread(
                    self.notify,
                    msg,
                    title="Bard Audio",
                    severity="warning",
                    timeout=5,
                )
        self.sync_playback_state()

    @work(thread=True)
    def action_next_track(self) -> None:
        self.client.next_track(device_id=self.bard_device_id)
        self.sync_playback_state()

    @work(thread=True)
    def action_prev_track(self) -> None:
        self.client.previous_track(device_id=self.bard_device_id)
        self.sync_playback_state()

    @work(thread=True)
    def action_volume_up(self) -> None:
        state = self.stage_widget.playback_data
        curr_vol = state.get("volume", 50) if state else 50
        new_vol = min(100, curr_vol + 5)
        self.client.set_volume(new_vol, device_id=self.bard_device_id)
        if state:
            state["volume"] = new_vol
            self.call_from_thread(self.stage_widget.refresh_stage)

    @work(thread=True)
    def action_volume_down(self) -> None:
        state = self.stage_widget.playback_data
        curr_vol = state.get("volume", 50) if state else 50
        new_vol = max(0, curr_vol - 5)
        self.client.set_volume(new_vol, device_id=self.bard_device_id)
        if state:
            state["volume"] = new_vol
            self.call_from_thread(self.stage_widget.refresh_stage)

    @work(thread=True)
    def handle_drawer_play(self, play_args: Dict[str, Any]) -> None:
        """Handle playlist or track selection from drawer."""
        if not self.bard_device_id:
            self._scan_and_bind_local_device()

        if not self.bard_device_id:
            self._wake_local_spotify()
            import time
            time.sleep(1.5)
            self._scan_and_bind_local_device()

        if not self.bard_device_id:
            hint = "Install librespot ('brew install librespot')" if platform.system() == "Darwin" else "Check that Bard's audio engine is running"
            msg = (
                f"No Spotify player found on this computer!\n"
                f"{hint} or open Spotify.\n"
                f"(Never routing audio to TV or remote devices)."
            )
            self.call_from_thread(
                self.notify,
                msg,
                title="Local Audio Required",
                severity="warning",
                timeout=7,
            )
            return

        context_uri = play_args.get("context_uri")
        uris = play_args.get("uris") if not context_uri else None
        offset = play_args.get("offset")

        success, err_msg = self.client.play(
            context_uri=context_uri,
            uris=uris,
            offset=offset,
            device_id=self.bard_device_id,
        )

        # Fallback to direct track URIs if context playback with offset fails
        if not success and play_args.get("uris"):
            success, err_msg = self.client.play(
                uris=play_args.get("uris"),
                device_id=self.bard_device_id,
            )

        if not success:
            if "no active device" in (err_msg or "").lower() or not self.bard_device_id:
                hint = "('brew install librespot')" if platform.system() == "Darwin" else "via Bard's audio engine"
                msg = (
                    f"No active Spotify player found!\n"
                    f"Please open Spotify on this machine, or enable standalone playback {hint}."
                )
                self.call_from_thread(
                    self.notify,
                    msg,
                    title="Spotify Connect",
                    severity="warning",
                    timeout=7,
                )
            else:
                self.call_from_thread(
                    self.notify,
                    f"Playback error: {err_msg}",
                    title="Spotify",
                    severity="warning",
                    timeout=5,
                )
        else:
            import time
            time.sleep(0.5)
            self.sync_playback_state()
