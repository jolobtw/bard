# YouTube Music Personal Library, Multi-Type Search & High-Resolution Artwork Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google OAuth Device Code pairing for YouTube Music personal library access (playlists, liked tracks, history), multi-type search with album drill-down, and high-resolution 46×20 Hero album artwork.

**Architecture:** A lightweight `YTMusicOAuth` device-code manager pairs user accounts via `google.com/device` and persists refreshable tokens to `~/.config/bard/oauth.json`. `YTMusicClient` exposes personal library and album extraction methods. `CurtainDrawer` integrates a hierarchical view with drill-down and back-navigation (`[ ◄ Back ]` action and `Backspace`). `art.py` upgrades thumbnail requests to 544×544 HD originals and renders responsive 46×20 ANSI half-block Hero artwork in `ZenStage`.

**Tech Stack:** Python 3.10+, Textual, Rich, Pillow (LANCZOS downsampling), ytmusicapi, requests.

**Spec:** `docs/superpowers/specs/2026-11-08-ytmusic-library-and-art-design.md`

## Global Constraints

- **Auto-Push Rule**: Every code change must be committed and pushed to GitHub (`git push origin main`).
- **Zero Mandatory Login Gate**: Bard MUST continue to work 100% anonymously for public search and trending music if no account is paired.
- **Aesthetic Fidelity**: Strictly preserve Bard's Arcane color palette (ember `#FF7A00`, gold `#FFD166`, slate `#2E3244`, surface `#13141C` and `#181A24`).
- **Responsive Terminal Adaptation**: Art and stage layout must automatically downscale on compact terminals (< 32 rows or < 86 cols) so controls are never clipped or hidden.

## Review Focus

1. **OAuth Token Refresh & Expiration**: When access tokens expire, `YTMusicOAuth` and `ytmusicapi` must automatically refresh using `refresh_token` without prompting the user again or raising unhandled 401 exceptions.
2. **Thumbnail URL Upgrades**: YouTube Music serves varied image URL formats (`googleusercontent.com`, `yt3.ggpht.com`, `i.ytimg.com`). `_upgrade_thumbnail_url()` must safely rewrite dimensions to `=w544-h544-l90-rj` or `=s800` without breaking relative URLs or non-standard CDN query strings.
3. **Drawer Drill-Down Stack Integrity**: Drilling into an album/playlist must preserve the parent category, search query, and scroll position so pressing Back (`Backspace` or `[ ◄ Back ]`) restores the exact previous state without blank screens.
4. **Queue Playback from Drilled Containers**: Selecting a track inside a drilled album/playlist must enqueue the entire container so `Next` (`N`) and `Prev` (`P`) navigate within that container's tracks.
5. **Pairing Abort & Timeout**: If a user cancels device pairing or the code expires after Google's polling timeout, the app must reset gracefully to anonymous mode without hanging background threads.

---

### Task 1: High-Resolution Album Art Pipeline and Responsive Stage

**Files:**
- Modify: `src/bard/art.py`
- Modify: `src/bard/ui/zen_stage.py`
- Test: `tests/test_art.py`
- Test: `tests/test_ui_stage.py`

**Interfaces:**
- Consumes: `art_url: str`
- Produces:
  ```python
  def upgrade_thumbnail_url(url: str, target_size: int = 544) -> str: ...
  def render_album_art(url_or_path: str, width: int = 46, height: int = 20) -> str: ...
  ```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_art.py
from bard.art import upgrade_thumbnail_url, render_album_art

def test_upgrade_thumbnail_url_rewrites_dimensions():
    low_res = "https://yt3.googleusercontent.com/abc=w60-h60-l90-rj"
    high_res = upgrade_thumbnail_url(low_res, target_size=544)
    assert "=w544-h544" in high_res

def test_upgrade_thumbnail_url_handles_s_param():
    low_res = "https://lh3.googleusercontent.com/xyz=s120"
    high_res = upgrade_thumbnail_url(low_res, target_size=544)
    assert "=s544" in high_res or "=w544-h544" in high_res

