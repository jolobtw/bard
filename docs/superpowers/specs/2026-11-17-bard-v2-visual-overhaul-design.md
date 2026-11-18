# Bard v2 Visual Overhaul — Design Specification

**Date:** 2026-11-17  
**Status:** Draft (Pending User Approval)  
**Scope:** Visual & layout overhaul of Bard's main Textual UI (`ZenStage`), queue visibility, and `mpv` telemetry/device wiring, preserving all existing playback, YouTube Music browsing, OAuth, and keybinding behavior.

---

## 1. Intent & Why

Overhaul Bard from its current single-column centered `ZenStage` layout into an "Obsidian & Ember" multi-pane terminal interface inspired by the v2.1 visual design spec (`bard_v2_1_design_implementation_specification.md`), while:
- Keeping the application titled **Bard** (discarding all "Observatory" branding/references).
- Preserving 100% of Bard's existing YouTube Music browsing (`CurtainDrawer`), OAuth pairing, `mpv` JSON-IPC playback, and keyboard shortcuts.
- Adding an always-visible, live-filterable **Playlist Queue** panel backed by `BardApp.queue`, a simulated play-state-gated **Center-Outward Harmonic Spectrum**, and real `mpv` stream/output-device telemetry.

---

## 2. Goals, Non-Goals, and Anti-Goals

### Goals
- **Visual Overhaul ("Obsidian & Ember"):** Adopt the high-contrast `#0D0E11` / `#14161A` / `#1B1E24` surfaces, `#2C323D` slate borders, and `#8F3900` → `#FF7B00` → `#FF9E2C` → `#FFD28A` amber/gold accent ramp across the main stage, header, and footer.
- **Two-Tier Command Layout:**
  1. **Top Visualization Deck (100% width):** Simulated center-outward vertical frequency spectrum (play-state-gated) + full-width interactive timeline progress scrubber.
  2. **Bottom Three-Column Deck (equal `1fr` thirds):**
     - **Left Column:** Framed full-color 2×3 sextant album art + track metadata + real `mpv` codec/sample-rate badge + source label.
     - **Center Column:** Always-visible, live-filterable active queue (`BardApp.queue`) with `J`/`K`/`Enter`/`/` navigation and mouse click support.
     - **Right Column:** Transport controls (3-state repeat `OFF`/`ALL`/`ONE`), full-width interactive volume fader + mute toggle, and clickable `mpv` output device selector.
- **Compact Chrome:** Keep a compact `ArcaneHeader` at the top and add a truthful 1-line Windows Terminal / Bard status footer at the bottom.
- **Non-Breaking UX:** Preserve `[Tab]` `CurtainDrawer` discovery/search/OAuth and all existing global keybindings (`Space`, `Tab`, `Esc`, `N`, `P`, `S`, `R`, `M`, `+`/`=`, `-`, `Q`).

### Non-Goals
- Real-time OS audio loopback capture (e.g., WASAPI loopback) or PCM/FFT analysis.
- Replacing or redesigning `CurtainDrawer` functionality (only minor palette alignment if needed, keeping its layout/categories/search/OAuth flow intact).
- Adding BPM detection, release year scraping, or modifying `Track` / `YTMusicClient` data models for unsupported fields.
- Changing existing global keybindings (`N`/`P` stay Next/Previous; `B`/`Z` are not adopted).

### Anti-Goals
- Fabricating fake telemetry (no hardcoded `/dev/pts/0`, no fake `[FLAC · 24-BIT/96kHz]` or `[112 BPM]` badges, no fake hardware DAC names).
- Leaving dead/duplicate stage UI code in the repository.
- Breaking `test_theme.py` or letting remote `~/.config/arcane/theme.json` sync override the new Obsidian & Ember palette.

---

## 3. Constraints

- **Framework & Runtime:** Python `>=3.10`, Textual (`textual>=0.80.0`), Rich, Pillow, headless `mpv` controlled via JSON-IPC (`src/bard/audio_player.py`), running primarily in Windows Terminal (`UTF-8`, 24-bit TrueColor).
- **Audio Backend (`mpv` IPC):** `mpv` does not expose raw PCM/FFT bins over JSON-IPC, so the spectrum visualizer must be simulated using playback state (`is_playing`), time progression, and smoothed procedural harmonics. However, `mpv` *does* support `audio-codec-name`, `audio-params/samplerate`, `audio-device-list`, and `audio-device` over JSON-IPC.
- **Data Model (`Track`):** `src/bard/models.py` provides `id`, `title`, `artist`, `album`, `duration_seconds`, `thumbnail_url`, and `stream_url`. `BardApp` also tracks `current_source` (playlist/category label).
- **Theme Backward Compatibility:** `tests/test_theme.py` asserts exact hex values on `arcane_theme.load_theme()["palette"]` (`#13141C`, `#181A24`, `#FF7A00`). Therefore, `arcane_theme.DEFAULT_THEME` must remain intact while Bard's new Obsidian & Ember tokens live as dedicated UI constants / TCSS tokens in the Bard UI layer.

