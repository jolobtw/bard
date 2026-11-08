# 🎵 B A R D
### The Arcane Terminal Music Player

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Textual](https://img.shields.io/badge/built%20with-Textual-teal.svg)](https://textual.textualize.io/)
[![Spotify Web API](https://img.shields.io/badge/Spotify-Web%20API-1DB954.svg)](https://developer.spotify.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Bard** is a distraction-free, aesthetic terminal Spotify player featuring 320 kbps direct streaming, high-density 24-bit TrueColor album art, keyboard-first navigation, and a signature Arcane dark-fantasy aesthetic.

---

## 🌟 Key Features

- **Zen Now-Playing Stage:** A distraction-free ambient music display featuring:
  - High-density 24-bit TrueColor ANSI half-block album artwork (`▀` / `▄`).
  - Arcane musical sigil empty-state artwork when paused or awaiting your next track.
  - Prominent track, artist, and album typography with real-time playback state.
  - Glowing Flame progress bar animating smoothly from Flame Orange (`#FF7A00`) to Amber Gold (`#FFD166`).
- **Instant Curtain Drawer (`[Tab]`):** A slide-out dual-tier browser to explore your playlists and queue individual tracks. Loads instantly with background fetching and shimmering loading states so playback is never interrupted.
- **Smart Rate-Limit & Quota Guard:** Built-in in-memory caching and intelligent exponential backoff to handle Spotify Web API rate limits gracefully without dropped frames or freezes.
- **Standalone Audio Engine (`librespot`):** Integrates the open-source `librespot` streaming engine to decode pristine 320 kbps Ogg Vorbis streams directly to your audio device—no official Spotify desktop app required!
- **Cross-Platform Audio Support:** Seamless playback on **Windows** (WASAPI) and **macOS** (CoreAudio for both Apple Silicon M-series and Intel).
- **Arcane Design System:** Styled with custom dark-fantasy design tokens, golden borders, and arcane rune glyphs (`✦ ❖ BARD ❖ Arcane Music Player`).

---

## ⌨️ Controls & Keybindings

### Global Controls
| Shortcut | Action |
| :--- | :--- |
| `Space` | **Play / Pause** toggle |
| `Tab` | **Toggle Playlists Drawer** (Left curtain slide-out) |
| `Esc` | **Close Drawer** (Return focus to Zen Stage) |
| `N` | **Next Track** |
| `P` | **Previous Track** |
| `+` or `=` | **Volume Up** (+5%) |
| `-` | **Volume Down** (-5%) |
| `Q` | **Quit Bard** |

### Inside the Playlists Drawer
| Shortcut | Action |
| :--- | :--- |
| `↑` / `↓` or `W` / `S` | Navigate up / down in playlists or tracks |
| `←` / `→` or `A` / `D` | Switch focus between Playlists column and Tracks column |
| `Enter` | Play highlighted playlist or track immediately |

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Spotify Premium Account** (required by Spotify for streaming and playback control).
- **Python 3.10 or newer**.

---

### 2. Spotify Developer Setup (One-time, ~60 seconds)
To allow Bard to connect to your Spotify account securely:
1. Log in to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Click **Create app**:
   - **App name:** `Bard`
   - **App description:** `Arcane Terminal Spotify Player`
   - **Redirect URIs:** `http://127.0.0.1:8888/callback` *(Be sure to click "Add")*
   - **Which API/SDKs are you planning to use?** Check **Web API**
3. Check the terms checkbox and click **Save**.
4. Go to **Settings** in your new app and copy your **Client ID**.

---

### 3. Installation & Setup

#### Step A: Clone the repository
```bash
git clone https://github.com/jolobtw/bard.git
cd bard
```

#### Step B: Set up Python virtual environment

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

**On macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

#### Step C: Run Bard
```bash
bard
```
*(Or run `python -m bard`)*

> **First Run Note:** On your first launch, Bard will prompt you for your **Client ID**, open a browser tab for a one-click authorization, and store your credentials securely in your user config directory (`~/.config/bard/config.json`).

---

## 🛠️ Direct Streaming Engine (`librespot`)

Bard functions out of the box as a remote control for any active Spotify Connect device (such as your phone, smart speaker, or desktop app).

To enable **direct terminal audio output** without running any other Spotify software:
1. **Windows:** Place the `librespot.exe` binary in `~/.config/bard/bin/librespot.exe` (or add it to your system `PATH`).
2. **macOS:** Install via Homebrew:
   ```bash
   brew install librespot
   ```
   *(Or place the binary in `~/.config/bard/bin/librespot`)*

When launched, Bard automatically discovers the engine, launches it quietly in the background as an audio daemon, registers the audio sink as **`"Bard"`**, and delivers uninterrupted 320 kbps sound.

---

## 📂 Project Structure

```text
bard/
├── src/bard/
│   ├── __init__.py
│   ├── __main__.py          # Entrypoint and daemon lifecycle
│   ├── art.py               # ANSI TrueColor art converter & Arcane empty sigils
│   ├── audio_engine.py      # librespot supervisor & process management
│   ├── auth.py              # OAuth2 authorization code flow with PKCE
│   ├── config.py            # Configuration loader and file persistence
│   ├── spotify_client.py    # Spotify Web API client with rate-limiting & cache
│   ├── theme.py             # Arcane color palette and theme tokens
│   └── ui/
│       ├── app.py           # Main Textual App orchestration
│       ├── curtain_drawer.py# Instant slide-out playlist & track navigator
│       ├── header.py        # Top arcane glyph status bar
│       └── zen_stage.py     # Center stage with artwork & glowing progress bar
├── tests/                   # Full automated test suite (pytest)
├── pyproject.toml           # Package configuration & dependencies
└── README.md
```

---

## 🧪 Running Tests

To run the automated test suite:
```bash
pytest
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
