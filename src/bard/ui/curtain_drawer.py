"""Left-Side Curtain Drawer for browsing and selecting playlists and tracks."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from bard.spotify_client import SpotifyClient


class CurtainDrawer(Widget):
    """Dual-tier slide-out drawer on the left side for playlists and tracklist."""

    DEFAULT_CSS = """
    CurtainDrawer {
        dock: left;
        width: 62;
        height: 100%;
        background: #181A24;
        border-right: heavy #FF7A00;
        layer: overlay;
        display: none;
        padding: 0 1;
    }

    CurtainDrawer.-visible {
        display: block;
    }

    #drawer-title-bar {
        height: 2;
        width: 100%;
        border-bottom: solid #2E3244;
        color: #FF7A00;
        text-style: bold;
        content-align: center middle;
    }

    #drawer-columns {
        width: 100%;
        height: 1fr;
    }

    #playlist-column {
        width: 1fr;
        height: 100%;
        border-right: solid #2E3244;
    }

    #track-column {
        width: 1fr;
        height: 100%;
    }

    OptionList {
        background: #181A24;
        border: none;
        scrollbar-gutter: stable;
    }

    OptionList:focus {
        border: none;
    }

    OptionList > .option-list--option-highlighted {
        background: #262938;
        color: #FFD166;
        text-style: bold;
    }

    #drawer-footer {
        height: 2;
        width: 100%;
        border-top: solid #2E3244;
        color: #6C7086;
        content-align: center middle;
    }
    """

    def __init__(self, spotify_client: SpotifyClient, on_play: Optional[Callable[[Dict[str, Any]], None]] = None):
        super().__init__()
        self.client = spotify_client
        self.on_play = on_play
        self.playlists: List[Dict[str, Any]] = []
        self.tracks: List[Dict[str, Any]] = []
        self._active_column = "playlists"  # "playlists" or "tracks"

    def compose(self) -> ComposeResult:
        yield Static("󰲸 YOUR PLAYLISTS                󰲸 TRACKS", id="drawer-title-bar")
        with Horizontal(id="drawer-columns"):
            with Vertical(id="playlist-column"):
                yield OptionList(id="playlist-list")
            with Vertical(id="track-column"):
                yield OptionList(id="track-list")
        yield Static("[←/→] Switch Column  [Enter] Play  [Esc] Close", id="drawer-footer")

    def toggle(self) -> None:
        """Toggle drawer visibility."""
        if self.has_class("-visible"):
            self.remove_class("-visible")
        else:
            self.add_class("-visible")
            self.refresh_playlists()
            self.query_one("#playlist-list", OptionList).focus()

    def hide(self) -> None:
        """Close drawer."""
        self.remove_class("-visible")

    def is_open(self) -> bool:
        return self.has_class("-visible")

    def refresh_playlists(self) -> None:
        """Fetch user's playlists and populate the playlist column."""
        self.playlists = self.client.get_playlists()
        plist = self.query_one("#playlist-list", OptionList)
        plist.clear_options()

        for idx, p in enumerate(self.playlists):
            name = p.get("name", "Untitled")
            count = p.get("tracks_count", 0)
            plist.add_option(Option(f"󰲸 {name} ({count})", id=str(idx)))

        if self.playlists:
            plist.highlighted = 0
            self.load_tracks_for_playlist(0)

    def load_tracks_for_playlist(self, index: int) -> None:
        """Load tracks for the selected playlist into the track column."""
        if 0 <= index < len(self.playlists):
            pid = self.playlists[index].get("id")
            if pid:
                self.tracks = self.client.get_playlist_tracks(pid)
                tlist = self.query_one("#track-list", OptionList)
                tlist.clear_options()
                for idx, t in enumerate(self.tracks):
                    name = t.get("name", "Unknown")
                    dur = t.get("duration_str", "")
                    tlist.add_option(Option(f"{idx+1}. {name} - {dur}", id=str(idx)))

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """When playlist selection moves, preview its tracks."""
        if event.option_list.id == "playlist-list" and event.option_index is not None:
            self.load_tracks_for_playlist(event.option_index)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """When Enter is pressed on an option, trigger playback."""
        if event.option_list.id == "playlist-list" and event.option_index is not None:
            # Play entire playlist
            if 0 <= event.option_index < len(self.playlists):
                selected = self.playlists[event.option_index]
                if self.on_play:
                    self.on_play({"context_uri": selected.get("uri")})
                self.hide()
        elif event.option_list.id == "track-list" and event.option_index is not None:
            # Play specific track
            if 0 <= event.option_index < len(self.tracks):
                selected = self.tracks[event.option_index]
                if self.on_play:
                    self.on_play({"uris": [selected.get("uri")]})
                self.hide()