---

## 4. Chosen Approach

**Approach A: Modularize the v2 Layout Inside `ZenStage` (Preserving `BardApp.stage_widget` Interface)**

We considered:
1. **Approach A (Chosen):** Keep `ZenStage` (`src/bard/ui/zen_stage.py`) as `BardApp.stage_widget` with its existing callback signature (`on_prev`, `on_play_pause`, `on_next`, `on_shuffle`, `on_repeat`, `on_seek`, `on_volume`, `on_mute`) and public methods (`update_playback`, `update_track`, `update_progress`, `update_volume`, `set_shuffle`, `set_repeat`, `set_device_name`, `refresh_stage`), extended cleanly with queue & output-device hooks. Replace `ZenStage`'s internal compose tree with clean, focused sub-widgets.
2. **Approach B (Rejected):** Create a parallel `ObservatoryStage` alongside `ZenStage`. Rejected because it leaves unused legacy stage code behind and doubles maintenance.
3. **Approach C (Rejected):** Flatten all panels directly into `BardApp.compose()`. Rejected because it breaks the `stage_widget` encapsulation relied on by `BardApp` and existing tests.

---

## 5. Detailed Design

### 5.1 Color Tokens ("Obsidian & Ember")
Scoped in Bard's UI layer (e.g., `src/bard/ui/palette.py` or `zen_stage.py` + `app.py` CSS) without mutating `arcane_theme.DEFAULT_THEME`:

| Token | Hex | Role |
| :--- | :--- | :--- |
| `BG_OBSIDIAN` | `#0D0E11` | Primary screen canvas & spectrum well |
| `BG_PANEL` | `#14161A` | Column/card surface fill |
| `BG_ELEVATED` | `#1B1E24` | Button resting surface, active controls background |
| `BG_CURSOR` | `#232832` | Keyboard-selected queue row highlight |
| `BORDER_SLATE` | `#2C323D` | Inactive panel borders (`╭─╮│╰─╯`) |
| `BORDER_AMBER` | `#FF7B00` | Focused/active borders (`╔═╗║╚═╝`) & active button accents |
| `TEXT_MUTED` | `#6E7787` | Secondary labels, inactive timestamps, keybinding hints |
| `TEXT_MAIN` | `#D4D9E3` | Track titles, artist names, active UI text |
| `AMBER_DEEP` | `#8F3900` | Spectrum base rows (`0..1`) |
| `AMBER_CORE` | `#FF7B00` | Spectrum mid-low (`2..4`), progress bar body, `/` prefix |
| `AMBER_FLOW` / `GLOW` | `#FF9E2C` | Spectrum mid-high (`5..7`), panel headers |
| `AMBER_PEAK` | `#FFD28A` | Spectrum peak caps (top 2 rows), active track title |

### 5.2 Top Chrome: `ArcaneHeader`
- Keep `ArcaneHeader` (`src/bard/ui/header.py`) docked at the top (`height: 2`, `margin-bottom: 0`) restyled to `#0D0E11` canvas background and Obsidian & Ember accents while preserving its title `"BARD"`, tagline `"Arcane Music Player"`, version, and live playback/source badges (`Playing`/`Paused`, active device/source). Remove the hardcoded `"320 kbps"` badge (and update `tests/test_ui_header.py` accordingly) so no fabricated telemetry appears.

### 5.3 Top Visualization Deck (`SpectrumDeck` + `SeekBar`)
- **Container:** Full-width (`100%`) bordered deck (`╔══[ BARD // CENTER-OUTWARD HARMONIC SPECTRUM ] ... STATE: ● RESONATING / ○ STANDBY ══╗`) with `#FF7B00` border when playing and `#2C323D` when paused/idle.
- **Play-State Gating:**
  - `isPlaying == false` (paused, stopped, or no track): Clear bars completely and render a centered dormant banner:
    ```text
    ─── ◈ STANDBY · AWAITING RESONANCE ◈ ───
    PRESS [SPACE] OR CLICK [▶ PLAY] TO IGNITE SPECTRAL TELEMETRY
    ```
  - `isPlaying == true`: Render a smooth, simulated center-outward spectrum updated on an animation interval (e.g. `~15–20 FPS` / `0.06s`), with zero residual noise when paused.
