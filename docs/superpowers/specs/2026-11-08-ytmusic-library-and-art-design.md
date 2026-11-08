# YouTube Music Personal Library, Multi-Type Search & High-Resolution Artwork Design

**Date:** 2026-11-08  
**Status:** Draft  
**Target:** Bard Terminal Music Player  

---

## 1. Intent & The "Why"

Bard is an Arcane-themed, standalone terminal music player. Having successfully pivoted from Spotify to YouTube Music for reliable standalone audio playback without requiring web or desktop apps, the player now needs to bridge the gap between anonymous public feeds and personal listening habits.

Users want:
1. **Their Personal Collection**: Access to their own curated playlists, liked tracks, and listening history directly within the terminal, alongside public trending and curated feeds.
2. **Deep Music Discovery**: The ability to search not only for individual songs, but also for specific artists and albums, with the ability to explore and play an entire album's tracklist.
3. **Hero-Grade Album Art**: Sharp, vibrant, high-definition album art that makes the Zen Now-Playing Stage look visually striking instead of pixelated and miniature.

---

## 2. Goals, Non-Goals, and Anti-Goals

### Goals
- **OAuth Device Flow Authentication**: Provide a rock-solid, permanent pairing flow via `google.com/device` that issues a refresh token, eliminating fragile browser cookie scraping.
- **Personal Library Integration**: Seamlessly display Liked Songs, User Playlists, and History in the Curtain Drawer when authenticated.
- **Album & Artist Exploration**: Search results display songs, albums, and artists. Selecting an album or artist dynamically loads its tracklist.
- **High-Definition ANSI Artwork**: Request full-resolution 544×544 artwork from YouTube Music and expand the terminal ANSI half-block canvas from 32×14 to a crisp 46×20 hero display.
- **Graceful Unauthenticated Degradation**: If not authenticated, Bard continues to function 100% anonymously for public search and trending feeds without nagging or blocking startup.

### Non-Goals
- Modifying user playlists (e.g. creating playlists, adding/removing tracks) from the terminal in this iteration. This design focuses on reading and streaming.
- Video playback or lyrics synchronization.
- Complex multi-account switching.

### Anti-Goals
- **No Mandatory Login Gate**: Never block Bard from launching if an account is not connected. Public explore and search must always remain accessible.
- **No Terminal Freezes**: Never execute YouTube API calls, image downloads, or stream extraction on the main Textual UI thread.
- **No Temporary Visitor Cookies**: Do not rely on brittle session cookies that expire when browser tabs close.

---

## 3. Constraints

- **Platform & Environment**: Windows, macOS, Linux (Python >= 3.10).
- **Auto-Push Rule**: All code changes must be committed and pushed to GitHub (`git push origin main`).
- **Aesthetic Fidelity**: Strictly preserve Bard's Arcane aesthetic (ember orange `#FF7A00`, gold `#FFD166`, slate `#2E3244`, dark surface `#13141C` and `#181A24`).
- **Terminal Sizing**: UI must adapt gracefully between standard 80×24 terminals and large maximized terminal windows.

---

## 4. Approaches Considered

### Approach 1: Integrated Personal Library & Arcane Hero Art (Selected)
- **Authentication**: Supports both in-app ("✦ Connect Account" option in drawer) and CLI (`bard --login`) device pairing. Tokens are cached in `~/.config/bard/oauth.json`.
- **Drawer Structure**: Clean visual hierarchy: "LIBRARY" (Liked Songs, Playlists, History), "DISCOVER" (Trending, Arcane, Lo-Fi, Synthwave), and "SEARCH" (Songs, Artists, Albums).
- **Art Quality**: Requests 544×544 HD image assets and renders on a 46×20 ANSI half-block grid.
- **Trade-off**: Requires Google Cloud Client credentials for the initial device flow setup, but provides permanent background auto-refreshing sessions.

### Approach 2: Lightweight CLI-Only Setup & Flat Lists
- Setup strictly via external `bard login` script before launch. Playlists appended to flat list without album/artist exploration.
- **Trade-off**: Simpler to write, but creates a disjointed user experience and lacks deep album/artist discovery.

### Approach 3: In-Drawer Modal Multi-Screen Explorer
- Pop-up modal dialogs inside Textual for authentication and full multi-screen drilldown.
- **Trade-off**: Cumbersome terminal keyboard navigation and excessive UI layer complexity.

**Selection**: Approach 1 was chosen by the user for its seamless, full-featured music player experience and visual polish.

---

## 5. Detailed Design

### 5.1 Authentication Flow (`OAuth Device Code`)

