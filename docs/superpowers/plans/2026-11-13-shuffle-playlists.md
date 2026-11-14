# YouTube Music Shuffle Playlists Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to shuffle-play across their entire Liked Songs library or any playlist directly from the Curtain Drawer using YouTube Music's server-side shuffle endpoint.

**Architecture:** Add `get_shuffled_playlist_tracks` to `YTMusicClient` using `self._ytm.get_watch_playlist(shuffle=True)`. In `CurtainDrawer`, bind `S` key when highlighting a category or playlist to trigger an `on_shuffle_play` callback. In `BardApp`, handle shuffle play asynchronously in a background worker, populating `self.queue` with the shuffled tracks and immediately starting playback on track 0.

**Tech Stack:** Python 3.10+, Textual TUI, ytmusicapi, pytest, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-11-13-shuffle-playlists-design.md`

## Global Constraints

- **Python Version**: >= 3.10.
- **Auto-Push Rule**: All code changes must be committed and pushed to GitHub (`git push origin main`).
- **No Main-Thread Blocking**: All network requests to `get_watch_playlist` and stream extraction must execute on worker threads.
- **Search Key Protection**: Pressing `s` while the inline search input (`#search-input`) has focus must type the character `s` and never trigger shuffle play.
- **Aesthetic Consistency**: Status notifications and hints must adhere to Arcane theme colors (`#FF7A00`, `#FFD166`, `#6C7086`).

## Review Focus

1. **Search Input Interference**: User types the letter `s` while searching for an artist or song. The search field must receive the character without triggering shuffle playback.
2. **Liked Songs Playlist Mapping**: User selects "❤️ Liked Songs" (`id="liked"`). The client must translate `"liked"` to `"LM"` for the YouTube Music API.
3. **Empty / Failed Watch Endpoint**: YouTube Music returns an empty watch list or API raises an exception. The client must degrade gracefully to client-side shuffle of standard playlist tracks rather than raising an unhandled exception.
4. **Queue & Playback Synchronization**: When shuffle succeeds, `self.queue` in `BardApp` must be fully replaced with the shuffled tracks, `self.current_index` set to 0, and track 0 begins playing.
5. **Drawer Focus & Selection**: When in `#category-list` vs `#track-list` (when browsing user playlists), pressing `s` shuffles the specifically highlighted item.

---

### Task 1: Backend `get_shuffled_playlist_tracks` in `YTMusicClient`

**Files:**
- Modify: `src/bard/ytmusic_client.py`
- Test: `tests/test_ytmusic_client.py`

**Interfaces:**
- Produces: `get_shuffled_playlist_tracks(self, playlist_id: str, limit: int = 50) -> List[Track]`

- [ ] **Step 1: Write the failing tests in `tests/test_ytmusic_client.py`**

```python
def test_get_shuffled_playlist_tracks_success(ytm_client):
    fake_watch_resp = {
        "tracks": [
            {
                "videoId": "vid_shuf_1",
                "title": "Shuffled Song 1",
                "artists": [{"name": "Artist 1"}],
                "album": {"name": "Album 1"},
                "length": "3:30",
                "thumbnail": [{"url": "http://example.com/art1.jpg"}],
            },
            {
                "videoId": "vid_shuf_2",
                "title": "Shuffled Song 2",
                "artists": [{"name": "Artist 2"}],
                "album": {"name": "Album 2"},
                "length": "4:00",
                "thumbnail": [{"url": "http://example.com/art2.jpg"}],
            },
        ]
    }
    with patch.object(ytm_client._ytm, "get_watch_playlist", return_value=fake_watch_resp) as mock_watch:
        tracks = ytm_client.get_shuffled_playlist_tracks("liked", limit=50)
        assert len(tracks) == 2
        assert tracks[0].id == "vid_shuf_1"
        assert tracks[0].title == "Shuffled Song 1"
        assert tracks[1].id == "vid_shuf_2"
        mock_watch.assert_called_once_with(playlistId="LM", shuffle=True, limit=50)


def test_get_shuffled_playlist_tracks_fallback_on_error(ytm_client):
    fallback_track = Track(
        id="fb_1",
        title="Fallback Track",
        artist="Artist",
        album="Album",
        duration_ms=180000,
        thumbnail_url="",
    )
    with patch.object(ytm_client._ytm, "get_watch_playlist", side_effect=Exception("API Error")):
        with patch.object(ytm_client, "get_playlist_tracks", return_value=[fallback_track]):
            tracks = ytm_client.get_shuffled_playlist_tracks("PL123", limit=50)
            assert len(tracks) == 1
            assert tracks[0].id == "fb_1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\pytest tests/test_ytmusic_client.py -k "test_get_shuffled_playlist_tracks" -v`
