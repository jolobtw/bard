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
    {"id": "search", "name": "🔍 Search Music...", "query": ""},
    {"id": "connect_account", "name": "✦ Connect Account", "query": None},
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
        on_connect_account: Optional[Callable[[], None]] = None,
        on_disconnect_account: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.client: Any = client if client is not None else spotify_client
        self.on_play: Optional[Callable[[Track], None]] = on_play
        self.on_connect_account: Optional[Callable[[], None]] = on_connect_account
        self.on_disconnect_account: Optional[Callable[[], None]] = on_disconnect_account

        self._nav_stack: List[Dict[str, Any]] = []
        self._cache: Dict[str, Any] = {}
        self._current_cat_idx: int = 0
        self._active_query: Optional[str] = None
        self.tracks: List[Track] = []
        self._current_items: List[Any] = []
        self.categories: List[Dict[str, Any]] = self._build_categories(self._is_authenticated())

    def _is_authenticated(self) -> bool:
        """Check whether underlying client is authenticated."""
        if not self.client:
            return False
        fn = getattr(self.client, "is_authenticated", None)
        if callable(fn):
            try:
                res = fn()
                if isinstance(res, bool):
                    return res
                return False
            except Exception:
                return False
        if isinstance(fn, bool):
            return fn
        return False

    def _build_categories(self, is_auth: bool) -> List[Dict[str, Any]]:
        """Construct categories list based on authentication state."""
        cats: List[Dict[str, Any]] = []
        if is_auth:
            cats.extend([
                {"id": "liked", "name": "❤️ Liked Songs", "query": None},
                {"id": "library_playlists", "name": "📂 Your Playlists", "query": None},
                {"id": "history", "name": "🕒 History", "query": None},
            ])

        # Curated feeds (always present)
        cats.extend([
            {"id": "trending", "name": "🔥 Trending Hits", "query": None},
            {"id": "arcane", "name": "⚡ Arcane & Cyberpunk", "query": "Arcane League of Legends soundtrack"},
            {"id": "lofi", "name": "☕ Lo-Fi Beats", "query": "lofi hip hop chill beats"},
            {"id": "synthwave", "name": "🌌 Synthwave Chill", "query": "synthwave retro chill"},
        ])

        # Actions
        cats.append({"id": "search", "name": "🔍 Search Music...", "query": ""})
        if is_auth:
            cats.append({"id": "disconnect_account", "name": "✦ Disconnect Account", "query": None})
        else:
            cats.append({"id": "connect_account", "name": "✦ Connect Account", "query": None})

        return cats

    def refresh_categories(self) -> None:
        """Re-evaluate authentication state and rebuild the category list."""
        is_auth = self._is_authenticated()
        self.categories = self._build_categories(is_auth)
        self._cache.clear()
        self._nav_stack.clear()
        self._current_cat_idx = 0

        try:
            clist = self.query_one("#category-list", OptionList)
            clist.clear_options()
            for idx, cat in enumerate(self.categories):
                name = cat["name"]
                clist.add_option(Option(Text(f" {name:<28}", no_wrap=True), id=str(idx)))
            clist.highlighted = 0
            self._update_column_headers()
            self.load_tracks_for_category(0)
        except Exception:
            pass

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
            "[#FFD166]← / →[/] Switch Column   [#FFD166]↑ / ↓[/] Navigate   [#FFD166]/[/] Search   [#FFD166]Enter[/] Play   [#FFD166]Backspace[/] Back   [#FFD166]Esc[/] Close",
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
            t_count = len(self.tracks) if self.tracks else len(self._current_items)

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
        """Handle keyboard shortcuts for search, drill-down back, and column navigation."""
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
                        if self._current_items or self.tracks:
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
        elif event.key == "backspace":
            if self._nav_stack:
                self._navigate_back()
                event.stop()
        elif event.key in ("right", "l"):
            tlist = self.query_one("#track-list", OptionList)
            if self._current_items or self.tracks:
                tlist.focus()
                if tlist.highlighted is None:
                    tlist.highlighted = 0
                self._update_column_headers()
                event.stop()
        elif event.key in ("left", "h"):
            try:
                tlist = self.query_one("#track-list", OptionList)
                if tlist.has_focus and self._nav_stack:
                    self._navigate_back()
                    event.stop()
                    return
            except Exception:
                pass
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

        self._nav_stack.clear()
        self._current_cat_idx = index
        cat = self.categories[index]
        cat_id = cat["id"]
        if cat_id != "search":
            self._active_query = None

        if cat_id == "connect_account":
            self.tracks = []
            self._current_items = []
            try:
                tlist = self.query_one("#track-list", OptionList)
                tlist.clear_options()
                tlist.add_option(
                    Option(Text("  ✦ Press Enter to connect Google / YouTube Music account", style="#FFD166 italic"), disabled=True)
                )
                self._update_column_headers()
            except Exception:
                pass
            return

        if cat_id == "disconnect_account":
            self.tracks = []
            self._current_items = []
            try:
                tlist = self.query_one("#track-list", OptionList)
                tlist.clear_options()
                tlist.add_option(
                    Option(Text("  ✦ Press Enter to disconnect your account", style="#FFD166 italic"), disabled=True)
                )
                self._update_column_headers()
            except Exception:
                pass
            return

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
            loading_msg = f"  ✦ Loading {cat['name']}..."
            tlist.add_option(Option(Text(loading_msg, style="#FFD166 italic"), id="loading_tr", disabled=True))
            t_header = self.query_one("#track-header", Static)
            t_header.update("[#FFD166]  TRACKS  (loading...)[/]")
        except Exception:
            pass

        self._load_tracks_worker(cat_id, is_trending=(cat_id == "trending"), query=cat.get("query"))

    def load_tracks_for_search(self, query: str) -> None:
        """Search tracks with user query and populate tracklist."""
        for idx, cat in enumerate(self.categories):
            if cat["id"] == "search":
                self._current_cat_idx = idx
                try:
                    clist = self.query_one("#category-list", OptionList)
                    clist.highlighted = idx
                except Exception:
                    pass
                break
        self._nav_stack.clear()
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
        items: List[Any] = []
        try:
            if cache_key == "liked":
                if hasattr(self.client, "get_liked_songs"):
                    items = self.client.get_liked_songs()
            elif cache_key == "library_playlists":
                if hasattr(self.client, "get_library_playlists"):
                    items = self.client.get_library_playlists()
            elif cache_key == "history":
                if hasattr(self.client, "get_history"):
                    items = self.client.get_history()
            elif is_trending:
                if hasattr(self.client, "get_trending"):
                    items = self.client.get_trending()
            elif query is not None:
                # Search mode: try search_all first for albums + songs, fallback to search()
                found = False
                if hasattr(self.client, "search_all"):
                    try:
                        res = self.client.search_all(query)
                        if isinstance(res, dict) and any(res.values()):
                            songs = res.get("songs") or []
                            albums = res.get("albums") or []
                            items = list(songs) + list(albums)
                            found = True
                    except Exception as err:
                        logger.debug("search_all failed: %s", err)

                if not found and hasattr(self.client, "search"):
                    items = self.client.search(query)
        except Exception as exc:
            logger.error("Failed to fetch tracks for key=%s: %s", cache_key, exc)
            items = []

        if items:
            self._cache[cache_key] = items
            if cache_key.startswith("search:"):
                self._cache["search"] = items

        if self.is_mounted and hasattr(self, "app") and self.app is not None:
            self.app.call_from_thread(self._populate_tracks, cache_key, items)
        else:
            self._populate_tracks(cache_key, items)

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

    def _render_track_row(self, idx: int, t: Track) -> Option:
        """Render a track row with strictly preserved two-tier formatting."""
        raw_title = (t.title or "Unknown Track").strip()
        raw_artist = (t.artist or "Unknown Artist").strip()
        dur = _format_duration(t.duration_seconds)

        max_title_len = 70
        clean_title = f"{raw_title[:max_title_len - 3]}..." if len(raw_title) > max_title_len else raw_title

        max_artist_len = 50
        clean_artist = f"{raw_artist[:max_artist_len - 3]}..." if len(raw_artist) > max_artist_len else raw_artist

        opt_text = Text(no_wrap=True)
        opt_text.append(f" {idx+1:>2}.  ", style="bold #FF7A00")
        opt_text.append(f"{clean_title}\n", style="bold #FFFFFF")
        opt_text.append(f"      {clean_artist}", style="#A6ADC8")
        opt_text.append("  •  ", style="#6C7086")
        opt_text.append(f"{dur}", style="#FFD166")

        return Option(opt_text, id=f"tr_{idx}")

    def _render_playlist_row(self, idx: int, p: Dict[str, Any]) -> Option:
        """Render a library playlist row."""
        title = (p.get("title") or "Untitled Playlist").strip()
        count = p.get("count") or ""
        count_str = f"{count} tracks" if count and not str(count).endswith("tracks") else (str(count) or "Playlist")

        max_title_len = 70
        clean_title = f"{title[:max_title_len - 3]}..." if len(title) > max_title_len else title

        opt_text = Text(no_wrap=True)
        opt_text.append(f" {idx+1:>2}.  📂 ", style="bold #FF7A00")
        opt_text.append(f"{clean_title}\n", style="bold #FFFFFF")
        opt_text.append(f"      {count_str}", style="#A6ADC8")

        return Option(opt_text, id=f"pl_{idx}")

    def _render_album_row(self, idx: int, a: Dict[str, Any]) -> Option:
        """Render an album result row."""
        title = (a.get("title") or "Unknown Album").strip()
        artist = (a.get("artist") or "Unknown Artist").strip()
        year = str(a.get("year") or "").strip()

        max_title_len = 70
        clean_title = f"{title[:max_title_len - 3]}..." if len(title) > max_title_len else title

        sub = f"{artist}  •  {year}" if year else artist

        opt_text = Text(no_wrap=True)
        opt_text.append(f" {idx+1:>2}.  💿 [Album] ", style="bold #FF7A00")
        opt_text.append(f"{clean_title}\n", style="bold #FFFFFF")
        opt_text.append(f"      {sub}", style="#A6ADC8")

        return Option(opt_text, id=f"alb_{idx}")

    def _populate_tracks(self, expected_key: str, items: List[Any]) -> None:
        """Populate results into the right OptionList."""
        if not self._matches_active_selection(expected_key):
            return

        self._current_items = list(items)
        self.tracks = [item for item in items if isinstance(item, Track)]

        try:
            tlist = self.query_one("#track-list", OptionList)
            tlist.clear_options()

            if not self._current_items:
                tlist.add_option(Option(Text("  ✦ No tracks found", style="#6C7086 italic"), disabled=True))
            else:
                for idx, item in enumerate(self._current_items):
                    if isinstance(item, Track):
                        tlist.add_option(self._render_track_row(idx, item))
                    elif isinstance(item, dict):
                        if item.get("browse_id") or item.get("browseId"):
                            tlist.add_option(self._render_album_row(idx, item))
                        else:
                            tlist.add_option(self._render_playlist_row(idx, item))

            self._update_column_headers()
            if getattr(self, "_play_on_load", False):
                self._play_on_load = False
                if self.tracks and self.on_play:
                    self.on_play(self.tracks[0])
                    self.hide()
        except Exception:
            pass

    def _drill_down_playlist(self, playlist: Dict[str, Any]) -> None:
        """Drill down into a library playlist."""
        playlist_id = playlist.get("id") or ""
        title = playlist.get("title") or "Playlist"
        self._push_nav_state("Playlists")
        self.close_search()

        try:
            tlist = self.query_one("#track-list", OptionList)
            tlist.clear_options()
            back_text = Text(no_wrap=True)
            back_text.append("  [ ◄ Back to Playlists ]\n", style="bold #FFD166")
            back_text.append("      Return to previous playlists list", style="#6C7086 italic")
            tlist.add_option(Option(back_text, id="nav_back"))
            tlist.add_option(Option(Text(f"  ✦ Loading {title}...", style="#FFD166 italic"), disabled=True))
            tlist.focus()

            t_header = self.query_one("#track-header", Static)
            t_header.update(f"[#FFD166]  {title}  (loading...)[/]")
            self._update_column_headers()
        except Exception:
            pass

        self._load_container_worker("playlist", playlist_id, title, "Playlists")

    def _drill_down_album(self, album: Dict[str, Any]) -> None:
        """Drill down into an album from search results."""
        browse_id = album.get("browse_id") or album.get("browseId") or album.get("id") or ""
        title = album.get("title") or "Album"
        self._push_nav_state("Results")
        self.close_search()

        try:
            tlist = self.query_one("#track-list", OptionList)
            tlist.clear_options()
            back_text = Text(no_wrap=True)
            back_text.append("  [ ◄ Back to Results ]\n", style="bold #FFD166")
            back_text.append("      Return to search results", style="#6C7086 italic")
            tlist.add_option(Option(back_text, id="nav_back"))
            tlist.add_option(Option(Text(f"  ✦ Loading {title}...", style="#FFD166 italic"), disabled=True))
            tlist.focus()

            t_header = self.query_one("#track-header", Static)
            t_header.update(f"[#FFD166]  {title}  (loading...)[/]")
            self._update_column_headers()
        except Exception:
            pass

        self._load_container_worker("album", browse_id, title, "Results")

    def _push_nav_state(self, parent_name: str) -> None:
        """Save current view state onto navigation stack."""
        try:
            tlist = self.query_one("#track-list", OptionList)
            highlighted = tlist.highlighted
        except Exception:
            highlighted = 0

        self._nav_stack.append({
            "items": list(self._current_items),
            "tracks": list(self.tracks),
            "highlighted": highlighted,
            "parent_name": parent_name,
            "active_query": self._active_query,
            "cat_idx": self._current_cat_idx,
        })

    def _navigate_back(self) -> None:
        """Return to parent view from drilled-down state."""
        if not self._nav_stack:
            return

        prev_state = self._nav_stack.pop()
        self._active_query = prev_state.get("active_query")
        self._current_items = prev_state.get("items", [])
        self.tracks = prev_state.get("tracks", [])

        try:
            tlist = self.query_one("#track-list", OptionList)
            tlist.clear_options()

            if self._nav_stack:
                # Still in a nested drill-down
                parent = self._nav_stack[-1].get("parent_name", "Parent")
                back_text = Text(no_wrap=True)
                back_text.append(f"  [ ◄ Back to {parent} ]\n", style="bold #FFD166")
                back_text.append("      Return to previous list", style="#6C7086 italic")
                tlist.add_option(Option(back_text, id="nav_back"))

            for idx, item in enumerate(self._current_items):
                if isinstance(item, Track):
                    tlist.add_option(self._render_track_row(idx, item))
                elif isinstance(item, dict):
                    if item.get("browse_id") or item.get("browseId"):
                        tlist.add_option(self._render_album_row(idx, item))
                    else:
                        tlist.add_option(self._render_playlist_row(idx, item))

            high = prev_state.get("highlighted", 0)
            if high is not None and 0 <= high < tlist.option_count:
                tlist.highlighted = high
            self._update_column_headers()
        except Exception:
            pass

    @work(thread=True, exclusive=True, group="track_fetch")
    def _load_container_worker(self, container_type: str, container_id: str, title: str, parent_name: str) -> None:
        """Background worker to fetch tracks for a playlist or album."""
        cache_key = f"{container_type}:{container_id}"
        tracks: List[Track] = []
        if cache_key in self._cache:
            tracks = self._cache[cache_key]
        else:
            try:
                if container_type == "playlist" and hasattr(self.client, "get_playlist_tracks"):
                    tracks = self.client.get_playlist_tracks(container_id)
                elif container_type == "album" and hasattr(self.client, "get_album_tracks"):
                    tracks = self.client.get_album_tracks(container_id)
            except Exception as exc:
                logger.error("Failed to load %s tracks for %s: %s", container_type, container_id, exc)
                tracks = []

            if tracks:
                self._cache[cache_key] = tracks

        if self.is_mounted and hasattr(self, "app") and self.app is not None:
            self.app.call_from_thread(self._populate_container_tracks, parent_name, title, tracks)
        else:
            self._populate_container_tracks(parent_name, title, tracks)

    def _populate_container_tracks(self, parent_name: str, title: str, tracks: List[Track]) -> None:
        """Render container tracks with Back button at index 0."""
        if not self._nav_stack:
            return

        self.tracks = list(tracks)
        self._current_items = list(tracks)

        try:
            tlist = self.query_one("#track-list", OptionList)
            tlist.clear_options()

            back_text = Text(no_wrap=True)
            back_text.append(f"  [ ◄ Back to {parent_name} ]\n", style="bold #FFD166")
            back_text.append("      Return to previous list", style="#6C7086 italic")
            tlist.add_option(Option(back_text, id="nav_back"))

            if not tracks:
                tlist.add_option(Option(Text("  ✦ No tracks found in this collection", style="#6C7086 italic"), disabled=True))
            else:
                for idx, t in enumerate(tracks):
                    tlist.add_option(self._render_track_row(idx, t))

            t_header = self.query_one("#track-header", Static)
            t_header.update(f"[bold #FFD166]▸ {title}[/]  [#6C7086]({len(tracks)})[/]")
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
            if 0 <= event.option_index < len(self.categories):
                cat = self.categories[event.option_index]
                cat_id = cat["id"]
                if cat_id == "search":
                    self.open_search()
                elif cat_id == "connect_account":
                    if self.on_connect_account:
                        self.on_connect_account()
                    self.hide()
                elif cat_id == "disconnect_account":
                    if self.on_disconnect_account:
                        self.on_disconnect_account()
                    self.refresh_categories()
                elif cat_id == "library_playlists":
                    tlist = self.query_one("#track-list", OptionList)
                    if self._current_items or self.tracks:
                        tlist.focus()
                        if tlist.highlighted is None:
                            tlist.highlighted = 0
                    self._update_column_headers()
                else:
                    if self.tracks and self.on_play:
                        self.on_play(self.tracks[0])
                        self.hide()
                    else:
                        self._play_on_load = True
                        self.load_tracks_for_category(event.option_index)
        elif event.option_list.id == "track-list" and event.option_index is not None:
            if self._nav_stack:
                if event.option_index == 0:
                    self._navigate_back()
                    return
                track_idx = event.option_index - 1
                if 0 <= track_idx < len(self.tracks):
                    selected = self.tracks[track_idx]
                    if self.on_play:
                        self.on_play(selected)
                    self.hide()
                return

            if 0 <= event.option_index < len(self._current_items):
                item = self._current_items[event.option_index]
                if isinstance(item, Track):
                    if self.on_play:
                        self.on_play(item)
                    self.hide()
                elif isinstance(item, dict):
                    if item.get("browse_id") or item.get("browseId"):
                        self._drill_down_album(item)
                    elif "id" in item:
                        self._drill_down_playlist(item)
