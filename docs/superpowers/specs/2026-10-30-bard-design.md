# Bard: Arcane Terminal Spotify Player
## Design Specification

**Date:** 2026-10-30  
**Project:** `bard`  
**Author:** Antigravity & User  
**Status:** In Review (Brainstorming Phase)

---

### 1. Intent & The "Why"
The user wants a dedicated, beautiful, distraction-free terminal music player for Spotify that runs continuously on their screen during both deep work and personal relaxation. 

The existing official Spotify desktop client is resource-heavy (Electron/Chromium consuming 400MB–1GB+ RAM), cluttered with unsolicited recommendations and podcasts, and visually disconnected from the user's bespoke terminal ecosystem. `bard` fills this gap by acting as a high-fidelity, keyboard-driven music station that seamlessly matches the **Arcane Theme** aesthetic shared by **Tome** and **JIRA TUI**.

---

### 2. Goals, Non-Goals & Anti-Goals

#### Goals
- **True Standalone Playback:** Direct audio playback through the user's audio device without needing the official Spotify desktop application running.
- **Arcane Theme Alignment:** Flawless visual consistency with Arcane Theme design tokens (`#13141C` canvas, `#181A24` panels, `#FF7A00` active flame borders, `#FFD166` gold accents, `✦ ❖` header glyphs).
- **Zen Monolith Mode:** A calm, aesthetic ambient screen featuring a prominent album cover, track metadata, glowing flame progress bar, and real-time playback state.
- **Left-Side Curtain Drawer:** An on-demand dual-tier drawer toggled via `[Tab]` to browse saved playlists and choose specific songs without breaking the immersion of the player.
- **Keyboard-First Ergonomics:** Immediate, responsive controls for play/pause, track skipping, volume, and drawer navigation.

#### Non-Goals (Version 1)
- Advanced music management features like creating/editing playlists, following artists, or lyrics karaoke mode.
- Offline track downloading / local caching of encrypted audio files.
- Support for non-Spotify audio sources (local MP3 libraries or SoundCloud).

#### Anti-Goals
- **Clutter & Feature Bloat:** Adding busy feeds, podcast carousels, or algorithm-driven noise. The user experience must remain tranquil and focused.
- **High Resource Footprint:** Memory usage should remain under ~60MB RAM and negligible CPU when idle/playing.
- **Terminal Lockups:** Audio decoding or API calls must never block the Textual UI rendering loop.

---

### 3. Constraints
- **Spotify Premium:** Required by Spotify's proprietary audio streaming protocol.
- **Operating System:** Cross-platform: **Windows** (WASAPI / Rodio audio backend) and **macOS** (CoreAudio / Rodio audio backend, supporting both Apple Silicon M-series and Intel).
- **Configuration & State Paths:** Cross-platform standard directory `~/.config/bard/` for credentials, caching, and tokens on both macOS and Windows (matching `arcane-theme`).
- **Terminal Environment:** Supports modern terminal capabilities across platforms (Ghostty, WezTerm, Windows Terminal, Kitty, iTerm2, etc. with TrueColor ANSI, UTF-8 glyphs, and optional image rendering with ANSI block fallback).
- **Design System:** Must import and honor `arcane-theme` tokens (`theme.json` / `arcane_theme.py`).

---

### 4. Approaches Considered

1. **Python + Textual with Embedded `librespot` (Selected)**
   - *Architecture:* Python terminal UI application using the Textual framework, directly importing `arcane_theme.py`. A lightweight `librespot` binary is managed under the hood as the headless audio decoding engine. Spotify Web API is used for library/playlist metadata and control.
   - *Trade-offs:* Rapid development, native compatibility with existing Python Arcane tools (`jira-tui`), clean async model. Slightly larger memory profile than pure Rust (~45MB vs ~20MB), but well within the lightweight target.
2. **Go + Bubble Tea / Lipgloss (Considered)**
   - *Architecture:* Go application mirroring `tome`.
   - *Trade-offs:* Blazing fast and single binary, but coordinating complex audio streaming protocol bindings across Go and C/Rust `librespot` adds unnecessary plumbing compared to the mature Python + headless daemon pattern.
3. **Rust + Ratatui + Native `librespot` (Considered)**
   - *Architecture:* Single monolithic Rust application.
   - *Trade-offs:* Lowest resource footprint, but higher development complexity and slower cycle times for styling tweaks.

---

### 5. Detailed UX & Functional Design

#### 5.1 Screen Layout & States

##### State A: The Zen Stage (Default View)
The primary screen when music is playing or paused:
- **Top Header:** 
  `✦ ❖ BARD ❖ Arcane Spotify Player` (Left)
  Badges (Right): `[󰓇 Spotify Connect]` `[󰋋 320 kbps]` `[󰐊 Playing]`
