# YouTube Music Pivot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pivot Bard from Spotify to a fully standalone YouTube Music terminal player that plays music locally without requiring any Spotify app, browser, or login.

**Architecture:** A standalone terminal music player powered by `ytmusicapi` for catalog/search/metadata, `yt-dlp` for stream extraction, and a headless `mpv` process communicating over JSON IPC for zero-latency local audio playback. Textual UI provides the Arcane Zen Stage with ANSI TrueColor album art, flame progress bar, and slide-out playlist/search drawer.

**Tech Stack:** Python 3.10+, Textual, Rich, Pillow, ytmusicapi, yt-dlp, mpv (headless background audio backend with IPC).

**Spec:** Pivot Bard from Spotify to YouTube Music: standalone terminal playback, no browser/desktop app required, Arcane aesthetic retained, instant keyboard transport controls (`Space`, `N`, `P`, `+`, `-`, `Tab`, `Q`).

## Global Constraints

- Standalone playback: audio MUST stream directly through local audio hardware without requiring any desktop or web application open.
- Aesthetic fidelity: retain Arcane theme (ember/gold palette, `#13141C` background), ANSI TrueColor album art conversion (`art.py`), and flame progress bar.
- Zero mandatory authentication: player functions immediately out of the box without requiring OAuth tokens, developer keys, or paid subscriptions.
- Auto-Push Rule: whenever code changes are made, commit and push to GitHub (`git push origin main`).
- Cross-platform binary management: use portable `mpv` executable bundled in `~/.config/bard/bin/` if not present in system PATH.

## Review Focus

1. **Stream Extraction Latency / Failure**: When `yt-dlp` extracts a stream URL for an unavailable or restricted video, `YTMusicClient.get_stream_url` must handle the exception gracefully and return `None` or raise a clean `AudioStreamError` without crashing the app.
2. **MPV IPC Pipe Disconnect**: If the background `mpv` process is killed or fails to open the IPC pipe/socket on Windows (`\\.\pipe\bard-mpv`), `AudioPlayer` must detect the drop, attempt a clean restart, or fail gracefully without hanging the UI event loop.
3. **Queue Auto-Advance**: When a song finishes playing (`end-file` event from mpv), the player must automatically advance to the next track in the current playlist/search queue.
4. **ANSI Thumbnail Scaling**: YouTube Music returns various thumbnail aspect ratios and resolutions (e.g. `w120-h120` or wide 16:9 thumbnails); `art.py` and `ZenStage` must crop/fit cleanly into the Arcane frame without stretching or throwing Pillow errors.
5. **Search with Empty or Special Characters**: Drawer search with empty strings, punctuation, or non-ASCII characters must return either valid results or a friendly "No tracks found" notice without breaking the OptionList.

---

### Task 1: Dependencies and Core Data Types

