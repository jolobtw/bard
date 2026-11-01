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

    @work(thread=True)
    def locate_bard_device(self) -> None:
        """Discover Bard or local PC Spotify Connect device ID and transfer playback to it."""
        if self.client.is_rate_limited():
            return
        devices = self.client.get_devices()
        local_target = None

        # Priority 1: Device named Bard
        for d in devices:
            if d.get("name") == self.config.device_name:
                local_target = d.get("id")
                break

        # Priority 2: Computer device (e.g. HOME-PC)
        if not local_target:
            for d in devices:
                if d.get("type") == "Computer":
                    local_target = d.get("id")
                    break

        # Priority 3: Any non-TV active device
        if not local_target:
            for d in devices:
                if d.get("type") != "TV":
                    local_target = d.get("id")
                    break

        if local_target:
            self.bard_device_id = local_target
            # Automatically reclaim playback control to this PC away from TV
            self.client.transfer_playback(local_target, play=False)

    @work(thread=True)
    def sync_playback_state(self) -> None:
        """Background sync of playback state from Spotify Web API."""
        if self.client.is_rate_limited():
            return
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
            success, err_msg = self.client.play(device_id=self.bard_device_id)
            if not success:
                if self.client.is_rate_limited():
                    self.call_from_thread(
                        self.notify,
                        self.client.get_cooldown_message(),
                        title="Spotify",
                        severity="warning",
                        timeout=6,
                    )
                    return
                self.locate_bard_device()
                success, err_msg = self.client.play(device_id=self.bard_device_id)
                if not success:
                    self.call_from_thread(
                        self.notify,
                        err_msg or "Could not resume playback. Please pick a playlist from [Tab].",
                        title="Spotify",
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
            self.locate_bard_device()

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
