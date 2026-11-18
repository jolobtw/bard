"""Main Bard stage widget: two-tier spectrum + 3-column command deck + footer."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget

from bard.models import Track
from bard.ui.palette import BG_OBSIDIAN
from bard.ui.spectrum import (
    SeekBar,
    SpectrumDeck,
    format_ms,
    render_arcane_bar,
    render_flame_progress,
)
from bard.ui.stage_widgets import (
    ArtifactPanel,
    ControlsPanel,
    QueuePanel,
    VolumeBar,
)

__all__ = [
    "SeekBar",
    "SpectrumDeck",
    "ArtifactPanel",
    "QueuePanel",
    "ControlsPanel",
    "VolumeBar",
    "ZenStage",
    "format_ms",
    "render_arcane_bar",
    "render_flame_progress",
]


class ZenStage(Widget):
    """Two-tier Obsidian & Ember stage composing SpectrumDeck and 3-column Command Deck."""

    DEFAULT_CSS = f"""
    ZenStage {{
        width: 100%;
        height: 1fr;
        background: {BG_OBSIDIAN};
        padding: 0 1;
    }}

    #stage-root {{
        width: 100%;
        height: 100%;
        background: {BG_OBSIDIAN};
    }}

    #command-deck {{
        width: 100%;
        height: 1fr;
        background: {BG_OBSIDIAN};
    }}

    ArtifactPanel {{
        margin-right: 1;
    }}

    QueuePanel {{
        margin-right: 1;
    }}
    """

    def __init__(
        self,
        on_prev: Optional[Callable[[], None]] = None,
        on_play_pause: Optional[Callable[[], None]] = None,
        on_next: Optional[Callable[[], None]] = None,
        on_shuffle: Optional[Callable[[], None]] = None,
        on_repeat: Optional[Callable[[], None]] = None,
        on_seek: Optional[Callable[[float], None]] = None,
        on_volume: Optional[Callable[[int], None]] = None,
        on_mute: Optional[Callable[[], None]] = None,
        on_select_queue_index: Optional[Callable[[int], None]] = None,
        on_cycle_device: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__()
        self.on_prev = on_prev
        self.on_play_pause = on_play_pause
        self.on_next = on_next
        self.on_shuffle = on_shuffle
        self.on_repeat = on_repeat
        self.on_seek = on_seek
        self.on_volume = on_volume
        self.on_mute = on_mute
        self.on_select_queue_index = on_select_queue_index
        self.on_cycle_device = on_cycle_device

        self.shuffle_enabled: bool = False
        self.repeat_mode: str = "off"
        self.playback_data: Optional[Dict[str, Any]] = None
        self._current_progress_ms: int = 0
        self._current_volume: int = 100
        self.device_name: Optional[str] = None
        self._audio_info: Dict[str, Any] = {}
        self._audio_device_label: str = "MPV // Default Output"
        self._queue: List[Track] = []
        self._queue_index: int = -1

    def compose(self) -> ComposeResult:
        with Vertical(id="stage-root"):
            yield SpectrumDeck(on_seek=self._handle_seek, id="spectrum-deck")
            with Horizontal(id="command-deck"):
                yield ArtifactPanel(id="artifact-panel")
                yield QueuePanel(on_select_index=self._handle_select_queue_index, id="queue-panel")
                yield ControlsPanel(
                    on_prev=self._handle_prev,
                    on_play_pause=self._handle_play_pause,
                    on_next=self._handle_next,
                    on_shuffle=self._handle_shuffle,
                    on_repeat=self._handle_repeat,
                    on_volume=self._handle_volume,
                    on_mute=self._handle_mute,
                    on_cycle_device=self._handle_cycle_device,
                    id="controls-panel",
                )

    def on_mount(self) -> None:
        self.refresh_stage()

    def _handle_prev(self) -> None:
        if self.on_prev:
            self.on_prev()
        elif self.app and hasattr(self.app, "action_prev_track"):
            self.app.action_prev_track()

    def _handle_play_pause(self) -> None:
        if self.on_play_pause:
            self.on_play_pause()
        elif self.app and hasattr(self.app, "action_toggle_playback"):
            self.app.action_toggle_playback()

    def _handle_next(self) -> None:
        if self.on_next:
            self.on_next()
        elif self.app and hasattr(self.app, "action_next_track"):
            self.app.action_next_track()

    def _handle_shuffle(self) -> None:
        if self.on_shuffle:
            self.on_shuffle()
        elif self.app and hasattr(self.app, "action_toggle_shuffle"):
            self.app.action_toggle_shuffle()

    def _handle_repeat(self) -> None:
        if self.on_repeat:
            self.on_repeat()
        elif self.app and hasattr(self.app, "action_cycle_repeat"):
            self.app.action_cycle_repeat()

    def _handle_seek(self, position_seconds: float) -> None:
        if self.on_seek:
            self.on_seek(position_seconds)
        elif self.app and hasattr(self.app, "action_seek_to"):
            self.app.action_seek_to(position_seconds)

    def _handle_volume(self, volume: int) -> None:
        if self.on_volume:
            self.on_volume(volume)
        elif self.app and hasattr(self.app, "action_set_volume"):
            self.app.action_set_volume(volume)

    def _handle_mute(self) -> None:
        if self.on_mute:
            self.on_mute()
        elif self.app and hasattr(self.app, "action_toggle_mute"):
            self.app.action_toggle_mute()

    def _handle_select_queue_index(self, index: int) -> None:
        if self.on_select_queue_index:
            self.on_select_queue_index(index)
        elif self.app and hasattr(self.app, "play_track_at_index"):
            self.app.play_track_at_index(index)

    def _handle_cycle_device(self) -> None:
        if self.on_cycle_device:
            self.on_cycle_device()
        elif self.app and hasattr(self.app, "action_cycle_output_device"):
            self.app.action_cycle_output_device()

    def set_shuffle(self, enabled: bool) -> None:
        """Update shuffle toggle state and refresh controls."""
        self.shuffle_enabled = bool(enabled)
        self._sync_controls()

    def set_repeat(self, mode: str) -> None:
        """Update repeat mode ('off', 'all', 'one') and refresh controls."""
        self.repeat_mode = mode if mode in ("off", "all", "one") else "off"
        self._sync_controls()

    def set_device_name(self, name: Optional[str]) -> None:
        """Update active source/engine label."""
        self.device_name = name
        if self.is_mounted:
            self.refresh_stage()

    def set_audio_device(self, label: str) -> None:
        """Update output route sink label in ControlsPanel."""
        cleaned = (label or "").strip() or "MPV // Default Output"
        self._audio_device_label = cleaned
        if self.is_mounted:
            try:
                self.query_one("#controls-panel", ControlsPanel).set_device_label(cleaned)
            except Exception:
                pass

    def set_audio_info(self, info: Dict[str, Any]) -> None:
        """Update real stream codec and sample rate metadata."""
        self._audio_info = dict(info or {})
        if self.is_mounted:
            try:
                self.query_one("#artifact-panel", ArtifactPanel).set_audio_info(self._audio_info)
            except Exception:
                pass

    def set_queue(self, tracks: Sequence[Track], current_index: int) -> None:
        """Synchronize the QueuePanel with BardApp's active queue."""
        self._queue = list(tracks)
        self._queue_index = current_index
        if self.is_mounted:
            try:
                self.query_one("#queue-panel", QueuePanel).set_queue(self._queue, self._queue_index)
            except Exception:
                pass
            self._sync_artifact_panel()

    def move_queue_cursor(self, delta: int) -> None:
        """Move QueuePanel cursor by delta rows."""
        if self.is_mounted:
            try:
                self.query_one("#queue-panel", QueuePanel).move_cursor(delta)
            except Exception:
                pass

    def get_selected_queue_index(self) -> Optional[int]:
        """Return original queue index of cursor row, or None."""
        if self.is_mounted:
            try:
                return self.query_one("#queue-panel", QueuePanel).selected_original_index()
            except Exception:
                pass
        return None

    def focus_queue_filter(self) -> None:
        """Focus QueuePanel filter input."""
        if self.is_mounted:
            try:
                self.query_one("#queue-panel", QueuePanel).focus_filter()
            except Exception:
                pass

    def blur_queue_filter(self, clear: bool = False) -> None:
        """Blur QueuePanel filter input."""
        if self.is_mounted:
            try:
                self.query_one("#queue-panel", QueuePanel).blur_filter(clear=clear)
            except Exception:
                pass

    def clear_queue_filter(self) -> None:
        """Clear QueuePanel filter text."""
        if self.is_mounted:
            try:
                self.query_one("#queue-panel", QueuePanel).clear_filter()
            except Exception:
                pass

    def is_queue_filter_focused(self) -> bool:
        """Return True if QueuePanel filter input is currently focused."""
        if self.is_mounted:
            try:
                return self.query_one("#queue-panel", QueuePanel).has_filter_focus()
            except Exception:
                pass
        return False

    def has_queue_filter_text(self) -> bool:
        """Return True if QueuePanel has an active filter string."""
        if self.is_mounted:
            try:
                return self.query_one("#queue-panel", QueuePanel).has_filter_text()
            except Exception:
                pass
        return False

    def get_art_dimensions(self) -> Tuple[int, int]:
        """Return proportional album art dimensions from ArtifactPanel."""
        if self.is_mounted:
            try:
                return self.query_one("#artifact-panel", ArtifactPanel).get_art_dimensions()
            except Exception:
                pass
        w = self.size.width or (self.app.size.width if self.app else 100)
        h = self.size.height or (self.app.size.height if self.app else 40)
        col_w = max(20, w // 3)
        deck_h = max(14, h - 14)
        return (max(18, min(32, col_w - 6)), max(7, min(14, deck_h - 10)))

    def update_volume(self, volume: int) -> None:
        """Update volume slider without re-rendering artwork or spectrum."""
        clamped = max(0, min(100, int(volume)))
        self._current_volume = clamped
        if self.is_mounted:
            try:
                self.query_one("#controls-panel", ControlsPanel).set_volume(clamped)
            except Exception:
                pass

    def update_track(self, track: Optional[Dict[str, Any]]) -> None:
        """Update stage with a newly selected track dictionary."""
        if track:
            data = dict(self.playback_data) if self.playback_data else {}
            data.update(track)
            if "duration_ms" not in data and "duration_seconds" in data:
                data["duration_ms"] = (data.get("duration_seconds") or 0) * 1000
            data["is_playing"] = data.get("is_playing", True)
            data["progress_ms"] = data.get("progress_ms", 0)
            if "device_name" not in data:
                data["device_name"] = self.device_name or "YouTube Music"
            self.update_playback(data)
        else:
            self.update_playback(None)

    def update_playback(self, data: Optional[Dict[str, Any]]) -> None:
        """Update stage with fresh playback data."""
        self.playback_data = data
        if data:
            self._current_progress_ms = int(data.get("progress_ms", 0) or 0)
        else:
            self._current_progress_ms = 0
        self.refresh_stage()

    def update_progress(self, progress_ms: int, duration_ms: int) -> None:
        """Update SeekBar progress without re-rendering artwork or queue."""
        self._current_progress_ms = max(0, int(progress_ms))
        if self.is_mounted:
            try:
                self.query_one("#spectrum-deck", SpectrumDeck).set_progress(
                    self._current_progress_ms, int(duration_ms)
                )
            except Exception:
                pass

    def tick_progress(self, delta_ms: int = 1000) -> None:
        """Advance progress bar by delta if currently playing."""
        if self.playback_data and self.playback_data.get("is_playing"):
            duration = int(self.playback_data.get("duration_ms", 0) or 0)
            if duration > 0 and self._current_progress_ms < duration:
                self.update_progress(min(duration, self._current_progress_ms + delta_ms), duration)

    def _sync_artifact_panel(self) -> None:
        if not self.is_mounted:
            return
        total = len(self._queue)
        pos = (self._queue_index + 1, total) if (total > 0 and self._queue_index >= 0) else (1, 1) if self.playback_data else (0, 0)
        try:
            self.query_one("#artifact-panel", ArtifactPanel).set_track(
                self.playback_data,
                queue_pos=pos,
                audio_info=self._audio_info,
            )
        except Exception:
            pass

    def _sync_controls(self) -> None:
        if not self.is_mounted:
            return
        is_playing = bool(self.playback_data and self.playback_data.get("is_playing", False))
        vol = int(self.playback_data.get("volume", self._current_volume)) if self.playback_data else self._current_volume
        self._current_volume = vol
        try:
            self.query_one("#controls-panel", ControlsPanel).set_state(
                is_playing=is_playing,
                has_track=bool(self.playback_data),
                shuffle_enabled=self.shuffle_enabled,
                repeat_mode=self.repeat_mode,
                volume=vol,
                device_name=self._audio_device_label,
            )
        except Exception:
            pass

    def refresh_stage(self) -> None:
        """Re-render all stage sub-panels."""
        if not self.is_mounted:
            return
        is_playing = bool(self.playback_data and self.playback_data.get("is_playing", False))
        duration = int(self.playback_data.get("duration_ms", 0) or 0) if self.playback_data else 0
        try:
            self.query_one("#spectrum-deck", SpectrumDeck).set_state(
                is_playing=is_playing,
                has_track=bool(self.playback_data),
                progress_ms=self._current_progress_ms,
                duration_ms=duration,
            )
        except Exception:
            pass
        self._sync_artifact_panel()
        try:
            self.query_one("#queue-panel", QueuePanel).set_queue(self._queue, self._queue_index)
        except Exception:
            pass
        self._sync_controls()
