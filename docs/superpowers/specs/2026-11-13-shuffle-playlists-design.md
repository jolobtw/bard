# YouTube Music Shuffle Playlists & Library Design

**Date:** 2026-11-13  
**Status:** Draft  
**Target:** Bard Terminal Music Player  

---

## 1. Intent & The "Why"

In Bard, users with extensive music collections (such as "Liked Songs" with 500+ tracks or large user playlists) currently experience a 50-track preview cutoff in the UI. When playing a playlist or category, Bard plays sequentially from the loaded preview.

Users want the ability to **shuffle-play across their entire library or playlist**, drawing from the full catalog (e.g. 500+ liked songs) rather than being bounded by the top 50 items. Users also want a direct, dedicated action from the Curtain Drawer to trigger shuffle playback on any highlighted playlist or library category.

---

## 2. Goals, Non-Goals, and Anti-Goals

### Goals
- **Full-Catalog Shuffle Playback**: Enable shuffle play that pulls from the entire playlist/library via YouTube Music's server-side shuffle endpoint (`get_watch_playlist(playlistId=..., shuffle=True)`), sampling across all 500+ tracks.
- **Dedicated Drawer Action**: Provide an intuitive keyboard action in the Curtain Drawer (e.g., `S` key when highlighting a category or playlist) to immediately start shuffled playback.
- **Visual Feedback & Controls Hint**: Add an explicit shortcut hint in the drawer (e.g. `[Enter] Play  ✦  [S] Shuffle Play`) and display an Arcane toast notification when shuffle starts (e.g. `✦ Shuffling Liked Songs (50 tracks queued)...`).
- **Seamless Queue Integration**: Replace Bard's active queue (`self.queue`) with the returned shuffled tracks and immediately start playing track 0.

### Non-Goals
- Full paginated continuation rendering in the drawer tracklist preview for this iteration (the user clarified that fetching 500+ items into the scrollable UI is unnecessary as long as playback draws from the entire catalog).
- Persistent global shuffle toggle (user chose a dedicated per-playlist trigger from the drawer).

### Anti-Goals
- **No UI Thread Freezes**: API calls to `get_watch_playlist` and stream extraction must execute asynchronously in background Textual workers.
- **No Key Hijacking in Search**: Pressing `s` while the inline search input (`#search-input`) has focus must enter the character `s` into the query string, never triggering playback.
- **No Broken Fallbacks**: If `get_watch_playlist` fails or an anonymous/unauthenticated user triggers shuffle on private collections, degrade gracefully with an actionable notification.

---

## 3. Constraints

- **Platform & Environment**: Windows (WASAPI / mpv), macOS (CoreAudio / mpv), Linux; Python >= 3.10.
- **Authentication**: Shuffling "Liked Songs" (`playlistId="LM"`) or private user playlists requires an authenticated session (`oauth.json`). Public and curated playlists work anonymously.
- **Version Control**: Auto-Push Rule — commit and push changes to GitHub (`git push origin main`).
- **Aesthetic**: Strictly preserve Arcane styling tokens (ember orange `#FF7A00`, gold `#FFD166`, slate `#6C7086`).

---

## 4. Approaches Considered

### Approach 1: YouTube Music Server-Side Shuffle via `get_watch_playlist` (Selected)
- **Mechanism**: Calls `self._ytm.get_watch_playlist(playlistId=pid, shuffle=True)` using YouTube Music's native shuffle parameter (`params="wAEB8gECKAE%3D"`).
- **Pros**: 
  - Instant response: single network call returns 25–50 randomized tracks sampled across the entire 500+ library.
  - Zero pagination delay: avoids 5–10 sequential HTTP requests.
  - Handled directly by YouTube's recommendation & shuffle engine.
- **Cons**: Populates the active playback queue rather than rendering all 500 rows in the drawer preview.
- **User Decision**: Selected. Matches user's explicit preference for instant playback over full tracklist rendering.

### Approach 2: Full Client-Side Continuation Resolution & In-Memory Shuffle
- **Mechanism**: Set `limit=None` on `get_liked_songs` and `get_playlist_tracks`, sequentially following pagination continuation tokens until all 500+ tracks are downloaded, then shuffling `self.queue` via Python `random.shuffle()`.
- **Trade-off**: Requires 5–10 sequential network requests (2–5 seconds latency) every time a playlist is opened, consuming unnecessary network quota and delaying playback start.

---

## 5. Architectural Specification & Implementation Details

### A. Client Layer (`src/bard/ytmusic_client.py`)
Add `get_shuffled_playlist_tracks(self, playlist_id: str, limit: int = 50) -> List[Track]`:
1. Resolve playlist ID (`"liked"` maps to `"LM"` for YouTube Music Liked Songs).
2. Call `self._ytm.get_watch_playlist(playlistId=playlist_id, shuffle=True, limit=limit)`.
3. Normalize the returned track dictionaries into Bard's `Track` dataclass (re-using `_normalize_track` / `_parse_tile_track`).
4. Fallback: If `get_watch_playlist` encounters an error, fallback to client-side shuffle of `get_playlist_tracks(playlist_id)` or `get_liked_songs()`.

### B. Drawer UI (`src/bard/ui/curtain_drawer.py`)
1. **Shortcut Support**:
   - In `on_key`, if `#search-input` does not have focus:
     - Check `if event.key in ("s", "S"):`
     - Determine highlighted target (either a category in `#category-list` such as Liked Songs / Trending, or a playlist in `#track-list` under "Your Playlists").
     - If valid target, invoke `self.on_shuffle_play(target_info)` or post custom event.
2. **Help Bar / Footer**:
   - Display shortcut hint in the drawer title/footer: `[Enter] Play  ✦  [S] Shuffle  ✦  [/] Search  ✦  [Tab/Esc] Close`.

### C. Application Coordinator (`src/bard/ui/app.py`)
1. Provide `handle_shuffle_play(self, item: Dict[str, Any])`:
   - Launch `@work(thread=True, exclusive=True, group="shuffle_fetch")` worker:
     - Show toast notification: `✦ Shuffling <Title>...`
     - Call `client.get_shuffled_playlist_tracks(playlist_id)`.
     - Dispatch to main thread: populate `self.queue` with shuffled tracks, set `self.current_index = 0`, update drawer tracks, and start playback via `self.play_track(self.queue[0])`.
     - Show success notification with track count.

---

## 6. What's Left to the Builder

- Exact key handling and focus management in `CurtainDrawer` ensuring clean interaction with `OptionList`.
- Unit tests for `get_shuffled_playlist_tracks` in `tests/test_ytmusic_client.py` and UI event handling in `tests/test_ui.py`.
- Documentation update in `README.md` under Controls & Keybindings.