def test_render_album_art_hero_dimensions():
    # Should render 46 chars wide by 20 rows high
    ansi = render_album_art("", width=46, height=20)
    lines = ansi.split("\n")
    assert len(lines) == 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\pytest tests/test_art.py -v`
Expected: FAIL with `ImportError: cannot import name 'upgrade_thumbnail_url'`

- [ ] **Step 3: Implement thumbnail upgrading and responsive sizing**

- In `src/bard/art.py`:
  - Implement `upgrade_thumbnail_url(url: str, target_size: int = 544) -> str`: regex replace `=w\d+-h\d+` with `=w{target_size}-h{target_size}` and `=s\d+` with `=s{target_size}`.
  - Update `fetch_image(url)` to call `upgrade_thumbnail_url(url)`.
  - Default `render_album_art` and `render_sigil_art` to `width=46, height=20`.
- In `src/bard/ui/zen_stage.py`:
  - Implement responsive sizing: check `self.size.height` and `self.size.width`.
  - If `height < 32` or `width < 86`, use compact dimensions `width=32, height=14`.
  - If `height >= 32` and `width >= 86`, use Hero dimensions `width=46, height=20`.
  - Update `#stage-container` CSS max-width to allow comfortable hero art display.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\pytest tests/test_art.py tests/test_ui_stage.py -v`
Expected: PASS

- [ ] **Step 5: Commit and push**

```bash
git add src/bard/art.py src/bard/ui/zen_stage.py tests/test_art.py tests/test_ui_stage.py
git commit -m "feat(art): implement high-resolution thumbnail upgrading and hero stage sizing"
git push origin main
```

---

### Task 2: OAuth 2.0 Device Code Manager & Token Persistence

**Files:**
- Create: `src/bard/oauth.py`
- Modify: `src/bard/config.py`
- Test: `tests/test_oauth.py`

**Interfaces:**
- Consumes: Nothing
- Produces: `YTMusicOAuth`
  ```python
  class YTMusicOAuth:
      def __init__(self, token_path: Optional[Path] = None): ...
      def get_device_code(self) -> dict: ... # returns {'verification_url', 'user_code', 'device_code', 'expires_in', 'interval'}
      def poll_for_token(self, device_code: str, interval: int = 5, timeout: int = 300) -> Optional[dict]: ...
      def save_tokens(self, tokens: dict) -> None: ...
      def load_tokens(self) -> Optional[dict]: ...
      def clear_tokens(self) -> None: ...
      def is_authenticated(self) -> bool: ...
  ```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_oauth.py
from unittest.mock import MagicMock, patch
from bard.oauth import YTMusicOAuth

def test_oauth_get_device_code():
    with patch("bard.oauth.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "device_code": "dev123",
            "user_code": "ABCD-WXYZ",
            "verification_url": "https://www.google.com/device",
            "expires_in": 1800,
            "interval": 5,
        }
        oauth = YTMusicOAuth()
        res = oauth.get_device_code()
        assert res["user_code"] == "ABCD-WXYZ"
        assert res["verification_url"] == "https://www.google.com/device"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\pytest tests/test_oauth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bard.oauth'`

- [ ] **Step 3: Implement `YTMusicOAuth` in `src/bard/oauth.py`**

