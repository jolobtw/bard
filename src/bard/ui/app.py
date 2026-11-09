"""Main Bard Textual Application with YouTube Music & AudioPlayer."""

from __future__ import annotations

import logging
import webbrowser
from typing import Any, Dict, List, Optional
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding

from bard.audio_player import AudioPlayer
from bard.config import BardConfig
from bard.models import Track
from bard.oauth import YTMusicOAuth
from bard.ui.header import ArcaneHeader
from bard.ui.zen_stage import ZenStage
from bard.ui.curtain_drawer import CurtainDrawer
from bard.ytmusic_client import YTMusicClient

logger = logging.getLogger(__name__)


class BardApp(App):
    """The Arcane Terminal YouTube Music Player application."""

    CSS = """
    Screen {
        background: #13141C;
        layers: base overlay;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_playback", "Play/Pause", priority=True),
        Binding("tab", "toggle_drawer", "Explore", priority=True),
        Binding("escape", "close_drawer", "Close", priority=True),
        Binding("n", "next_track", "Next"),
        Binding("p", "prev_track", "Previous"),
        Binding("+", "volume_up", "Vol +"),
        Binding("=", "volume_up", "Vol +", show=False),
        Binding("-", "volume_down", "Vol -"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        config: BardConfig,
        client: Any,
        player: Optional[AudioPlayer] = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.client = client
        self.player = player

        self.header_widget = ArcaneHeader(is_playing=False, device_name="YouTube Music")
        self.stage_widget = ZenStage()
        self.drawer_widget = CurtainDrawer(
            self.client,
            on_play=self.handle_drawer_play,
            on_connect_account=self.handle_connect_account,
            on_disconnect_account=self.handle_disconnect_account,
        )

        self.queue: List[Track] = []
        self.current_index: int = -1
        self.current_track: Optional[Track] = None

        self.bard_device_id: Optional[str] = "local"
        self._sync_timer = None
        self._tick_timer = None
        self._had_started: bool = False
        self._last_known_pos: float = 0.0
        self._last_known_dur: float = 0.0
        self._user_paused: bool = False

    def compose(self) -> ComposeResult:
        yield self.header_widget
        yield self.drawer_widget
        yield self.stage_widget

    def on_mount(self) -> None:
        """Start timers and set initial state."""
        self._tick_timer = self.set_interval(1.0, self.on_progress_tick)
        self._sync_timer = self.set_interval(5.0, self.sync_playback_state)
        self.locate_bard_device()
        self.sync_playback_state()

    def locate_bard_device(self) -> None:
        """Set local audio output name."""
        self.stage_widget.set_device_name("YouTube Music / Standalone")

    def on_progress_tick(self) -> None:
        """Smooth 1s ticker for progress bar and track auto-advance."""
        if self.player:
            try:
                is_playing = self.player.is_playing()
                pos = self.player.get_position()
                dur = self.player.get_duration()
            except Exception:
                return

            if is_playing:
                self._had_started = True
                self._user_paused = False
                if dur > 0:
                    self._last_known_pos = pos
                    self._last_known_dur = dur
                if self.stage_widget.playback_data:
                    self.stage_widget.playback_data["is_playing"] = True
                    self.stage_widget.playback_data["progress_ms"] = int(pos * 1000)
                    if dur > 0:
                        self.stage_widget.playback_data["duration_ms"] = int(dur * 1000)
                    self.stage_widget._current_progress_ms = int(pos * 1000)
                    self.stage_widget.refresh_stage()
            else:
                # If playback was active and stopped near end of track, auto-advance
                if (
                    not self._user_paused
                    and self._had_started
                    and self._last_known_dur > 0
                    and self._last_known_pos >= max(1.0, self._last_known_dur - 3.0)
                ):
                    self._had_started = False
                    self._last_known_pos = 0.0
                    self._last_known_dur = 0.0
                    self.action_next_track()
        else:
            self.stage_widget.tick_progress(1000)

    def sync_playback_state(self) -> None:
        """Poll local player status and update UI state."""
        if not self.player:
            return
        try:
            is_playing = self.player.is_playing()
            vol = self.player.get_volume()
            pos = self.player.get_position()
            dur = self.player.get_duration()
        except Exception:
            return

        if self.stage_widget.playback_data:
            self.stage_widget.playback_data["is_playing"] = is_playing
            self.stage_widget.playback_data["volume"] = vol
            self.stage_widget.playback_data["progress_ms"] = int(pos * 1000)
            if dur > 0:
                self.stage_widget.playback_data["duration_ms"] = int(dur * 1000)
            self.stage_widget._current_progress_ms = int(pos * 1000)
            self.header_widget.update_status(is_playing=is_playing, device_name="YouTube Music")
            self.stage_widget.refresh_stage()

    def handle_drawer_play(self, track: Any) -> None:
        """Handle track selection from drawer."""
        if isinstance(track, Track):
            track_obj = track
        elif isinstance(track, dict):
            track_obj = Track(
                id=track.get("id", ""),
                title=track.get("title", "Unknown"),
                artist=track.get("artist", "Unknown Artist"),
                album=track.get("album", ""),
                duration_seconds=track.get("duration_seconds", 0),
                thumbnail_url=track.get("thumbnail_url", track.get("album_art_url", "")),
                stream_url=track.get("stream_url"),
            )
        else:
            return

        if hasattr(self.drawer_widget, "tracks") and self.drawer_widget.tracks:
            self.queue = list(self.drawer_widget.tracks)
            try:
                self.current_index = self.queue.index(track_obj)
            except ValueError:
                matching = [i for i, t in enumerate(self.queue) if t.id == track_obj.id]
                self.current_index = matching[0] if matching else 0
        else:
            self.queue = [track_obj]
            self.current_index = 0

        self.play_track(track_obj)

    def play_track(self, track: Track) -> None:
        """Set track as current and start background resolution & playback."""
        self.current_track = track
        self._play_track_worker(track)

    def play_track_at_index(self, index: int) -> None:
        """Play track at specific queue index."""
        if 0 <= index < len(self.queue):
            self.current_index = index
            track = self.queue[index]
            self.play_track(track)

    @work(thread=True, exclusive=True, group="player_stream")
    def _play_track_worker(self, track: Track) -> None:
        """Background worker to extract stream URL and initiate audio playback."""
        stream_url = track.stream_url
        if not stream_url and hasattr(self.client, "get_stream_url"):
            try:
                stream_url = self.client.get_stream_url(track.id)
            except Exception as e:
                logger.error("Failed to extract stream for %s: %s", track.id, e)
                if self.is_mounted:
                    self.call_from_thread(
                        self.notify,
                        f"Error extracting stream: {e}",
                        title="YouTube Music",
                        severity="error",
                        timeout=5,
                    )
                return

        if not stream_url:
            if self.is_mounted:
                self.call_from_thread(
                    self.notify,
                    f"Could not resolve audio stream for '{track.title}'.",
                    title="Playback Error",
                    severity="error",
                    timeout=5,
                )
            return

        track.stream_url = stream_url

        if self.player:
            try:
                success = self.player.play(stream_url)
                if not success:
                    if self.is_mounted:
                        self.call_from_thread(
                            self.notify,
                            f"Audio engine failed to play '{track.title}'.",
                            title="Audio Player Error",
                            severity="error",
                            timeout=5,
                        )
                    return
            except Exception as e:
                logger.error("Player play error: %s", e)
                if self.is_mounted:
                    self.call_from_thread(
                        self.notify,
                        f"Playback failed: {e}",
                        title="Audio Player Error",
                        severity="error",
                        timeout=5,
                    )
                return

        self._had_started = True
        self._user_paused = False
        self._last_known_pos = 0.0
        self._last_known_dur = float(track.duration_seconds or 0)

        track_data = track.to_dict()
        track_data["is_playing"] = True
        if self.player:
            try:
                track_data["volume"] = self.player.get_volume()
            except Exception:
                pass

        if self.is_mounted:
            self.call_from_thread(self._on_track_started, track_data)
        else:
            self._on_track_started(track_data)

    def _on_track_started(self, track_data: Dict[str, Any]) -> None:
        """Update UI widgets when playback starts."""
        self.stage_widget.update_track(track_data)
        self.header_widget.update_status(is_playing=True, device_name="YouTube Music")

    def action_toggle_playback(self) -> None:
        """Play or pause local playback."""
        if self.player:
            try:
                if self.player.is_playing():
                    self.player.pause()
                    self._user_paused = True
                    if self.stage_widget.playback_data:
                        self.stage_widget.playback_data["is_playing"] = False
                    self.header_widget.update_status(is_playing=False, device_name="YouTube Music")
                    self.stage_widget.refresh_stage()
                else:
                    self._user_paused = False
                    if self.current_track or (
                        self.stage_widget.playback_data and self.stage_widget.playback_data.get("title")
                    ):
                        self.player.resume()
                        if self.stage_widget.playback_data:
                            self.stage_widget.playback_data["is_playing"] = True
                        self.header_widget.update_status(is_playing=True, device_name="YouTube Music")
                        self.stage_widget.refresh_stage()
                    elif self.queue and len(self.queue) > 0:
                        idx = max(0, self.current_index)
                        self.play_track_at_index(idx)
                    else:
                        self.notify(
                            "No music currently loaded.\nPress [Tab] to explore and pick a track!",
                            title="Bard Audio",
                            severity="information",
                            timeout=5,
                        )
            except Exception:
                pass
        else:
            self.notify(
                "Audio player not initialized.\nPress [Tab] to explore and select a track.",
                title="Bard Audio",
                severity="warning",
                timeout=5,
            )

    def action_next_track(self) -> None:
        """Skip to next track in queue."""
        if self.queue and len(self.queue) > 0:
            next_idx = self.current_index + 1
            if next_idx < len(self.queue):
                self.play_track_at_index(next_idx)
            else:
                self.notify("Queue completed. Press [Tab] to browse more tracks.", title="Bard Queue", severity="information", timeout=3)
        else:
            self.notify("No tracks in queue. Press [Tab] to explore.", title="Bard Queue", severity="information", timeout=3)

    def action_prev_track(self) -> None:
        """Previous track in queue or restart current track."""
        pos = 0.0
        if self.player:
            try:
                pos = self.player.get_position()
            except Exception:
                pos = 0.0
            if pos > 3.0:
                self.player.seek(-pos)
                if self.stage_widget.playback_data:
                    self.stage_widget.playback_data["progress_ms"] = 0
                    self.stage_widget._current_progress_ms = 0
                    self.stage_widget.refresh_stage()
                return

        if self.queue and self.current_index > 0:
            self.play_track_at_index(self.current_index - 1)
        elif self.player:
            try:
                self.player.seek(-pos)
                if self.stage_widget.playback_data:
                    self.stage_widget.playback_data["progress_ms"] = 0
                    self.stage_widget._current_progress_ms = 0
                    self.stage_widget.refresh_stage()
            except Exception:
                pass

    def action_volume_up(self) -> None:
        """Increase volume by 5%."""
        if self.player:
            try:
                curr = self.player.get_volume()
                new_vol = min(100, curr + 5)
                self.player.set_volume(new_vol)
                if self.stage_widget.playback_data:
                    self.stage_widget.playback_data["volume"] = new_vol
                    self.stage_widget.refresh_stage()
            except Exception:
                pass

    def action_volume_down(self) -> None:
        """Decrease volume by 5%."""
        if self.player:
            try:
                curr = self.player.get_volume()
                new_vol = max(0, curr - 5)
                self.player.set_volume(new_vol)
                if self.stage_widget.playback_data:
                    self.stage_widget.playback_data["volume"] = new_vol
                    self.stage_widget.refresh_stage()
            except Exception:
                pass

    def action_toggle_drawer(self) -> None:
        """Toggle left curtain drawer."""
        self.drawer_widget.toggle()

    def action_close_drawer(self) -> None:
        """Close drawer if open."""
        if self.drawer_widget.is_open():
            self.drawer_widget.hide()
            self.stage_widget.focus()

    def action_quit(self) -> None:
        """Pause playback, terminate audio player cleanly, and exit."""
        if self.player:
            try:
                self.player.pause()
            except Exception:
                pass
            try:
                self.player.close()
            except Exception:
                pass
        self.exit()

    def on_unmount(self) -> None:
        """Ensure audio engine is stopped when application unmounts."""
        if self.player:
            try:
                self.player.close()
            except Exception:
                pass

    def _safe_call(self, callback: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute callback on main Textual thread if running in background thread, else directly."""
        import threading
        if self._loop is not None and getattr(self, "_thread", None) != threading.current_thread():
            try:
                return self.call_from_thread(callback, *args, **kwargs)
            except RuntimeError:
                pass
        return callback(*args, **kwargs)

    def handle_connect_account(self) -> None:
        """Initiate OAuth 2.0 device pairing workflow."""
        if self._loop is not None and self.is_running:
            self._connect_account_worker()
        else:
            self._connect_account_sync()

    @work(thread=True, exclusive=True, group="account_pairing")
    def _connect_account_worker(self) -> None:
        """Background worker for device code retrieval and token polling."""
        self._connect_account_sync()

    def _connect_account_sync(self, oauth: Optional[YTMusicOAuth] = None) -> bool:
        """Core logic for device pairing flow."""
        if oauth is None:
            oauth = YTMusicOAuth(config=self.config)

        try:
            device_data = oauth.get_device_code()
        except Exception as e:
            logger.error("Failed to retrieve device code: %s", e)
            device_data = None

        if not device_data or not device_data.get("device_code") or not device_data.get("user_code"):
            self._safe_call(
                self.notify,
                "Failed to get YouTube Music device pairing code.",
                title="Pairing Error",
                severity="error",
            )
            return False

        verification_url = device_data.get("verification_url", "https://www.google.com/device")
        user_code = device_data["user_code"]
        device_code = device_data["device_code"]
        interval = device_data.get("interval", 5)

        try:
            webbrowser.open(verification_url)
        except Exception:
            pass

        pairing_msg = f"Pair at {verification_url} with code: {user_code}"
        self._safe_call(
            self.notify,
            pairing_msg,
            title="YouTube Music Pairing",
            timeout=15,
        )

        token_data = oauth.poll_for_token(device_code, interval=interval)
        if token_data:
            def _apply_login() -> None:
                self.client = YTMusicClient(oauth=oauth)
                self.drawer_widget.client = self.client
                self.drawer_widget.refresh_categories()
                self.notify(
                    "Connected to YouTube Music successfully!",
                    title="Account Linked",
                )

            self._safe_call(_apply_login)
            return True
        else:
            self._safe_call(
                self.notify,
                "YouTube Music pairing timed out or cancelled.",
                title="Pairing Error",
                severity="error",
            )
            return False

    def handle_disconnect_account(self) -> None:
        """Clear tokens and restore unauthenticated client."""
        oauth = YTMusicOAuth(config=self.config)
        oauth.clear_tokens()
        self.client = YTMusicClient()
        self.drawer_widget.client = self.client
        self.drawer_widget.refresh_categories()
        self.notify("Disconnected from YouTube Music.", title="Account")