```
   Terminal (Bard)                     Google OAuth Server              Browser (User)
         │                                      │                             │
         │─── Request Device Code ─────────────>│                             │
         │<── Return user_code & verify_url ────│                             │
         │                                      │                             │
         │─── Display Pairing Box ───────────────────────────────────────────>│
         │    "Visit google.com/device          │                             │ (User visits URL &
         │     and enter code: ABCD-1234"       │                             │  clicks Approve)
         │                                      │                             │
         │─── Poll for Token (every 5s) ───────>│                             │
         │<── Return access_token & refresh_token                             │
         │                                      │                             │
         │─── Save to ~/.config/bard/oauth.json ─
         │    Initialize authenticated YTMusicClient
```

1. **Storage**: Credentials stored at `~/.config/bard/oauth.json` (chmod 600 where supported).
2. **Setup CLI**: `bard --login` runs the terminal pairing prompt with Rich formatting and automatically opens the browser.
3. **In-App Pairing**: Selecting "✦ Connect Account" in the Drawer opens an Arcane pairing overlay on the stage.
4. **Disconnection**: Option to disconnect removes `oauth.json` and resets client to anonymous mode immediately.

### 5.2 Personal Library Integration (`YTMusicClient`)

When `YTMusicClient` detects `oauth.json`, it initializes `YTMusic(auth=oauth_filepath)`.
New capabilities added to `YTMusicClient`:
- `is_authenticated() -> bool`: Returns `True` if initialized with valid OAuth credentials.
- `get_liked_songs(limit: int = 50) -> list[Track]`: Fetches user's liked music.
- `get_library_playlists(limit: int = 50) -> list[dict]`: Fetches user's custom and saved playlists (`id`, `title`, `trackCount`, `thumbnail`).
- `get_history() -> list[Track]`: Fetches recent playback history.
- `get_album_tracks(album_browse_id: str) -> list[Track]`: Fetches full tracklist of a specific album.
- `get_artist_top_tracks(artist_channel_id: str) -> list[Track]`: Fetches top tracks of an artist.

### 5.3 Drawer Layout & Multi-Type Search (`CurtainDrawer`)

The left column of the drawer is structured into clear, visually distinct categories:

```text
 ┌─ EXPLORE ────────────────────────┐┌─ TRACKS (25) ─────────────────────────────────┐
 │                                  ││                                               │
 │  ✦ YOUR LIBRARY                  ││   1.  Burn It All Down                        │
 │   ❤️ Liked Songs                 ││       League of Legends, PVRIS  •  03:22      │
 │   📂 Your Playlists              ││   2.  Breakthroughs (feat. Ray Chen)          │
 │   🕒 Listening History           ││       Arcane  •  01:59                        │
 │                                  ││                                               │
 │  ✦ CURATED FEEDS                 ││                                               │
 │   🔥 Trending Hits               ││                                               │
 │   ⚡ Arcane & Cyberpunk          ││                                               │
 │   ☕ Lo-Fi Beats                 ││                                               │
 │   🌌 Synthwave Chill             ││                                               │
 │                                  ││                                               │
 │  ✦ DISCOVERY & ACCOUNT           ││                                               │
 │   🔍 Search Songs & Albums...    ││                                               │
 │   ✦ Connect Account (or Status)  ││                                               │
 └──────────────────────────────────┘└───────────────────────────────────────────────┘
```

#### Multi-Type Search:
When typing in Search (`/`):
- Searches YouTube Music with filters for songs and albums.
- In the right column, results clearly badge their type (e.g., `[Album]` vs `[Song]`).
- Clicking an `[Album]` dynamically expands its full tracklist so the user can play any track from that album.

### 5.4 High-Resolution Album Artwork (`art.py` & `ZenStage`)

1. **Resolution Escalation in URL Fetching**:
   YouTube Music thumbnail URLs typically end with `=w60-h60-l90-rj` or `=w120-h120`. `art.py` inspects the URL and upgrades thumbnail queries to `=w544-h544-l90-rj` (or `=s800`), obtaining native high-definition artwork directly from Google's CDN.
2. **Expanded Character Grid**:
   - `width` increased from 32 to **46 character columns**.
   - `height` increased from 14 to **20 character rows** (equivalent to 40 vertical pixels via upper-half blocks `▀`).
   - Lanczos downsampling with subtle contrast adjustment prevents dark murky colors and produces vibrant, crisp cover art.
3. **Adaptive Canvas Alignment**:
   `ZenStage` centers the 46×20 art block inside the 86-column Arcane stage container with balanced vertical padding.

---

## 6. What's Left to the Builder

- Exact debounce timeout for live search inputs (recommended: 300ms).
- Fallback placeholder sigil sizing when a track has no thumbnail URL.
- Specific error messaging formatting when Google OAuth device flow times out or is canceled by user.
