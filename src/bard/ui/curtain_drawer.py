"""Left-Side Curtain Drawer for browsing and selecting playlists and tracks."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from rich.text import Text
from textual import events, work
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
        width: 88%;
        min-width: 86;
        max-width: 140;
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
        width: 42%;
        min-width: 36;
        max-width: 50;
        height: 100%;
        border-right: solid #2E3244;
    }

    #playlist-header {
        height: 2;
        width: 100%;
        border-bottom: solid #2E3244;
        padding: 0 1;
        content-align: left middle;
    }

    #track-column {
        width: 1fr;
        height: 100%;
    }

    #track-header {
        height: 2;
        width: 100%;
        border-bottom: solid #2E3244;
        padding: 0 1;
        content-align: left middle;
    }

    OptionList {
        background: #181A24;
        color: #A6ADC8;
        border: none;
        scrollbar-gutter: stable;
        padding: 0;
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
        color: #A6ADC8;
        content-align: center middle;
    }
    """

    def __init__(self, spotify_client: SpotifyClient, on_play: Optional[Callable[[Dict[str, Any]], None]] = None):
        super().__init__()
        self.client = spotify_client
        self.on_play = on_play
        self.playlists: List[Dict[str, Any]] = []
        self.tracks: List[Dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Static("✦  ❖  YOUR MUSIC LIBRARY  ❖  ✦", id="drawer-title-bar")
        with Horizontal(id="drawer-columns"):
            with Vertical(id="playlist-column"):
                yield Static("▸ PLAYLISTS (0)", id="playlist-header")
                yield OptionList(id="playlist-list")
            with Vertical(id="track-column"):
                yield Static("  TRACKS (0)", id="track-header")
                yield OptionList(id="track-list")
        yield Static(
            "[#FFD166]← / →[/] Switch Column   [#FFD166]↑ / ↓[/] Navigate   [#FFD166]Enter[/] Play   [#FFD166]Esc[/] Close",
            id="drawer-footer",
        )

    def toggle(self) -> None:
        """Toggle drawer visibility."""
        if self.has_class("-visible"):
            self.remove_class("-visible")
        else:
            self.add_class("-visible")
            plist = self.query_one("#playlist-list", OptionList)
            plist.focus()
            self._update_column_headers()
            self.refresh_playlists()

    def hide(self) -> None:
        """Close drawer."""
        self.remove_class("-visible")

    def is_open(self) -> bool:
        return self.has_class("-visible")

    def _update_column_headers(self) -> None:
        """Highlight active column header based on focus."""
        try:
            p_header = self.query_one("#playlist-header", Static)
            t_header = self.query_one("#track-header", Static)
            plist = self.query_one("#playlist-list", OptionList)
            tlist = self.query_one("#track-list", OptionList)

            p_count = len(self.playlists)
            t_count = len(self.tracks)

            if plist.has_focus:
                p_header.update(f"[bold #FFD166]▸ PLAYLISTS[/]  [#6C7086]({p_count})[/]")
                t_header.update(f"[#6C7086]  TRACKS  ({t_count})[/]")
            elif tlist.has_focus:
                p_header.update(f"[#6C7086]  PLAYLISTS  ({p_count})[/]")
                t_header.update(f"[bold #FFD166]▸ TRACKS[/]  [#6C7086]({t_count})[/]")
            else:
                p_header.update(f"[#FF7A00]PLAYLISTS[/]  [#6C7086]({p_count})[/]")
                t_header.update(f"[#FF7A00]TRACKS[/]  [#6C7086]({t_count})[/]")
        except Exception:
            pass

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        """Keep column headers in sync when focus shifts."""
        self._update_column_headers()

    def on_key(self, event: events.Key) -> None:
        """Handle left/right navigation between columns."""
        if event.key in ("right", "l"):
            tlist = self.query_one("#track-list", OptionList)
            if self.tracks:
                tlist.focus()
                if tlist.highlighted is None:
                    tlist.highlighted = 0
                self._update_column_headers()
                event.stop()
        elif event.key in ("left", "h"):
            plist = self.query_one("#playlist-list", OptionList)
            plist.focus()
            self._update_column_headers()
            event.stop()

    def refresh_playlists(self) -> None:
        """Fetch user's playlists and populate the playlist column."""
        plist = self.query_one("#playlist-list", OptionList)
        tlist = self.query_one("#track-list", OptionList)

        # If already cached in client, populate immediately
        cache = getattr(self.client, "_playlists_cache", None)
        if isinstance(cache, list):
            self._populate_playlists(cache)
            return

        # Otherwise display immediate loading state and fetch in background
        plist.clear_options()
        plist.add_option(Option(Text("  ✦ Deciphering playlists...", style="#FFD166 italic"), id="loading_pl", disabled=True))
        tlist.clear_options()
        tlist.add_option(Option(Text("  ✦ Waiting for library...", style="#6C7086 italic"), id="waiting_tr", disabled=True))
        self._load_playlists_worker()

    @work(thread=True, exclusive=True, group="playlist_fetch")
    def _load_playlists_worker(self) -> None:
        playlists = self.client.get_playlists()
        self.app.call_from_thread(self._populate_playlists, playlists)

    def _populate_playlists(self, playlists: List[Dict[str, Any]]) -> None:
        self.playlists = playlists
        plist = self.query_one("#playlist-list", OptionList)
        plist.clear_options()

        if not self.playlists:
            msg = "  [Rate limited / Cooldown in effect]" if self.client.is_rate_limited() else "  No playlists found"
            plist.add_option(Option(Text(msg, style="#6C7086 italic"), disabled=True))
            self._update_column_headers()
            return

        for idx, p in enumerate(self.playlists):
            raw_name = p.get("name", "Untitled") or "Untitled"
            clean_name = f"{raw_name[:23]}..." if len(raw_name) > 26 else raw_name
            count = p.get("tracks_count", 0)
            label = f" {clean_name:<26}  [{count:>3}]"
            plist.add_option(Option(Text(label, no_wrap=True), id=str(idx)))

        self._update_column_headers()

        if self.playlists:
            plist.highlighted = 0
            self.load_tracks_for_playlist(0)

    def load_tracks_for_playlist(self, index: int) -> None:
        """Load tracks for the selected playlist into the track column."""
        tlist = self.query_one("#track-list", OptionList)
        tlist.clear_options()

        if not (0 <= index < len(self.playlists)):
            self.tracks = []
            self._update_column_headers()
            return

        pid = self.playlists[index].get("id")
        if not pid:
            self.tracks = []
            self._update_column_headers()
            return

        # If already cached, populate immediately
        tracks_cache = getattr(self.client, "_tracks_cache", None)
        if isinstance(tracks_cache, dict) and pid in tracks_cache:
            self._populate_tracks(index, tracks_cache[pid])
            return

        # Display immediate loading state and fetch in background
        tlist.add_option(Option(Text("  ✦ Reading tracklist...", style="#FFD166 italic"), id="loading_tr", disabled=True))
        try:
            t_header = self.query_one("#track-header", Static)
            t_header.update("[#FFD166]  TRACKS  (loading...)[/]")
        except Exception:
            pass

        self._load_tracks_worker(index, pid)

    @work(thread=True, exclusive=True, group="track_fetch")
    def _load_tracks_worker(self, index: int, playlist_id: str) -> None:
        tracks = self.client.get_playlist_tracks(playlist_id)
        self.app.call_from_thread(self._populate_tracks, index, tracks)

    def _populate_tracks(self, index: int, tracks: List[Dict[str, Any]]) -> None:
        plist = self.query_one("#playlist-list", OptionList)
        if plist.highlighted != index:
            # User navigated away to another playlist before fetch finished
            return

        self.tracks = tracks
        tlist = self.query_one("#track-list", OptionList)
        tlist.clear_options()

        if not tracks:
            msg = "  [Rate limited / Cooldown in effect]" if self.client.is_rate_limited() else "  No tracks in this playlist"
            tlist.add_option(Option(Text(msg, style="#6C7086 italic"), disabled=True))
        else:
            for idx, t in enumerate(self.tracks):
                raw_title = t.get("name", "Unknown Track") or "Unknown Track"
                raw_artist = t.get("artist", "Unknown Artist") or "Unknown Artist"
                dur = t.get("duration_str", "00:00")

                clean_title = f"{raw_title[:30]}..." if len(raw_title) > 33 else raw_title
                clean_artist = f"{raw_artist[:20]}..." if len(raw_artist) > 23 else raw_artist

                label = f" {idx+1:>2}.  {clean_title:<33}  {clean_artist:<23}  {dur:>5}"
                tlist.add_option(Option(Text(label, no_wrap=True), id=str(idx)))

        self._update_column_headers()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """When playlist selection moves, preview its tracks."""
        if event.option_list.id == "playlist-list" and event.option_index is not None:
            if 0 <= event.option_index < len(self.playlists):
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