Expected: FAIL with `AttributeError: 'YTMusicClient' object has no attribute 'get_shuffled_playlist_tracks'`

- [ ] **Step 3: Implement `get_shuffled_playlist_tracks` in `src/bard/ytmusic_client.py`**

In `src/bard/ytmusic_client.py`:
1. Check `if not playlist_id: return []`
2. Map `pid = "LM" if playlist_id in ("liked", "LM") else playlist_id`
3. In a `try-except` block, call `res = self._ytm.get_watch_playlist(playlistId=pid, shuffle=True, limit=limit)`
4. Parse items from `res.get("tracks", [])`: for each item, extract `videoId`, `title`, artists, album, duration (via `_parse_duration_to_ms` / `length`), and thumbnail. Map each to `Track`.
5. If `tracks` is non-empty, return it.
6. Fallback block: if `tracks` is empty or exception occurred, if `pid == "LM"`, call `self.get_liked_songs(limit=limit)`; else call `self.get_playlist_tracks(pid)`. Randomize the fallback list with `random.shuffle()` and return it.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\pytest tests/test_ytmusic_client.py -k "test_get_shuffled_playlist_tracks" -v`
Expected: PASS

- [ ] **Step 5: Commit and push**

```bash
git add src/bard/ytmusic_client.py tests/test_ytmusic_client.py
git commit -m "feat(ytmusic): add get_shuffled_playlist_tracks using server-side watch endpoint"
git push origin main
```

---

### Task 2: Drawer UI Shortcut `S` and Hint in `CurtainDrawer`

**Files:**
- Modify: `src/bard/ui/curtain_drawer.py`
- Test: `tests/test_ui_drawer.py`

**Interfaces:**
- Consumes: None (UI interaction)
- Produces: `CurtainDrawer.on_shuffle_play: Optional[Callable[[Dict[str, Any]], None]] = None`

- [ ] **Step 1: Write failing tests in `tests/test_ui_drawer.py`**

```python
def test_drawer_shuffle_shortcut_category_trigger():
    drawer = CurtainDrawer()
    shuffled_payload = []
    drawer.on_shuffle_play = lambda payload: shuffled_payload.append(payload)

    # Highlight Liked Songs
    clist = drawer.query_one("#category-list", OptionList)
    liked_idx = next(i for i, c in enumerate(drawer.categories) if c["id"] == "liked")
    clist.highlighted = liked_idx

    event = events.Key(key="s", character="s")
    drawer.on_key(event)

    assert len(shuffled_payload) == 1
    assert shuffled_payload[0]["id"] == "liked"
    assert shuffled_payload[0]["type"] == "category"