**Files:**
- Modify: `pyproject.toml`
- Create: `src/bard/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: Nothing
- Produces: `Track` dataclass:
  ```python
  @dataclass
  class Track:
      id: str
      title: str
      artist: str
      album: str
      duration_seconds: int
      thumbnail_url: str
      stream_url: Optional[str] = None

      @property
      def duration_ms(self) -> int:
          return self.duration_seconds * 1000

      def to_dict(self) -> dict: ...
  ```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from bard.models import Track

def test_track_instantiation_and_dict():
    track = Track(
        id="video123",
        title="Get Lucky",
        artist="Daft Punk",
        album="Random Access Memories",
        duration_seconds=248,
        thumbnail_url="https://example.com/thumb.jpg",
    )
    assert track.id == "video123"
    assert track.duration_ms == 248000
    d = track.to_dict()
    assert d["title"] == "Get Lucky"
    assert d["artist"] == "Daft Punk"
    assert d["album_art_url"] == "https://example.com/thumb.jpg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bard.models'"

- [ ] **Step 3: Update `pyproject.toml` and implement `Track` in `src/bard/models.py`**

Add `ytmusicapi>=1.12.0` and `yt-dlp>=2024.0.0` to `pyproject.toml` dependencies.
Implement `Track` with dataclass fields and `to_dict()` formatting suitable for `ZenStage`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit and push**

```bash
git add pyproject.toml src/bard/models.py tests/test_models.py
git commit -m "feat: add Track model and YouTube Music dependencies"
git push origin main
```

---

### Task 2: YouTube Music Catalog and Stream Extractor Client

**Files:**
- Create: `src/bard/ytmusic_client.py`
- Test: `tests/test_ytmusic_client.py`

**Interfaces:**
- Consumes: `Track` from `src/bard/models.py`
- Produces: `YTMusicClient`
  ```python
  class YTMusicClient:
      def __init__(self, auth_header: Optional[str] = None): ...
      def search(self, query: str, limit: int = 25) -> list[Track]: ...
      def get_trending(self, country: str = "US") -> list[Track]: ...
      def get_playlist_tracks(self, playlist_id: str) -> list[Track]: ...
      def get_stream_url(self, video_id: str) -> Optional[str]: ...
  ```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ytmusic_client.py
from unittest.mock import MagicMock, patch
from bard.ytmusic_client import YTMusicClient

def test_search_normalizes_tracks():
    mock_raw_results = [
        {
            "resultType": "song",
            "videoId": "abc1234",
            "title": "Harder, Better, Faster, Stronger",
            "artists": [{"name": "Daft Punk"}],
            "album": {"name": "Discovery"},
            "duration_seconds": 224,
            "thumbnails": [{"url": "https://img.jpg", "width": 120, "height": 120}],
        }
    ]
    with patch("bard.ytmusic_client.YTMusic") as MockYTMusic:
        mock_instance = MockYTMusic.return_value
        mock_instance.search.return_value = mock_raw_results
        client = YTMusicClient()
        tracks = client.search("Daft Punk")
        assert len(tracks) == 1
        assert tracks[0].id == "abc1234"
        assert tracks[0].title == "Harder, Better, Faster, Stronger"
        assert tracks[0].artist == "Daft Punk"
        assert tracks[0].album == "Discovery"
        assert tracks[0].duration_seconds == 224
        assert tracks[0].thumbnail_url == "https://img.jpg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ytmusic_client.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bard.ytmusic_client'"

- [ ] **Step 3: Implement `YTMusicClient` in `src/bard/ytmusic_client.py`**

Wrap `ytmusicapi.YTMusic` for searching, trending charts, and playlists.
Use `yt_dlp.YoutubeDL({'format': 'bestaudio/best', 'quiet': True})` in `get_stream_url` to extract direct media streams.
Handle extraction errors gracefully without crashing.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ytmusic_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit and push**

```bash
git add src/bard/ytmusic_client.py tests/test_ytmusic_client.py
git commit -m "feat: implement YTMusicClient catalog search and stream extractor"
git push origin main
```

---

### Task 3: Local MPV Audio Player Engine with IPC Control

**Files:**
- Create: `src/bard/audio_player.py`
- Modify: `src/bard/audio_engine.py` (ensure mpv binary discovery/downloader)
- Test: `tests/test_audio_player.py`

**Interfaces:**
- Consumes: Nothing
- Produces: `AudioPlayer`
  ```python
  class AudioPlayer:
      def __init__(self, binary_path: Optional[str] = None): ...
      def play(self, stream_url: str) -> bool: ...
      def pause(self) -> None: ...
      def resume(self) -> None: ...
      def toggle_pause(self) -> None: ...
      def stop(self) -> None: ...
      def seek(self, offset_seconds: float) -> None: ...
      def set_volume(self, volume: int) -> None: ...
      def get_volume(self) -> int: ...
      def get_position(self) -> float: ...
      def get_duration(self) -> float: ...
      def is_playing(self) -> bool: ...
      def close(self) -> None: ...
  ```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_audio_player.py
from unittest.mock import MagicMock, patch
from bard.audio_player import AudioPlayer

def test_player_command_generation():
    with patch("bard.audio_player.subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc
        player = AudioPlayer(binary_path="dummy_mpv")
        
        with patch.object(player, "_send_command") as mock_cmd:
            player.pause()
            mock_cmd.assert_called_with(["set_property", "pause", True])
            
            player.resume()
            mock_cmd.assert_called_with(["set_property", "pause", False])

            player.toggle_pause()
            mock_cmd.assert_called_with(["cycle", "pause"])

            player.set_volume(85)
            mock_cmd.assert_called_with(["set_property", "volume", 85])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_audio_player.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bard.audio_player'"

- [ ] **Step 3: Implement `AudioPlayer` in `src/bard/audio_player.py` and update `audio_engine.py`**

Implement MPV headless runner:
- Spawn `mpv` with `--no-video --idle=yes --input-ipc-server=<pipe/socket>`.
- On Windows, connect to `\\.\pipe\bard-mpv-<pid>`.
- On Unix/macOS, connect to `/tmp/bard-mpv-<pid>.sock`.
- Send JSON commands: `{"command": [...]}\n`.
- Query `time-pos`, `duration`, `pause`, `volume`.
- Update `audio_engine.py` to recognize `mpv` in `~/.config/bard/bin/` as the default local audio engine.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_audio_player.py -v`
Expected: PASS

- [ ] **Step 5: Commit and push**

```bash
git add src/bard/audio_player.py src/bard/audio_engine.py tests/test_audio_player.py
git commit -m "feat: implement AudioPlayer with MPV JSON-IPC control"
git push origin main
```

---

### Task 4: Update Curtain Drawer for YouTube Music Search and Playlists

**Files:**
- Modify: `src/bard/ui/curtain_drawer.py`
- Test: `tests/test_ui_drawer.py`

