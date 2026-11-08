"""Left-Side Curtain Drawer for browsing and selecting YouTube Music categories, search, and tracks."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional
from rich.text import Text
from textual import events, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from bard.models import Track
from bard.ytmusic_client import YTMusicClient

logger = logging.getLogger(__name__)


def _format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds as mm:ss or hh:mm:ss."""
    if not seconds or seconds < 0:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


DEFAULT_CATEGORIES: List[Dict[str, Any]] = [
    {"id": "trending", "name": "🔥 Trending Hits", "query": None},
    {"id": "arcane", "name": "⚡ Arcane & Cyberpunk", "query": "Arcane League of Legends soundtrack"},
    {"id": "lofi", "name": "☕ Lo-Fi Beats", "query": "lofi hip hop chill beats"},
    {"id": "synthwave", "name": "🌌 Synthwave Chill", "query": "synthwave retro chill"},
    {"id": "search", "name": "🔍 Search Tracks...", "query": ""},
]


class CurtainDrawer(Widget):
    """Dual-tier slide-out drawer on the left side for YouTube Music categories and tracklist."""

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

    #category-column, #playlist-column {
        width: 42%;
        min-width: 36;
        max-width: 50;
        height: 100%;
        border-right: solid #2E3244;
    }

    #category-header, #playlist-header {
        height: 2;
        width: 100%;
        border-bottom: solid #2E3244;
        padding: 0 1;
        content-align: left middle;
    }

    #search-input {
        dock: bottom;
        height: 3;
        width: 100%;
        background: #181A24;
        border: solid #FF7A00;
        color: #FFD166;
        display: none;
    }

    #search-input.-visible {
        display: block;
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

    def __init__(
        self,
        client: Optional[Any] = None,
        on_play: Optional[Callable[[Track], None]] = None,
        spotify_client: Optional[Any] = None,
    ):
        super().__init__()
        self.client: Any = client if client is not None else spotify_client
        self.on_play: Optional[Callable[[Track], None]] = on_play
        self.categories: List[Dict[str, Any]] = list(DEFAULT_CATEGORIES)
        self.tracks: List[Track] = []
        self._cache: Dict[str, List[Track]] = {}
        self._current_cat_idx: int = 0
        self._active_query: Optional[str] = None

    @property
    def playlists(self) -> List[Dict[str, Any]]:
        """Backwards compatibility alias for categories."""
        return self.categories

    def query_one(self, *args: Any, **kwargs: Any) -> Any:
        """Alias legacy playlist selectors to new category selectors."""
        if args and args[0] == "#playlist-list":
            args = ("#category-list",) + args[1:]
        elif args and args[0] == "#playlist-header":
            args = ("#category-header",) + args[1:]
        elif args and args[0] == "#playlist-column":
            args = ("#category-column",) + args[1:]
        return super().query_one(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield Static("✦  ❖  YOUTUBE MUSIC EXPLORER  ❖  ✦", id="drawer-title-bar")
        with Horizontal(id="drawer-columns"):
            with Vertical(id="category-column"):
                yield Static(f"▸ EXPLORE ({len(self.categories)})", id="category-header")
                yield OptionList(id="category-list")
                yield Input(placeholder="🔍 Type song/artist & press Enter...", id="search-input")
            with Vertical(id="track-column"):
                yield Static("  TRACKS (0)", id="track-header")
                yield OptionList(id="track-list")
        yield Static(
            "[#FFD166]← / →[/] Switch Column   [#FFD166]↑ / ↓[/] Navigate   [#FFD166]/[/] Search   [#FFD166]Enter[/] Play   [#FFD166]Esc[/] Close",
            id="drawer-footer",
        )

    def toggle(self) -> None:
        """Toggle drawer visibility."""
        if self.has_class("-visible"):
            self.hide()
        else:
            self.add_class("-visible")
            try:
                self._populate_category_list()
                clist = self.query_one("#category-list", OptionList)
                clist.focus()
                if clist.highlighted is None:
                    clist.highlighted = 0
                self._update_column_headers()
                self.load_tracks_for_category(clist.highlighted)
            except Exception:
                pass

    def hide(self) -> None:
        """Close drawer."""
        self.remove_class("-visible")
        self.close_search()

    def is_open(self) -> bool:
        return self.has_class("-visible")

    def open_search(self) -> None:
        """Reveal and focus inline search input."""
        try:
            s_input = self.query_one("#search-input", Input)
            s_input.add_class("-visible")
            s_input.focus()
            self._update_column_headers()
        except Exception:
            pass

    def close_search(self) -> None:
        """Hide inline search input and refocus category list."""
        try:
            s_input = self.query_one("#search-input", Input)
            s_input.remove_class("-visible")
            clist = self.query_one("#category-list", OptionList)
            clist.focus()
            self._update_column_headers()
        except Exception:
            pass

    def _update_column_headers(self) -> None:
        """Highlight active column header based on focus."""
        try:
            c_header = self.query_one("#category-header", Static)
            t_header = self.query_one("#track-header", Static)
            clist = self.query_one("#category-list", OptionList)
            tlist = self.query_one("#track-list", OptionList)
            s_input = self.query_one("#search-input", Input)

            c_count = len(self.categories)
            t_count = len(self.tracks)

            if clist.has_focus or s_input.has_focus:
                c_header.update(f"[bold #FFD166]▸ EXPLORE[/]  [#6C7086]({c_count})[/]")
                t_header.update(f"[#6C7086]  TRACKS  ({t_count})[/]")
            elif tlist.has_focus:
                c_header.update(f"[#6C7086]  EXPLORE  ({c_count})[/]")
                t_header.update(f"[bold #FFD166]▸ TRACKS[/]  [#6C7086]({t_count})[/]")
            else:
                c_header.update(f"[#FF7A00]EXPLORE[/]  [#6C7086]({c_count})[/]")
                t_header.update(f"[#FF7A00]TRACKS[/]  [#6C7086]({t_count})[/]")
        except Exception:
            pass

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        """Keep column headers in sync when focus shifts."""
        self._update_column_headers()

    def on_key(self, event: events.Key) -> None:
        """Handle keyboard shortcuts for search and column navigation."""
        try:
            s_input = self.query_one("#search-input", Input)
            if s_input.has_class("-visible"):
                if event.key == "escape":
                    self.close_search()
                    event.stop()
                    return
                elif s_input.has_focus:
                    if event.key == "up":
                        clist = self.query_one("#category-list", OptionList)
                        clist.focus()
                        event.stop()
                    elif event.key == "down":
                        tlist = self.query_one("#track-list", OptionList)
                        if self.tracks:
                            tlist.focus()
                            if tlist.highlighted is None:
                                tlist.highlighted = 0
                        event.stop()
                    return
        except Exception:
            pass

        if event.key == "slash":
            self.open_search()
            event.stop()
        elif event.key in ("right", "l"):
            tlist = self.query_one("#track-list", OptionList)
            if self.tracks:
                tlist.focus()
                if tlist.highlighted is None:
                    tlist.highlighted = 0
                self._update_column_headers()
                event.stop()
        elif event.key in ("left", "h"):
            clist = self.query_one("#category-list", OptionList)
            clist.focus()
            self._update_column_headers()
            event.stop()

    def _populate_category_list(self) -> None:
        """Populate predefined categories into the left OptionList."""
        try:
            clist = self.query_one("#category-list", OptionList)
            if clist.option_count > 0:
                return
            for idx, cat in enumerate(self.categories):
                name = cat["name"]
                clist.add_option(Option(Text(f" {name:<28}", no_wrap=True), id=str(idx)))
        except Exception:
            pass

    def select_category(self, index: int) -> None:
        """Select category programmatically by index."""
        if 0 <= index < len(self.categories):
            self._current_cat_idx = index
            try:
                clist = self.query_one("#category-list", OptionList)
                if clist.highlighted != index:
                    clist.highlighted = index
            except Exception:
                pass
            self.load_tracks_for_category(index)

    def load_tracks_for_category(self, index: int) -> None:
        """Fetch and populate tracks for a specific category index."""
        if not (0 <= index < len(self.categories)):
            return

        self._current_cat_idx = index
        cat = self.categories[index]
        cat_id = cat["id"]
        if cat_id != "search":
            self._active_query = None

        if cat_id == "search":
            self.open_search()
            if "search" in self._cache and self._cache["search"]:
                self._populate_tracks("search", self._cache["search"])
            else:
                try:
                    tlist = self.query_one("#track-list", OptionList)
                    tlist.clear_options()
                    tlist.add_option(
                        Option(Text("  ✦ Press Enter or '/' to search YouTube Music", style="#6C7086 italic"), disabled=True)
                    )
                except Exception:
                    pass
            return

        # Check in-memory cache
        if cat_id in self._cache:
            self._populate_tracks(cat_id, self._cache[cat_id])
            return

        # Show loading indicator in tracklist
        try:
            tlist = self.query_one("#track-list", OptionList)
            tlist.clear_options()
            loading_msg = "  ✦ Fetching trending hits..." if cat_id == "trending" else f"  ✦ Searching {cat['name']}..."
            tlist.add_option(Option(Text(loading_msg, style="#FFD166 italic"), id="loading_tr", disabled=True))
            t_header = self.query_one("#track-header", Static)
            t_header.update("[#FFD166]  TRACKS  (loading...)[/]")
        except Exception:
            pass

        self._load_tracks_worker(cat_id, is_trending=(cat_id == "trending"), query=cat["query"])

    def load_tracks_for_search(self, query: str) -> None:
        """Search tracks with user query and populate tracklist."""
        self._active_query = query
        cache_key = f"search:{query}"
        if cache_key in self._cache:
            self._populate_tracks(cache_key, self._cache[cache_key])
            return

        try:
            tlist = self.query_one("#track-list", OptionList)
            tlist.clear_options()
            tlist.add_option(
                Option(Text(f"  ✦ Searching YouTube Music for '{query}'...", style="#FFD166 italic"), id="loading_tr", disabled=True)
            )
            t_header = self.query_one("#track-header", Static)
            t_header.update("[#FFD166]  TRACKS  (searching...)[/]")
        except Exception:
            pass

        self._load_tracks_worker(cache_key, is_trending=False, query=query)

    @work(thread=True, exclusive=True, group="track_fetch")
    def _load_tracks_worker(self, cache_key: str, is_trending: bool, query: Optional[str]) -> None:
        """Background worker for YouTube Music API requests."""
        tracks: List[Track] = []
        try:
            if is_trending:
                if hasattr(self.client, "get_trending"):
                    tracks = self.client.get_trending()
            elif query:
                if hasattr(self.client, "search"):
                    tracks = self.client.search(query)
        except Exception as exc:
            logger.error("Failed to fetch tracks for key=%s: %s", cache_key, exc)
            tracks = []

        if tracks:
            self._cache[cache_key] = tracks
            if cache_key.startswith("search:"):
                self._cache["search"] = tracks

        if self.is_mounted and hasattr(self, "app") and self.app is not None:
            self.app.call_from_thread(self._populate_tracks, cache_key, tracks)
        else:
            self._populate_tracks(cache_key, tracks)

    def _matches_active_selection(self, expected_key: str) -> bool:
        """Verify whether expected_key matches the currently active category or search query."""
        if not (0 <= self._current_cat_idx < len(self.categories)):
            return False
        active_cat_id = self.categories[self._current_cat_idx]["id"]
        if active_cat_id == "search":
            if self._active_query:
                return expected_key == f"search:{self._active_query}" or expected_key == "search"
            return expected_key == "search" or expected_key.startswith("search:")
        return expected_key == active_cat_id

    def _populate_tracks(self, expected_key: str, tracks: List[Track]) -> None:
        """Populate track results into the right OptionList."""
        if not self._matches_active_selection(expected_key):
            return
        self.tracks = tracks
        try:
            tlist = self.query_one("#track-list", OptionList)
            tlist.clear_options()

            if not self.tracks:
                tlist.add_option(Option(Text("  No tracks found", style="#6C7086 italic"), disabled=True))
            else:
                for idx, t in enumerate(self.tracks):
                    raw_title = t.title or "Unknown Track"
                    raw_artist = t.artist or "Unknown Artist"
                    dur = _format_duration(t.duration_seconds)

                    clean_title = f"{raw_title[:30]}..." if len(raw_title) > 33 else raw_title
                    clean_artist = f"{raw_artist[:20]}..." if len(raw_artist) > 23 else raw_artist

                    label = f" {idx+1:>2}.  {clean_title:<33}  {clean_artist:<23}  {dur:>5}"
                    tlist.add_option(Option(Text(label, no_wrap=True), id=str(idx)))

            self._update_column_headers()
        except Exception:
            pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle search query submission from inline input."""
        query = (event.value or "").strip()
        if not query:
            return
        self.load_tracks_for_search(query)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Preview tracks when category selection moves."""
        if event.option_list.id in ("category-list", "playlist-list") and event.option_index is not None:
            if 0 <= event.option_index < len(self.categories):
                self._current_cat_idx = event.option_index
                self.load_tracks_for_category(event.option_index)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle Enter key on category or track."""
        if event.option_list.id in ("category-list", "playlist-list") and event.option_index is not None:
            if 0 <= event.option_index < len(self.categories) and self.categories[event.option_index]["id"] == "search":
                self.open_search()
            else:
                tlist = self.query_one("#track-list", OptionList)
                if self.tracks:
                    tlist.focus()
                    if tlist.highlighted is None:
                        tlist.highlighted = 0
                self._update_column_headers()
        elif event.option_list.id == "track-list" and event.option_index is not None:
            if 0 <= event.option_index < len(self.tracks):
                selected = self.tracks[event.option_index]
                if self.on_play:
                    self.on_play(selected)
                self.hide()
