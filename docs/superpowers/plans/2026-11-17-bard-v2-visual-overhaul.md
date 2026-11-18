# Bard v2 Visual Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overhaul Bard's main Textual UI into the "Obsidian & Ember" two-tier layout (simulated play-state-gated center-outward spectrum + full-width scrubber over a 3-column Art/Queue/Controls deck + truthful status footer) while keeping all existing playback, YouTube Music browsing, OAuth, and keybindings intact.

**Architecture:** Refactor inside `ZenStage` (`src/bard/ui/zen_stage.py`) as the single `BardApp.stage_widget` boundary, backed by focused UI modules (`palette.py`, `spectrum.py`, `stage_widgets.py`), truthful `mpv` JSON-IPC codec/device helpers in `AudioPlayer`, and non-breaking `BardApp` queue/keybind orchestration. `CurtainDrawer` (`[Tab]`) and `arcane_theme.py` stay functionally unchanged.

**Tech Stack:** Python `>=3.10`, Textual (`>=0.80.0`), Rich, Pillow, headless `mpv` JSON-IPC, pytest.

**Spec:** [docs/superpowers/specs/2026-11-17-bard-v2-visual-overhaul-design.md](file:///C:/Users/josep/tools/bard/docs/superpowers/specs/2026-11-17-bard-v2-visual-overhaul-design.md)

## Global Constraints

- Application stays titled **Bard**; discard all "Observatory" branding/references.
- Scope Obsidian & Ember palette (`#0D0E11`, `#14161A`, `#1B1E24`, `#232832`, `#2C323D`, `#FF7B00`, `#6E7787`, `#D4D9E3`, `#8F3900`, `#FF9E2C`, `#FFD28A`) in Bard's UI layer without modifying `src/bard/arcane_theme.py` (`tests/test_theme.py` must stay green).
- No fabricated telemetry: no hardcoded `/dev/pts/0`, no fake `"320 kbps"`, no fake `[FLAC · 24-BIT/96kHz]`, no fake BPM/Year, no fake DAC names.
- Preserve all existing global keybinds (`Space`, `Tab`, `Esc`, `N`, `P`, `S`, `R`, `M`, `+`, `=`, `-`, `Q`) and 3-state repeat (`off` → `all` → `one`).
- Simulated spectrum only (no OS audio loopback dependencies); strictly play-state-gated (`is_playing == False` shows only the standby banner).
- Use non-focusable clickable transport widgets (`#btn-prev`, `#btn-play`, `#btn-next`, `#btn-shuffle`, `#btn-repeat`) and yield `Space` when an `Input` is focused.
- Two-step `Esc` on queue filter: first `Esc` (or `Enter`) blurs filter keeping query active; second `Esc` when drawer is closed and filter unfocused clears query.

## Review Focus

- Typing spaces or global shortcut keys (`j`, `k`, `n`, `p`, `s`, `r`, `m`, `q`, `/`) inside `#queue-filter` `Input` must insert text cleanly without triggering player actions.
- Clicking or dragging past `SeekBar` / `VolumeBar` edges (`x < 0` or `x >= width`) must clamp cleanly to `[0.0, 1.0]` / `[0, 100]`.
- Filtering the queue to zero matches must show `ARCHIVE: 0/N TRACKS` and `SEL: --`, and ignore `J`/`K`/`Enter` without `IndexError`.
- Compact terminal sizes (e.g., `80×24`) must render spectrum, 3 columns, and footer without negative widths or zero-division errors.
- Rapid Play → Pause → Unmount must immediately switch spectrum to the standby banner and stop interval timers without errors.

---

## File Structure

- `src/bard/audio_player.py` (Modify): Add `get_audio_info()`, `get_audio_devices()`, `get_current_audio_device()`, `set_audio_device(name)`.
- `src/bard/ui/palette.py` (Create): Obsidian & Ember color tokens and deterministic `track_rune(track_id)`.
- `src/bard/ui/spectrum.py` (Create): Simulated 28-bin center-outward spectrum generator/renderer (`SpectrumDeck`) + full-width `SeekBar`.
- `src/bard/ui/stage_widgets.py` (Create): `ArtifactPanel`, `QueuePanel`, `ControlsPanel`, `VolumeBar`, and `StatusFooter`.
- `src/bard/ui/header.py` (Modify): Restyle to Obsidian & Ember and remove hardcoded `"320 kbps"` badge.
- `src/bard/ui/zen_stage.py` (Modify): Compose top `SpectrumDeck`, 3-column lower deck (`ArtifactPanel`, `QueuePanel`, `ControlsPanel`), and `StatusFooter` while preserving public `ZenStage` interface.
- `src/bard/ui/app.py` (Modify): Update canvas CSS to `#0D0E11`, sync queue/audio info/output device with `ZenStage`, refine `Space`/`Esc` and stage-only `j`/`k`/`enter`/`/`/`left`/`right`/`h`/`l` key routing.
- `tests/test_audio_player.py`, `tests/test_ui_spectrum.py`, `tests/test_ui_stage_widgets.py`, `tests/test_ui_header.py`, `tests/test_ui_stage.py`, `tests/test_app.py`: Unit & integration tests covering every new and updated behavior.

---

### Task 1: `AudioPlayer` IPC Telemetry & Output Device Methods

**Files:**
- Modify: `src/bard/audio_player.py:290-320`
- Test: `tests/test_audio_player.py`

**Interfaces:**
- Produces:
  - `AudioPlayer.get_audio_info() -> Dict[str, Any]` (`{"codec": str, "samplerate": int}` when available, else `{}`)
  - `AudioPlayer.get_audio_devices() -> List[Dict[str, str]]` (`[{"name": str, "description": str}, ...]`)
  - `AudioPlayer.get_current_audio_device() -> str`
  - `AudioPlayer.set_audio_device(device_name: str) -> bool`

- [ ] **Step 1: Write failing tests in `tests/test_audio_player.py`**

Add tests `test_player_audio_info_and_devices()` and `test_player_audio_info_safe_defaults_when_disconnected()` asserting:
- `get_audio_info()` queries `["get_property", "audio-codec-name"]` and `["get_property", "audio-params/samplerate"]` and returns `{"codec": "opus", "samplerate": 48000}`.
- `get_audio_devices()` queries `["get_property", "audio-device-list"]` and returns filtered `[{"name": ..., "description": ...}]`.
- `get_current_audio_device()` queries `["get_property", "audio-device"]`.
- `set_audio_device("wasapi/{abc}")` sends `["set_property", "audio-device", "wasapi/{abc}"]` and returns `True` on `error == "success"`, `False` otherwise.
- Dead/disconnected player returns `{}`, `[]`, `""`, and `False`.

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_audio_player.py -k "audio_info" -v`
Expected: FAIL with `AttributeError: 'AudioPlayer' object has no attribute 'get_audio_info'`.

- [ ] **Step 3: Implement IPC helper methods in `src/bard/audio_player.py`**

Implement `get_audio_info`, `get_audio_devices`, `get_current_audio_device`, and `set_audio_device` using `self._send_command(...)` with `Optional`/`Dict`/`List` typing and safe fallbacks when `self._process` is dead or `resp` is `None`/error.

- [ ] **Step 4: Run `tests/test_audio_player.py`**

Run: `pytest tests/test_audio_player.py -v`
Expected: PASS (all existing + new tests green).

- [ ] **Step 5: Commit**

```bash
git add src/bard/audio_player.py tests/test_audio_player.py
git commit -m "feat: add mpv audio info and output device IPC helpers"
```

---

### Task 2: Obsidian & Ember Palette + Simulated Center-Outward Spectrum & Scrubber

**Files:**
- Create: `src/bard/ui/palette.py`
- Create: `src/bard/ui/spectrum.py`
- Test: `tests/test_ui_spectrum.py`

**Interfaces:**
- Produces (`src/bard/ui/palette.py`):
  - `BG_OBSIDIAN`, `BG_PANEL`, `BG_ELEVATED`, `BG_CURSOR`, `BORDER_SLATE`, `BORDER_AMBER`, `TEXT_MUTED`, `TEXT_MAIN`, `AMBER_DEEP`, `AMBER_CORE`, `AMBER_GLOW`, `AMBER_PEAK`
  - `RUNES = ("ᛟ", "ᛉ", "☉", "ᛗ", "ᛜ")`
  - `track_rune(track_id: str) -> str`
- Produces (`src/bard/ui/spectrum.py`):
  - `generate_simulated_bins(phase: float, n_bins: int = 28, prev_bins: Optional[Sequence[float]] = None) -> List[float]`
  - `mirror_spectrum_bins(half_levels: Sequence[float]) -> List[float]`
  - `render_spectrum_lines(half_levels: Sequence[float], rows: int = 8) -> List[str]`
  - `SeekBar(Widget)` with `set_progress(progress_ms: int, duration_ms: int)`, `on_seek: Optional[Callable[[float], None]]`, full-width `[ mm:ss ] [ bar ] [ mm:ss ]`, mouse click/drag clamping to `[0.0, 1.0]`.
  - `SpectrumDeck(Widget)` with `set_state(is_playing: bool, has_track: bool, progress_ms: int, duration_ms: int)`, `set_playing(is_playing: bool)`, `set_progress(progress_ms: int, duration_ms: int)`, `#progress-bar` (`SeekBar`).

- [ ] **Step 1: Write failing tests in `tests/test_ui_spectrum.py`**

Cover:
- `palette.track_rune("abc")` is deterministic and in `RUNES`, `track_rune("") == "ᛟ"`.
- `mirror_spectrum_bins([0.9, 0.4, 0.1]) == [0.1, 0.4, 0.9, 0.9, 0.4, 0.1]`.
- `generate_simulated_bins(0.5, n_bins=28)` returns 28 floats in `[0.0, 1.0]` with center (`[0]`) biased higher than outer wing (`[-1]`) on average across phases.
- `render_spectrum_lines([1.0, 0.5], rows=8)` outputs 8 lines using block characters `▁▂▃▄▅▆▇█` and `#FFD28A`/`#8F3900` row colors.
- `SpectrumDeck` mounted in Textual: when `is_playing=False`, renders `"STANDBY · AWAITING RESONANCE"` and zero spectrum bars; when `is_playing=True`, renders `"RESONATING"` and `"60Hz SUB-CORE"` without standby banner; rapid `True -> False` clears immediately; unmount stops timer cleanly; `SeekBar` click/drag clamps `x < 0` and `x >= width` to `[0.0, duration_sec]`.

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_ui_spectrum.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bard.ui.palette'`.

- [ ] **Step 3: Implement `src/bard/ui/palette.py` and `src/bard/ui/spectrum.py`**

Create `palette.py` with exact hex constants and `track_rune`. Create `spectrum.py` with the center-outward mirroring algorithm, 8-step vertical blocks, row-gradient Rich/ANSI formatting, play-state-gated `SpectrumDeck`, `0.06s` animation timer active only while `is_playing`, and full-width `SeekBar` supporting click and mouse-drag seeking with clamped bounds.

- [ ] **Step 4: Run `tests/test_ui_spectrum.py` and `tests/test_theme.py`**

Run: `pytest tests/test_ui_spectrum.py tests/test_theme.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bard/ui/palette.py src/bard/ui/spectrum.py tests/test_ui_spectrum.py
git commit -m "feat: add Obsidian & Ember palette and simulated center-outward spectrum"
```

---

### Task 3: Bottom Command Deck Sub-Widgets (`ArtifactPanel`, `QueuePanel`, `ControlsPanel`, `StatusFooter`)

**Files:**
- Create: `src/bard/ui/stage_widgets.py`
- Test: `tests/test_ui_stage_widgets.py`

**Interfaces:**
- Consumes: `bard.ui.palette`, `bard.art` (`render_album_art`, `frame_art_ansi`), `bard.models.Track`
- Produces (`src/bard/ui/stage_widgets.py`):
  - `ArtifactPanel(Widget)`:
    - `set_track(playback_data: Optional[Dict[str, Any]], queue_pos: Tuple[int, int] = (0, 0), audio_info: Optional[Dict[str, Any]] = None)`
    - `get_art_dimensions(avail_width: int, avail_height: int) -> Tuple[int, int]`
    - Exposes `#art-box`, `#track-title`, `#track-meta`, `#track-source`, `#track-codec`.
  - `QueuePanel(Widget)`:
    - `set_queue(tracks: Sequence[Track], current_index: int)`
    - `move_cursor(delta: int) -> None`
    - `selected_original_index() -> Optional[int]`
    - `focus_filter() -> None`
    - `blur_filter(clear: bool = False) -> None`
    - `clear_filter() -> None`
    - `has_filter_focus() -> bool`
    - `has_filter_text() -> bool`
    - Exposes `#queue-filter` (`Input`), `#queue-list`, `#queue-footer`, callback `on_select_index: Optional[Callable[[int], None]]`.
  - `ControlsPanel(Widget)`:
    - Non-focusable clickable buttons: `#btn-prev`, `#btn-play`, `#btn-next`, `#btn-shuffle`, `#btn-repeat`, `#volume-control` (`VolumeBar`), `#output-route`
    - `set_state(is_playing: bool, has_track: bool, shuffle_enabled: bool, repeat_mode: str, volume: int, device_name: str)`
  - `StatusFooter(Widget)`:
    - `set_status(text: str)`

- [ ] **Step 1: Write failing tests in `tests/test_ui_stage_widgets.py`**

Cover:
- `ArtifactPanel`: empty state shows `"Select Music"`, `"Press [Tab] to explore"`, sigil art; active track shows rune + title, artist, album, real codec badge `"[OPUS · 48kHz]"` when `audio_info={"codec": "opus", "samplerate": 48000}` and omits codec badge when empty (no fake FLAC/BPM); marquee advances on long titles.
- `QueuePanel`: `set_queue` renders tracks; typing `"obelisk"` in `#queue-filter` filters case-insensitively (`ARCHIVE: 1/3 TRACKS`), typing gibberish shows `ARCHIVE: 0/3 TRACKS` and `SEL: --` and `move_cursor(1)` / `selected_original_index()` safely returns `None` without raising; `blur_filter(clear=False)` retains filter text so `move_cursor` + `selected_original_index()` maps back to the real `BardApp.queue` index; `clear_filter()` restores full list; clicking a row invokes `on_select_index(real_idx)`.
- `ControlsPanel`: buttons `#btn-prev`, `#btn-play`, `#btn-next`, `#btn-shuffle`, `#btn-repeat` are non-focusable (`can_focus == False`), show `OFF` / `ALL` / `ONE` repeat labels, invoke callbacks on click; `VolumeBar` click & drag clamp to `0..100` and mute toggle works; `#output-route` click invokes `on_cycle_device`.
- `StatusFooter`: displays `"BARD // UTF-8 • 24-BIT TRUECOLOR"` and status text without `/dev/pts/0`.

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_ui_stage_widgets.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bard.ui.stage_widgets'`.

- [ ] **Step 3: Implement `src/bard/ui/stage_widgets.py`**

Implement `ArtifactPanel`, `QueuePanel`, `VolumeBar`, `ControlsPanel`, and `StatusFooter` using `palette.py` Obsidian & Ember colors, double-line / slate-rounded panels, marquee timer in `ArtifactPanel`, mouse click+drag on `VolumeBar`, and clean `QueuePanel` index mapping (`_filtered_entries: List[Tuple[int, Track]]`).

- [ ] **Step 4: Run `tests/test_ui_stage_widgets.py`**

Run: `pytest tests/test_ui_stage_widgets.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bard/ui/stage_widgets.py tests/test_ui_stage_widgets.py
git commit -m "feat: add ArtifactPanel, QueuePanel, ControlsPanel, and StatusFooter widgets"
```

---

### Task 4: Refactor `ArcaneHeader` & `ZenStage` to Two-Tier Layout

**Files:**
- Modify: `src/bard/ui/header.py`
- Modify: `src/bard/ui/zen_stage.py`
- Modify: `tests/test_ui_header.py`
- Modify: `tests/test_ui_stage.py`

**Interfaces:**
- Consumes: `bard.ui.palette`, `bard.ui.spectrum.SpectrumDeck`, `bard.ui.stage_widgets` (`ArtifactPanel`, `QueuePanel`, `ControlsPanel`, `StatusFooter`)
- Produces (`ZenStage`):
  - Constructor keeps existing params + optional `on_select_queue_index: Optional[Callable[[int], None]] = None`, `on_cycle_device: Optional[Callable[[], None]] = None`.
  - Preserves `update_playback`, `update_track`, `update_progress`, `update_volume`, `set_shuffle`, `set_repeat`, `set_device_name`, `refresh_stage`, `get_art_dimensions`, `playback_data`, `shuffle_enabled`, `repeat_mode`.
  - Adds `set_queue(tracks: Sequence[Track], current_index: int)`, `set_audio_info(info: Dict[str, Any])`, `set_audio_device(label: str)`, `move_queue_cursor(delta: int)`, `get_selected_queue_index() -> Optional[int]`, `focus_queue_filter()`, `blur_queue_filter(clear: bool = False)`, `clear_queue_filter()`, `is_queue_filter_focused() -> bool`, `has_queue_filter_text() -> bool`.

- [ ] **Step 1: Update `tests/test_ui_header.py` and `tests/test_ui_stage.py` for the new spec**

- In `tests/test_ui_header.py`: assert `"BARD"`, `"v0.2.0"`, `"Arcane Music Player"`, `"Playing"`, and assert `"320 kbps"` is NOT in `plain`.
- In `tests/test_ui_stage.py`: keep `format_ms` / `render_flame_progress` / `render_arcane_bar` helper tests if exported or imported from `spectrum.py`, and update widget layout assertions to verify:
  - Empty state keeps 3 columns mounted with `"Select Music"`, `"Press [Tab] to explore"`, and `"STANDBY · AWAITING RESONANCE"` in `SpectrumDeck`.
  - Playing state activates `"RESONATING"`, updates `ArtifactPanel`, `QueuePanel`, `ControlsPanel`, `SeekBar`, and `StatusFooter`.
  - Responsive sizing at `(80, 24)`, `(100, 40)`, `(120, 48)` renders cleanly without exceptions or negative dimensions.
  - Clicking `#btn-prev`, `#btn-play`, `#btn-next`, `#btn-shuffle`, `#btn-repeat`, `#volume-control`, `#progress-bar`, and `#output-route` invokes all callbacks.

- [ ] **Step 2: Run updated tests to verify they fail before refactoring**

Run: `pytest tests/test_ui_header.py tests/test_ui_stage.py -v`
Expected: FAIL (header still emits `"320 kbps"`, `ZenStage` still uses legacy `#transport-controls` / hides `#art-center`).

- [ ] **Step 3: Implement `ArcaneHeader` update and `ZenStage` refactor**

- Update `src/bard/ui/header.py`: Obsidian `#0D0E11` background, remove `"320 kbps"` badge, keep `BARD`, tagline, version, device badge, and Play/Pause badge.
- Refactor `src/bard/ui/zen_stage.py`: compose `SpectrumDeck` (top) + `Horizontal(id="command-deck")` containing `ArtifactPanel`, `QueuePanel`, `ControlsPanel` (bottom 3 equal `1fr` columns) + `StatusFooter`. Delegate state updates cleanly and preserve helper exports (`format_ms`, `render_arcane_bar`, `render_flame_progress`) for compatibility.

- [ ] **Step 4: Run `tests/test_ui_header.py` and `tests/test_ui_stage.py`**

Run: `pytest tests/test_ui_header.py tests/test_ui_stage.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bard/ui/header.py src/bard/ui/zen_stage.py tests/test_ui_header.py tests/test_ui_stage.py
git commit -m "feat: overhaul ArcaneHeader and ZenStage into Obsidian & Ember layout"
```

---

### Task 5: Wire `BardApp` Queue, Keybindings, `mpv` Info & Output Device Cycling

**Files:**
- Modify: `src/bard/ui/app.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `ZenStage` new methods (`set_queue`, `set_audio_info`, `set_audio_device`, queue filter helpers, `on_select_queue_index`, `on_cycle_device`), `AudioPlayer` (`get_audio_info`, `get_audio_devices`, `get_current_audio_device`, `set_audio_device`).

- [ ] **Step 1: Update `tests/test_app.py` transport click tests & add integration tests**

- Update `test_app_transport_buttons_clickable_in_app` (lines 533–558 and 704–728) to click `#btn-shuffle`, `#btn-repeat`, `#btn-play`, `#btn-next`, `#btn-prev`.
- Add tests for:
  - Queue synchronization: `handle_drawer_play` & `action_toggle_shuffle` sync `stage_widget` queue.
  - Stage keybinds when drawer closed: `j`/`k`/`enter` navigate and play from queue; `/` focuses `#queue-filter`; typing `"track 2"` (with a space!) filters queue without triggering play/pause; first `escape` blurs keeping filter so `enter` plays filtered item; second `escape` clears filter.
  - Preserved `n`, `p`, `s`, `r`, `m`, `+`, `-`, `tab`, `q` bindings when not typing in `Input`.
  - `action_cycle_output_device` cycles `player.get_audio_devices()` and calls `player.set_audio_device(...)`.

- [ ] **Step 2: Run `tests/test_app.py` to verify failures**

Run: `pytest tests/test_app.py -v`
Expected: FAIL on updated transport IDs and new queue/keybind/device tests.

- [ ] **Step 3: Update `src/bard/ui/app.py`**

- Set `Screen { background: #0D0E11; }`.
- Remove `priority=True` on `space` and `escape` (or guard `action_toggle_playback` / `action_close_drawer` via `on_key` + `Input` focus check so typing spaces in `#queue-filter` or `#search-input` always inserts a space, while `Space` toggles playback whenever no `Input` is focused).
- Implement two-step `Esc` handling, `j`/`k`/`enter`/`/`/`left`/`right`/`h`/`l` routing when `not self.drawer_widget.is_open()` and not typing in an `Input`.
- Pass `on_select_queue_index=self.play_track_at_index` and `on_cycle_device=self.action_cycle_output_device` to `ZenStage`.
- Sync `self.stage_widget.set_queue(self.queue, self.current_index)` whenever queue or `current_index` changes, and refresh `audio_info` + current output device on track start and `sync_playback_state`.

- [ ] **Step 4: Run full test suite**

Run: `pytest -v`
Expected: All tests pass (0 failures).

- [ ] **Step 5: Commit**

```bash
git add src/bard/ui/app.py tests/test_app.py
git commit -m "feat: wire BardApp queue sync, key routing, and mpv device cycling"
```