- **Center Hero Card:**
  - Album Artwork Box: Renders high-res art via Kitty/Sixel graphics protocol if supported, with automatic fallback to high-quality colored ANSI character mosaic.
  - Track Title: Large, bold, Bright White (`#FFFFFF`).
  - Artist & Album: Regular Slate (`#A6ADC8`) with Muted (`#6C7086`) release year.
- **Flame Progress Bar:**
  - Smooth 1-second interval ticker.
  - Current elapsed timestamp `01:42` on left, remaining/total `03:50` on right.
  - Filled track uses gradient Flame Orange (`#FF4500`) to Amber Gold (`#FFD166`), with unplayed track in Slate Gray (`#2E3244`).
- **Footer Status & Controls Bar:**
  - Status indicators: Shuffle, Repeat, Volume percentage (`󰕾 80%`).
  - Keybinding hints: `[Space] Play/Pause` `[Tab] Playlists` `[N] Next` `[P] Prev` `[+/-] Volume` `[Q] Quit`.

##### State B: The Left-Side Curtain Drawer (Active View)
Triggered by pressing `[Tab]`:
- A split drawer slides open occupying the left ~55% of the screen, with the right ~45% showing the dimmed/receding Zen Stage.
- **Left Column of Drawer:** Scrollable list of user's Saved Playlists & Liked Songs.
  - Active selection highlighted with Arcane Selection Slate (`#262938`) and Flame indicator (`>` or active flame border).
- **Right Column of Drawer:** Songs inside the currently highlighted playlist (Title, Artist, Duration).
- **Interaction:**
  - `↑/↓` or `W/S`: Navigate current list.
  - `Right / Tab`: Move focus from Playlists to Songs.
  - `Left`: Move focus back to Playlists.
  - `Enter`: Start playback of the highlighted playlist or track.
  - `Esc`: Close the drawer and return full focus to the Zen Stage.

---

### 6. Architecture & Implementation Plan

```
┌────────────────────────────────────────────────────────────────────────┐
│                          bard (Textual UI)                             │
│  - Arcane Theme Styling (arcane_theme.py)                              │
│  - Zen Stage Widget (Now Playing, Progress, Album Art)                 │
│  - Left-Side Curtain Drawer Widget (Playlists & Tracks)                │
└───────────────────┬──────────────────────────────────┬─────────────────┘
                    │                                  │
         (Spotify Web API HTTPS)              (Subprocess Management)
                    │                                  │
┌───────────────────▼──────────────────────┐   ┌───────▼─────────────────┐
│     Spotify Web API                      │   │   Headless librespot    │
│  - Authenticates via OAuth 2.0 PKCE      │   │  - Device Name: "Bard"  │
│  - Retrieves Playlists & Tracks          │   │  - Auth: --enable-oauth │
│  - Sends Play/Pause/Skip/Seek to "Bard"  │   │  - Streams 320kbps audio│
└──────────────────────────────────────────┘   └─────────────────────────┘
```

#### 6.1 Authentication & Playback Control Architecture (Architectural Calls)
- **Playback Control via Spotify Connect:** `bard` acts as the command center. When launched, `bard` runs `librespot` in the background with the device name `"Bard"`. `bard` sends all playback commands (Play, Pause, Skip, Transfer Playback) through Spotify's standard Web API targeting the `"Bard"` audio device. This ensures rock-solid audio streaming without complex local IPC plumbing.
- **First-Run Authentication Flow:**
  - **Streaming Audio Engine (`librespot`):** Authenticates via `librespot --enable-oauth` on first run, which generates a one-click Spotify authorization URL and caches session credentials locally in `~/.config/bard/`.
  - **Interface & Metadata (Web API):** Uses standard OAuth 2.0 PKCE.
  - **Spotify Developer App:** A personal Spotify Developer Client ID & Redirect URI (`http://127.0.0.1:8888/callback`) is used. On first launch, if no credentials exist, `bard` provides a friendly, guided terminal onboarding prompt to enter the Client ID, which is securely saved in `~/.config/bard/config.json`.

#### 6.2 Album Art Rendering Engine
- Fetches the 300x300 or 640x640 album artwork URL from track metadata.
- Detects terminal graphics capabilities:
  - If Kitty protocol or Sixel is supported by the terminal: renders graphic image buffer.
  - Fallback: converts downscaled image to 24-bit ANSI half-block characters (`▀` / `▄`), preserving vivid album colors.

---

### 7. What is Left to the Builder
- Selection of specific Python Spotify Web API wrapper (`spotipy` or custom lightweight async client).
- Managing binary distribution/download for the `librespot` Windows executable on first launch if not present.
- Fine-tuning exact animation speeds for the curtain drawer.