- **Center-Outward Mirroring:**
  - Generate `N = 28` normalized half-spectrum magnitudes `[0.0, 1.0]` (`0` = sub-bass `60Hz` at center, `N-1` = `16kHz` outer wing) using multi-sine harmonic envelopes + smooth temporal attack/decay damping (plus subtle responsive width scaling if terminal width `< 68`).
  - Mirror via `fullLevels = reverse(halfLevels) + halfLevels` (`56` columns centered in the well).
  - Render `R` character rows (`R = 8`–`10` standard, `R = 6`–`7` compact terminals) using `[' ', '▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']` with row gradient:
    - `r >= R - 2`: `#FFD28A`
    - `r >= R - 5`: `#FF9E2C`
    - `r >= 2`: `#FF7B00`
    - `r < 2`: `#8F3900`
  - Frequency axis baseline row beneath bars: `16kHz ... 4kHz ... ◈ 60Hz SUB-CORE ◈ ... 4kHz ... 16kHz`.
- **Full-Width Scrubber (`SeekBar`):**
  - Spans 100% of the deck's inner width (`[ elapsed_time ] [ 100% flex-fill scrubber ] [ total_duration ]`).
  - Clickable (and supports drag/click seeking via `seekRatio = clamp((x - barLeft) / barWidth, 0.0, 1.0)`) wired to `on_seek`.

### 5.4 Bottom Three-Column Command Deck (`1fr` / `1fr` / `1fr`)
Always rendered (even when no track is loaded, showing the `render_sigil_art` placeholder / empty state prompt).

1. **Left Column — Cover Art & Metadata (`ArtifactPanel`):**
   - Header: `╭─ ARTIFACT COVER ── 01/05 ─╮` (shows active `current_index + 1 / len(queue)` or `--/--` when empty).
   - **Artwork:** Uses `art.py` full-color 2×3 Unicode sextant rendering (`render_album_art`) sized proportionally to the left column width/height, framed cleanly inside `#FF7B00` double-line or `frame_art_ansi` border; falls back to `render_sigil_art` when no URL or no track is loaded.
   - **Metadata Block (below divider):**
     - Line 1: Deterministic arcane rune (`ᛟ`, `ᛉ`, `☉`, `ᛗ`, `ᛜ` hashed from track ID, or `ᛟ` in empty state) + Track Title in `#FFD28A` bold (with marquee scrolling if longer than column width). Empty state displays `"Select Music"` + `"Press [Tab] to explore"`.
     - Line 2: Artist Name in `#D4D9E3`.
     - Line 3: Album Title (if present) or Playlist Source in `#6E7787`.
     - Line 4: Real stream badge from `mpv` IPC when available (e.g. `[OPUS · 48kHz]`) and/or `[YOUTUBE MUSIC]` source pill. **No fake BPM or Year.**

2. **Center Column — Live-Filterable Active Queue (`QueuePanel`):**
   - Header: `╭─ PLAYLIST QUEUE ── [J/K]+[ENTER] ─╮`.
   - **Live Filter Bar:** Compact `/ filter...` `Input` with `#FF7B00` `/` prefix. Typing filters `BardApp.queue` in real time by `title` or `artist` (case-insensitive).
   - **Two-Step Filter Blur/Clear Workflow:** First `Esc` (or `Enter`) while the filter `Input` is focused blurs the input and returns focus to the stage while **keeping** the active filter applied so `J`/`K`/`Enter` can navigate and play from the filtered results. A second `Esc` when the drawer is closed and the filter is not focused clears the filter text.
   - **Queue List:** Renders each track (`NN  Title  mm:ss`).
     - **Active playing track:** Amber-tinted highlight (`#2B1A0D` / `#FF7B00` accent), `▶` prefix, `#FFD28A` title & duration.
     - **Keyboard cursor row (`selectedQueueIndex`):** Elevated slate highlight (`#232832`) with `>` prefix.
     - Clicking a row selects and plays it; pressing `J`/`K` (or `↓`/`↑` when queue focused) moves `selectedQueueIndex`; pressing `Enter` plays `selectedQueueIndex`.
   - **Footer line inside column:** `ARCHIVE: X/Y TRACKS` on left, `SEL: NN` on right.
   - **Synchronization:** `BardApp` pushes `set_queue(self.queue, self.current_index)` whenever a drawer track starts, shuffle toggles, or track advances.