- Use YouTube on TV public client ID / device OAuth endpoint (`https://oauth2.googleapis.com/device/code`).
- Implement `get_device_code()`, `poll_for_token()`, token saving/loading at `~/.config/bard/oauth.json`.
- Support custom client credentials override in `BardConfig`.
- Add `oauth_path` and `is_authenticated()` properties to `BardConfig`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\pytest tests/test_oauth.py -v`
Expected: PASS

- [ ] **Step 5: Commit and push**

```bash
git add src/bard/oauth.py src/bard/config.py tests/test_oauth.py
git commit -m "feat(auth): implement YTMusicOAuth device code manager and token persistence"
git push origin main
```

---

### Task 3: Personal Library API & Album/Artist Traversal

**Files:**
- Modify: `src/bard/ytmusic_client.py`
- Test: `tests/test_ytmusic_client.py`

**Interfaces:**
- Consumes: `YTMusicOAuth`, `Track`
- Produces: `YTMusicClient` with library methods:
  ```python
  class YTMusicClient:
      def is_authenticated(self) -> bool: ...
      def get_liked_songs(self, limit: int = 50) -> list[Track]: ...
      def get_library_playlists(self, limit: int = 50) -> list[dict]: ...
      def get_history(self) -> list[Track]: ...
      def get_album_tracks(self, browse_id: str) -> list[Track]: ...
      def search_all(self, query: str) -> dict: ... # returns {"songs": list[Track], "albums": list[dict], "artists": list[dict]}
  ```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ytmusic_client.py
from unittest.mock import MagicMock, patch
from bard.ytmusic_client import YTMusicClient

def test_client_get_liked_songs():
    client = YTMusicClient()
    with patch.object(client, "_ytm") as mock_ytm:
        mock_ytm.get_liked_songs.return_value = {
            "tracks": [
                {"videoId": "v1", "title": "Liked Track 1", "artists": [{"name": "Artist 1"}], "duration_seconds": 180, "thumbnails": []}
            ]
        }
        tracks = client.get_liked_songs()
        assert len(tracks) == 1
        assert tracks[0].title == "Liked Track 1"
        assert tracks[0].id == "v1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\pytest tests/test_ytmusic_client.py -k "test_client_get_liked_songs" -v`
Expected: FAIL with `AttributeError: 'YTMusicClient' object has no attribute 'get_liked_songs'`

- [ ] **Step 3: Implement library and traversal methods in `src/bard/ytmusic_client.py`**

- Initialize `YTMusic` with `oauth.json` when present.
- Implement `get_liked_songs()`, `get_library_playlists()`, `get_history()`.
- Implement `get_album_tracks(browse_id: str) -> list[Track]` via `ytm.get_album()`.
- Implement `search_all(query: str)` querying `ytm.search()` across songs and albums.
- Handle unauthenticated state cleanly (return empty list without throwing).

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\pytest tests/test_ytmusic_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit and push**

```bash
git add src/bard/ytmusic_client.py tests/test_ytmusic_client.py
git commit -m "feat(client): add personal library, album extraction, and multi-type search"
git push origin main
```

---

### Task 4: Curtain Drawer Library Sections & Drill-Down Navigation

**Files:**
- Modify: `src/bard/ui/curtain_drawer.py`
- Test: `tests/test_ui_drawer.py`

**Interfaces:**
- Consumes: `YTMusicClient`, `Track`
- Produces: `CurtainDrawer` with visual sections, drill-down container navigation, and `[ ◄ Back ]` action.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ui_drawer.py
from bard.ui.curtain_drawer import CurtainDrawer
from bard.models import Track
from unittest.mock import MagicMock

def test_drawer_library_categories_when_authenticated():
    mock_client = MagicMock()
    mock_client.is_authenticated.return_value = True
    drawer = CurtainDrawer(client=mock_client)
    category_ids = [c["id"] for c in drawer.categories]
    assert "liked" in category_ids
    assert "library_playlists" in category_ids
    assert "history" in category_ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\pytest tests/test_ui_drawer.py -k "test_drawer_library_categories" -v`
Expected: FAIL with `AssertionError: assert 'liked' in category_ids`

- [ ] **Step 3: Implement library categories and drill-down navigation in `CurtainDrawer`**

- Add category sections:
  - If authenticated: `❤️ Liked Songs`, `📂 Your Playlists`, `🕒 History`.
  - Discover: `🔥 Trending Hits`, `⚡ Arcane`, `☕ Lo-Fi`, `🌌 Synthwave`.
  - Discovery & Auth: `🔍 Search Music...`, `✦ Connect Account` / `✦ Disconnect`.
- Implement drill-down view state:
  - When selecting a playlist or album item, store breadcrumb stack `self._nav_stack`.
  - Load album/playlist tracks into `#track-list`.
  - First item rendered in `#track-list` is `[ ◄ Back to Playlists / Search ]`.
  - Selecting Back item or pressing `Backspace` / `h` returns to parent list.
