# Arcane Empty State & Non-Blocking Drawer Loading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide an atmospheric Arcane musical sigil empty state in Zen Stage and an instantly opening Curtain Drawer with background loading feedback for playlists and tracklists.

**Architecture:** 
1. Render a TrueColor ANSI musical sigil emblem in `art.py` and hook it into `ZenStage`'s empty-playback state with evocative typography.
2. Refactor `CurtainDrawer` to open immediately upon `toggle()` and offload `get_playlists` and `get_playlist_tracks` to background workers with loading placeholder options in the OptionLists.

**Tech Stack:** Python 3.12, Textual 6.x, Rich, Pillow, Pytest.

**Spec:** `docs/superpowers/specs/2026-11-01-empty-state-and-drawer-loading.md`

## Global Constraints
- Must adhere to the Arcane Theme color tokens: `#13141C` (canvas), `#181A24` (surface), `#FF7A00` (accent flame), `#FFD166` (gold), `#A6ADC8` (subtext), `#2E3244` (border).
- Must preserve all existing tests and key bindings.
- All code changes must be auto-pushed to GitHub upon completion.

## Review Focus
1. `ZenStage` must not crash or misalign when terminal width is resized or when transitioning between empty state and active playback.
2. Rapidly pressing `[Tab]` to open/close the drawer while a background fetch is running must not crash or leave dangling threads.
3. Rapidly pressing arrow keys through playlists while tracklists are fetching must cancel or supersede previous pending track fetches gracefully.
4. Sigil rendering must fallback gracefully without throwing encoding or character-set exceptions across platforms.

---

### Task 1: Arcane Sigil Artwork & ZenStage Empty State

**Files:**
- Modify: `src/bard/art.py`
- Modify: `src/bard/ui/zen_stage.py`
- Test: `tests/test_art.py`
- Test: `tests/test_ui_stage.py`

- [ ] **Step 1: Write failing tests for `render_sigil_art` in `tests/test_art.py`**
  Verify that `render_sigil_art()` returns non-empty ANSI string containing rune glyphs (`✦`, `◈`, `◇`, `♫`) and correct dimensions.
- [ ] **Step 2: Run tests to confirm failure**
  Run `pytest tests/test_art.py`.
- [ ] **Step 3: Implement `render_sigil_art` in `src/bard/art.py`**
  Implement `render_sigil_art(width=32, height=12) -> str` using 24-bit TrueColor ANSI styling and arcane geometric runes.
- [ ] **Step 4: Update `ZenStage` empty state in `src/bard/ui/zen_stage.py`**
  When `playback_data` is None, render the sigil via `render_sigil_art`, show title `THE STAGE IS SILENT`, and display the updated prompt.
- [ ] **Step 5: Add tests for `ZenStage` empty state in `tests/test_ui_stage.py`**
  Verify empty state elements and labels.
- [ ] **Step 6: Run tests to confirm passing**
  Run `pytest tests/test_art.py tests/test_ui_stage.py`.
- [ ] **Step 7: Commit and push Task 1 to GitHub**
  Commit changes with descriptive message and push.

---

### Task 2: Instant Curtain Drawer with Non-Blocking Background Loading

**Files:**
- Modify: `src/bard/ui/curtain_drawer.py`
- Test: `tests/test_ui_drawer.py`

- [ ] **Step 1: Write failing tests for instant drawer open and loading state in `tests/test_ui_drawer.py`**
  Test that `drawer.toggle()` makes drawer visible immediately and shows loading indicators before playlists resolve.
- [ ] **Step 2: Run tests to confirm failure**
  Run `pytest tests/test_ui_drawer.py`.
- [ ] **Step 3: Refactor `CurtainDrawer` in `src/bard/ui/curtain_drawer.py`**
  - In `toggle()`: immediately add `-visible` class, focus playlist list, and start background load worker `@work(thread=True)`.
  - While loading playlists, show `Option(Text("  ✦ Deciphering playlists..."))` with distinct styling.
  - In `load_tracks_for_playlist()`: show `Option(Text("  ✦ Reading tracklist..."))` and offload fetch to a background worker `@work(thread=True, exclusive=True)`.
  - Safely post results back to the OptionList via `self.call_from_thread`.
- [ ] **Step 4: Run tests to confirm passing**
  Run `pytest tests/test_ui_drawer.py`.
- [ ] **Step 5: Run full test suite**
  Run `pytest` to ensure all tests pass.
- [ ] **Step 6: Commit and push Task 2 to GitHub**
  Commit changes and push to GitHub.