3. **Right Column — Media Controls, Volume & Output Route (`ControlsPanel`):**
   - Header: `╭─ MEDIA CONTROLS ── AUDIO SINK ─╮`.
   - **Non-Focusable Clickable Transport Widgets (Builder Call):** Transport buttons use non-focusable clickable widgets (e.g., `Widget` with `on_click` and stable IDs `#btn-prev`, `#btn-play`, `#btn-next`, `#btn-shuffle`, `#btn-repeat`) rather than focusable Textual `Button` controls, preventing `Space` from activating individual buttons instead of toggling global playback.
   - **Primary Transport Row (3 equal-width buttons):**
     - `[ |◀ PREV ]` (`#btn-prev`, click -> `on_prev`)
     - `[ ▶ PLAY ]` / `[ ❚❚ PAUSE ]` (`#btn-play`, always highlighted with `#FF7B00` accent; click -> `on_play_pause`)
     - `[ NEXT ▶| ]` (`#btn-next`, click -> `on_next`)
   - **Secondary Mode Row (2 equal-width buttons):**
     - `[ ⇄ SHUF: ON/OFF ]` (`#btn-shuffle`, click -> `on_shuffle`)
     - `[ ↻ LOOP: OFF/ALL/ONE ]` (`#btn-repeat`, preserves 3-state `repeat_mode`; click -> `on_repeat`)
   - **Full-Width Volume Container:**
     - Header row: `[ VOL ]` left, `[M: MUTE]` clickable toggle center, `XX%` right-aligned (shows `MUTED` or `00%` when volume is 0).
     - Full-width interactive horizontal fader bar below header supporting click (and drag) across its width, wired to `on_volume(pct)`.
   - **Output Route Selector:**
     - Interactive clickable box showing `OUTPUT ROUTE` + `[CLICK TO CYCLE]` hint and current sink label (e.g., `◈ WASAPI // Speakers (...)` or `◈ MPV // Auto Default`).
     - Clicking cycles through devices returned by `AudioPlayer.get_audio_devices()` -> `AudioPlayer.set_audio_device(device_id)` (with safe fallback to `Default` if `mpv` has no device list or `player is None`).
   - **Keybind Hint Row:** Compact summary of active bindings (`[TAB] BROWSE [SPACE] PLAY [N/P] TRACK [+/-] VOL`).

### 5.5 Bottom Status Footer (`StatusFooter`)
- 1-line docked bar at the bottom of the screen (`height: 1`, `#0D0E11` / `#14161A`):
  - Left: Truthful environment label (`BARD // UTF-8 • 24-BIT TRUECOLOR`).
  - Right: Dynamic status prompt (`READY // Press [Tab] to explore or [Space] to play`, or active state / stream codec summary).

### 5.6 Keybindings (Non-Breaking Preservation)
- **Existing Global Bindings Preserved in `BardApp.BINDINGS`:**
  - `Space`: Play/Pause (Builder Call: remove `priority=True` or yield when `isinstance(self.focused, Input)` so users can type spaces inside the `/` queue filter and drawer search inputs, while `Space` still toggles playback everywhere else since `ControlsPanel` buttons are non-focusable)
  - `Tab`: Toggle `CurtainDrawer`
  - `Esc`: If queue filter `Input` is focused, blur it while keeping the filter active; else if `CurtainDrawer` is open, close drawer; else if queue filter is non-empty, clear the filter
  - `N`: Next track
  - `P`: Previous track
  - `S`: Toggle shuffle
  - `R`: Cycle repeat (`off` → `all` → `one`)
  - `M`: Toggle mute
  - `+` / `=` / `-`: Volume up / down (5%)
  - `Q`: Quit
- **Additive Stage Bindings (active only when `CurtainDrawer` is closed and queue filter input is not focused):**
  - `j` / `k`: Move `selectedQueueIndex` down / up in queue
  - `enter`: Play track at `selectedQueueIndex`
  - `/`: Focus the queue filter input
  - `left` / `right` (and `h` / `l` only when drawer is closed): Seek `-10s` / `+10s`

### 5.7 Backend Extensions (`AudioPlayer` in `src/bard/audio_player.py`)
Add non-breaking helper methods with safe fallbacks when `mpv` isn't connected:
- `get_audio_info() -> Dict[str, Any]`: Queries `audio-codec-name` and `audio-params/samplerate` over JSON-IPC (returns `{}` on failure).
- `get_audio_devices() -> List[Dict[str, str]]`: Queries `audio-device-list` over JSON-IPC (list of `{"name": ..., "description": ...}`).
- `get_current_audio_device() -> str` & `set_audio_device(name: str) -> bool`: Gets/sets `mpv` `audio-device` property over JSON-IPC.

---

## 6. What's Left to the Builder

- Exact module breakdown inside `src/bard/ui/` (e.g., placing new sub-widgets in `src/bard/ui/stage_widgets.py` or keeping them inside `src/bard/ui/zen_stage.py`).
- Exact procedural wave equation / damping constants for the simulated 28-bin harmonic spectrum.
- Exact responsive layout breakpoints for compact terminals (e.g., `< 90` cols or `< 32` rows) so all 3 columns remain readable without clipping controls.
- Updating `tests/test_ui_stage.py`, updating `tests/test_app.py` transport click tests (lines 534–556 and 705–727) to target `#btn-shuffle`, `#btn-repeat`, `#btn-play`, `#btn-next`, `#btn-prev` instead of legacy `17×4` pixel offsets, and updating `tests/test_ui_header.py` after removing the fake `"320 kbps"` badge — while keeping all other tests in `tests/test_app.py`, `tests/test_theme.py`, and the rest of the suite green.