- Keep two-tier track styling intact: Bold full-width title on row 1, subtle indented artist and duration on row 2.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\pytest tests/test_ui_drawer.py -v`
Expected: PASS

- [ ] **Step 5: Commit and push**

```bash
git add src/bard/ui/curtain_drawer.py tests/test_ui_drawer.py
git commit -m "feat(ui): add personal library drawer categories and drill-down back navigation"
git push origin main
```

---

### Task 5: In-App Device Pairing Screen & CLI `--login` Command

**Files:**
- Modify: `src/bard/__main__.py`
- Modify: `src/bard/ui/app.py`
- Test: `tests/test_main.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `YTMusicOAuth`, `BardApp`, `CurtainDrawer`
- Produces:
  - CLI `bard --login` command that initiates device flow and awaits approval in terminal.
  - In-app pairing overlay/banner when selecting "✦ Connect Account" in the drawer.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main.py
from unittest.mock import patch, MagicMock
from bard.__main__ import run_device_login

def test_run_device_login_success():
    with patch("bard.__main__.YTMusicOAuth") as MockOAuth:
        mock_instance = MockOAuth.return_value
        mock_instance.get_device_code.return_value = {
            "verification_url": "https://www.google.com/device",
            "user_code": "ABCD-1234",
            "device_code": "dev_code",
            "interval": 1,
            "expires_in": 300,
        }
        mock_instance.poll_for_token.return_value = {"access_token": "acc", "refresh_token": "ref"}
        ok = run_device_login()
        assert ok is True
        mock_instance.save_tokens.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\pytest tests/test_main.py -k "test_run_device_login_success" -v`
Expected: FAIL with `ImportError: cannot import name 'run_device_login'`

- [ ] **Step 3: Implement login flow in `__main__.py` and in-app handler in `BardApp`**

- In `src/bard/__main__.py`:
  - Add CLI argument `--login` / `--logout`.
  - Implement `run_device_login()`: prints Rich Arcane panel with verification URL and code, attempts auto-opening browser, polls for token, and saves credentials.
- In `src/bard/ui/app.py`:
  - Handle "✦ Connect Account" callback from drawer: opens device pairing screen or opens browser.
  - On pairing completion, refreshes `self.client` and tells `drawer.refresh_categories()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\pytest tests/test_main.py tests/test_app.py -v`
Expected: PASS

- [ ] **Step 5: Commit and push**

```bash
git add src/bard/__main__.py src/bard/ui/app.py tests/test_main.py tests/test_app.py
git commit -m "feat(auth): add CLI --login pairing command and in-app account connection"
git push origin main
```

---

### Task 6: System Verification and Live Playback Check

**Files:**
- Create: `scratch/verify_library_and_art.py`

**Interfaces:**
- Consumes: `art.py`, `YTMusicOAuth`, `YTMusicClient`
- Produces: Live validation verifying high-res artwork URL rewriting and rendering, OAuth device code generation, and multi-type search results.

- [ ] **Step 1: Create verification script**

Write `scratch/verify_library_and_art.py`:
- Tests thumbnail upgrade regex on real YouTube Music image URLs.
- Tests generating 46×20 ANSI Hero art string.
- Tests `YTMusicOAuth.get_device_code()` obtaining a real Google device authorization code and verification link.
- Tests `YTMusicClient.search_all("Daft Punk")` returning categorized results.

- [ ] **Step 2: Run verification script**

Run: `.\.venv\Scripts\python.exe scratch/verify_library_and_art.py`
Expected: Outputs formatted Hero art preview, valid device code payload, and exit code 0.

- [ ] **Step 3: Run full pytest suite**

Run: `.\.venv\Scripts\pytest`
Expected: All 82+ tests pass.

- [ ] **Step 4: Commit and push**

```bash
git add scratch/verify_library_and_art.py
git commit -m "chore: add verification script for library access, search, and hero art"
git push origin main
```
