# 🎵 B A R D
### The Arcane Terminal Spotify Player

A distraction-free, aesthetic terminal Spotify station with standalone 320 kbps streaming, live auto-syncing Arcane Theme styling, and keyboard-first controls.

---

## 🌟 Key Features

- **Zen Now-Playing Stage:** Uncluttered ambient music display featuring high-density 24-bit TrueColor ANSI half-block album artwork (`▀` / `▄`), prominent track typography, and real-time playback state.
- **Glowing Flame Progress Bar:** Smoothly animating timeline transitioning from Flame Orange (`#FF7A00`) to Amber Gold (`#FFD166`) with current and remaining track times.
- **Left-Side Curtain Drawer (`[Tab]`):** Slide-out dual-tier browser to inspect your saved Spotify playlists and pick individual tracks on demand without breaking the player's ambient focus.
- **Standalone Audio Engine:** Integrates the open-source `librespot` engine to decode pristine 320 kbps Ogg Vorbis streams directly to your audio device without needing the official Spotify desktop client open.
- **Cross-Platform:** Seamless experience on both **Windows** (WASAPI) and **macOS** (CoreAudio on Apple Silicon M-series & Intel).
- **Arcane Design System:** Native integration with `arcane-theme` design tokens and header glyphs (`✦ ❖ BARD ❖ Arcane Spotify Player`).

---

## ⌨️ Controls & Keybindings

| Shortcut | Action |
| :--- | :--- |
| `Space` | **Play / Pause** toggle |
| `Tab` | **Toggle Playlists Drawer** (Left curtain) |
| `Esc` | **Close Drawer** (Return to Zen Stage) |
| `N` | **Next Track** |
| `P` | **Previous Track** |
| `+` or `=` | **Volume Up** (+5%) |
| `-` | **Volume Down** (-5%) |
| `Q` | **Quit Bard** |

*Inside the Playlists Drawer:*
- `↑ / ↓` or `W / S`: Navigate playlists or tracks.
- `← / →`: Switch focus between Playlists column and Tracks column.
- `Enter`: Start playback of highlighted playlist or track.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Spotify Premium Account** (required by Spotify for third-party streaming).
- **Python 3.10+**

### 2. Spotify Developer Setup (One-time, 60 seconds)
1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create app**:
   - **App name:** `Bard`
   - **App description:** `Arcane Terminal Spotify Player`
   - **Redirect URIs:** `http://127.0.0.1:8888/callback` *(Click "Add")*
   - **API/SDKs:** Check **Web API**
3. Save and copy your **Client ID**.

### 3. Running Bard

#### On Windows:
```powershell
cd ~/tools/bard
.\.venv\Scripts\python -m bard
```

#### On macOS:
```bash
cd ~/tools/bard
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python3 -m bard
```

On first launch, Bard will prompt you once for your **Client ID**, open your browser for a quick authorization click, and save credentials safely in `~/.config/bard/config.json`.

---

## 🛠️ Direct Streaming Engine (`librespot`)

Bard seamlessly acts as a Spotify Connect controller for your existing speakers right out of the box. 

To enable direct terminal sound output without any official Spotify app running:
- **Windows:** Place `librespot.exe` in `~/.config/bard/bin/librespot.exe` (or in your system PATH).
- **macOS:** Install via Homebrew (`brew install librespot`) or place the binary in `~/.config/bard/bin/librespot`.

Bard automatically discovers the engine, boots it quietly in the background, registers the device as **`"Bard"`**, and delivers uninterrupted 320 kbps high-fidelity playback.