def test_drawer_shuffle_shortcut_ignored_in_search():
    drawer = CurtainDrawer()
    shuffled_payload = []
    drawer.on_shuffle_play = lambda payload: shuffled_payload.append(payload)

    drawer.open_search()
    s_input = drawer.query_one("#search-input", Input)
    s_input.focus()

    event = events.Key(key="s", character="s")
    drawer.on_key(event)

    assert len(shuffled_payload) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\pytest tests/test_ui_drawer.py -k "test_drawer_shuffle_shortcut" -v`
Expected: FAIL

- [ ] **Step 3: Implement shuffle keybinding and hint in `src/bard/ui/curtain_drawer.py`**

1. In `CurtainDrawer.__init__`:
   Add `self.on_shuffle_play: Optional[Callable[[Dict[str, Any]], None]] = None`.
2. In `curtain_drawer.py` compose:
   Add or update footer hint / subtitle bar with `[Enter] Play  ✦  [S] Shuffle  ✦  [/] Search  ✦  [Tab/Esc] Close`.
3. In `on_key(self, event: events.Key)`:
   - Ensure `if s_input.has_class("-visible") and s_input.has_focus: return`
   - Add handler for `event.key in ("s", "S")`:
     - If focus is in `#track-list` and inside `library_playlists` navigation (where items are playlist dicts):
       - If highlighted option is a playlist dict (e.g. index > 0 if `_nav_stack` active), extract playlist info `{"id": item["id"], "title": item["title"], "type": "playlist"}`.
       - Invoke `self.on_shuffle_play(payload)`.
       - `event.stop()`
     - Else:
       - Check highlighted category in `#category-list`:
       - If highlighted category is playable (`id in ("liked", "trending", "arcane", "lofi", "synthwave")` or has a query/id):
         - Extract payload `{"id": cat["id"], "title": cat["name"], "type": "category", "query": cat.get("query")}`.
         - Invoke `self.on_shuffle_play(payload)`.
         - `event.stop()`

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\pytest tests/test_ui_drawer.py -k "test_drawer_shuffle_shortcut" -v`
Expected: PASS

- [ ] **Step 5: Commit and push**

```bash
git add src/bard/ui/curtain_drawer.py tests/test_ui_drawer.py
git commit -m "feat(drawer): add S shortcut and hint for playlist shuffle play"
git push origin main
```

---

### Task 3: Application Playback Coordinator & Documentation in `BardApp`

**Files:**
- Modify: `src/bard/ui/app.py`
- Modify: `README.md`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `YTMusicClient.get_shuffled_playlist_tracks`, `CurtainDrawer.on_shuffle_play`
- Produces: `BardApp.handle_shuffle_play(item: Dict[str, Any]) -> None`

- [ ] **Step 1: Write failing tests in `tests/test_app.py`**

```python
@pytest.mark.asyncio
async def test_app_handle_shuffle_play():
    app = BardApp(config=BardConfig(), client=MagicMock())
    shuffled_tracks = [
        Track(id="shuf_1", title="Track 1", artist="Artist", album="Album", duration_ms=180000, thumbnail_url=""),
        Track(id="shuf_2", title="Track 2", artist="Artist", album="Album", duration_ms=200000, thumbnail_url=""),
    ]
    app.client.get_shuffled_playlist_tracks = MagicMock(return_value=shuffled_tracks)
    app.play_track = MagicMock()
    app.notify = MagicMock()

    app.handle_shuffle_play({"id": "liked", "title": "❤️ Liked Songs", "type": "category"})
    # Call synchronous worker execution or directly test logic
    app._shuffle_play_worker("liked", "❤️ Liked Songs")

    assert len(app.queue) == 2
    assert app.current_index == 0
    assert app.queue[0].id == "shuf_1"
    app.play_track.assert_called_once_with(shuffled_tracks[0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\pytest tests/test_app.py -k "test_app_handle_shuffle_play" -v`
Expected: FAIL with `AttributeError: 'BardApp' object has no attribute 'handle_shuffle_play'`

- [ ] **Step 3: Implement `handle_shuffle_play` in `src/bard/ui/app.py` and update `README.md`**

1. In `BardApp.on_mount`:
   Wire `self.drawer_widget.on_shuffle_play = self.handle_shuffle_play`.
2. Implement `handle_shuffle_play(self, item: Dict[str, Any]) -> None`:
   - Hide the drawer (`self.drawer_widget.hide()`).
   - Extract `playlist_id = item["id"]` and `title = item.get("title", "Playlist")`.
   - Show notification `self.notify(f"✦ Shuffling {title}...", title="Bard Shuffle", severity="information", timeout=3)`.
   - Dispatch `self._shuffle_play_worker(playlist_id, title)`.
3. Implement `@work(thread=True, exclusive=True, group="shuffle_fetch") def _shuffle_play_worker(self, playlist_id: str, title: str) -> None`:
   - Call `tracks = self.client.get_shuffled_playlist_tracks(playlist_id)`.
   - If not tracks:
     - Notify error/empty `self.notify(f"No tracks found to shuffle in {title}.", severity="warning")`.
     - Return.
   - Dispatch to main thread / update `self.queue = list(tracks)`, `self.current_index = 0`, update `self.drawer_widget.tracks = list(tracks)`.
   - Call `self.play_track(tracks[0])`.
   - Notify `self.notify(f"Playing {title} on shuffle ({len(tracks)} tracks queued)", title="Bard Shuffle", timeout=4)`.
4. Update `README.md` controls table:
   Add row under `Inside the Playlists Drawer`:
   `S` | **Shuffle Play** highlighted playlist or Liked Songs.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\pytest tests/test_app.py -k "test_app_handle_shuffle_play" -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `.\.venv\Scripts\pytest`
Expected: All tests PASS.

- [ ] **Step 6: Commit and push**

```bash
git add src/bard/ui/app.py tests/test_app.py README.md
git commit -m "feat(app): implement shuffle play coordinator, queue replacement, and docs"
git push origin main
```