**Interfaces:**
- Consumes: `YTMusicClient`, `Track`
- Produces: `CurtainDrawer` with interactive YouTube search and curated playlists (Trending, Lo-Fi, Synthwave, Arcane)
  - Pressing `/` or selecting "Search" opens inline input to search any artist/song on YouTube Music.
  - Selecting a track emits `on_play(track)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ui_drawer.py
from bard.ui.curtain_drawer import CurtainDrawer
from bard.models import Track
from unittest.mock import MagicMock

def test_drawer_initialization_with_ytmusic():
    mock_client = MagicMock()
    mock_client.get_trending.return_value = [
        Track(id="1", title="Enemy", artist="Imagine Dragons", album="Arcane", duration_seconds=173, thumbnail_url="")
    ]
    drawer = CurtainDrawer(client=mock_client, on_play=MagicMock())
    assert drawer is not None
```

- [ ] **Step 2: Run test to verify it fails or needs updates**

Run: `pytest tests/test_ui_drawer.py -v`
Expected: FAIL or type mismatch if expecting SpotifyClient.

- [ ] **Step 3: Update `CurtainDrawer` in `src/bard/ui/curtain_drawer.py`**

- Accept `YTMusicClient` (or duck-typed client).
- Curate categories on the left:
  - "🔥 Trending Hits"
  - "⚡ Arcane & Cyberpunk"
  - "☕ Lo-Fi Beats"
  - "🌌 Synthwave Chill"
  - "🔍 Search Tracks..." (with Textual `Input` widget to type any song/artist)
- Right column displays track results. Selecting one fires `self.on_play(track)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ui_drawer.py -v`
Expected: PASS

- [ ] **Step 5: Commit and push**

```bash
git add src/bard/ui/curtain_drawer.py tests/test_ui_drawer.py
git commit -m "feat: update CurtainDrawer with YouTube Music categories and search"
git push origin main
```

---

### Task 5: Wire BardApp and ZenStage to AudioPlayer

**Files:**
- Modify: `src/bard/ui/app.py`
- Modify: `src/bard/ui/zen_stage.py`
- Modify: `src/bard/config.py`
- Modify: `src/bard/__main__.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `YTMusicClient`, `AudioPlayer`, `Track`, `ZenStage`, `CurtainDrawer`
- Produces: Fully interactive standalone Bard terminal application:
  - Space: instant local Play/Pause.
  - N/P: Next / Previous track in the current playlist/search queue.
  - + / -: Volume adjustment.
  - Tab: Open/close search and playlist drawer.
  - Selecting a track from drawer resolves stream and plays immediately.
  - Smooth 1s flame progress bar synced with local player position.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_app.py
from bard.ui.app import BardApp
from bard.config import BardConfig
from unittest.mock import MagicMock

def test_bard_app_mount_ytmusic():
    config = BardConfig()
    client = MagicMock()
    player = MagicMock()
    app = BardApp(config=config, client=client, player=player)
    assert app.player == player
    assert app.client == client
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app.py -v`
Expected: FAIL due to parameter differences or missing player.

- [ ] **Step 3: Update `BardApp`, `__main__.py`, and `config.py`**

- Update `BardApp.__init__` to accept `client: YTMusicClient` and `player: AudioPlayer`.
- Replace Spotify Web API polling with direct local player status updates (`player.get_position()`, `player.is_playing()`).
- On track selection in drawer:
  - Background thread extracts stream URL via `client.get_stream_url(track.id)`.
  - Tells `player.play(stream_url)`.
  - Calls `stage_widget.update_track(track.to_dict())`.
- Update `__main__.py`: remove Spotify login/pairing requirement; start `AudioPlayer` and launch `BardApp` directly.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_app.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite and verify end-to-end**

Run: `pytest`
Expected: All tests pass.

- [ ] **Step 6: Commit and push**

```bash
git add src/bard/ui/app.py src/bard/ui/zen_stage.py src/bard/config.py src/bard/__main__.py tests/test_app.py
git commit -m "feat: complete standalone YouTube Music playback integration in Bard"
git push origin main
```

---

### Task 6: System Verification and Live Playback Check

**Files:**
- Create: `scratch/verify_ytmusic_playback.py`

**Interfaces:**
- Consumes: `YTMusicClient`, `AudioPlayer`
- Produces: Live verified playback test proving music plays through Windows audio hardware with zero errors.

- [ ] **Step 1: Create verification script**

Write a script that searches for a track, extracts its audio stream, plays it for 5 seconds using `AudioPlayer`, verifies position advances and volume control, then cleanly stops.

- [ ] **Step 2: Run verification script**

Run: `.\.venv\Scripts\python.exe scratch/verify_ytmusic_playback.py`
Expected: Audio plays cleanly, position increments, returns exit code 0.

- [ ] **Step 3: Auto-push final changes**

```bash
git push origin main
```
