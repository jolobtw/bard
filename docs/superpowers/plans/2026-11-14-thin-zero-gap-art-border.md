# Thin Zero-Gap Album Art Border Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Textual's thick `border: inner #FF7A00` (`1/2`-cell) with a crisp `1/8`-cell (~1–2px) Arcane-orange border that touches the album art pixels with zero gap.

**Architecture:** Textual's built-in `border: round` centers a thin stroke inside each border cell (leaving a half-cell gap), while `border: inner` uses `1/2`-cell blocks (`▄`, `▀`, `▐`, `▌`). To get both thinness and zero gap, `src/bard/art.py` will wrap the rendered ANSI art rows in Unicode 1.1 one-eighth block elements (`▁` top, `▔` bottom, `▕` left, `▏` right) colored with `palette["accent_flame"]` (`#FF7A00`) on `palette["canvas_bg"]` (`#13141C`), while `src/bard/ui/zen_stage.py` removes the CSS border on `#art-box` and applies the framed ANSI when updating `#art-box`.

**Tech Stack:** Python 3.12, Textual, Rich (`rich.text.Text.from_ansi`), Unicode Block Elements (`U+2581`, `U+258F`, `U+2594`, `U+2595`), `pytest`.

## Global Constraints

- Preserve `ZenStage._cached_art_ansi` as the unframed `render_album_art()` output so existing responsive-sizing tests (`14` / `20` lines) remain accurate.
- Pull border and background colors from `arcane_theme.py` (`accent_flame` `#FF7A00`, `canvas_bg` `#13141C`) rather than hardcoding unrelated colors.
- Do not introduce playback or click-flicker regressions on `#art-box`.

## Review Focus

- Empty `art_ansi` input to `frame_art_ansi("")` must return `""` without emitting stray border lines.
- Width calculation of `art_ansi` must strip ANSI escape sequences before counting visible columns so the top `▁` and bottom `▔` bars match the exact art width.
- Narrow/compact (`80x24`), hero (`100x40`), and large (`120x48`) art dimensions must all frame cleanly without wrapping or clipping.
- Transitioning from playing to empty state (`update_playback(None)`) must clear `#art-box` completely.
- Existing `pytest` suite (155 tests) must continue to pass.

---

### Task 1: Add `frame_art_ansi()` helper in `src/bard/art.py`

**Files:**
- Modify: `src/bard/art.py`
- Test: `tests/test_art.py`

**Interfaces:**
- Produces: `frame_art_ansi(art_ansi: str, border_hex: str = "#FF7A00", bg_hex: str = "#13141C") -> str`

- [ ] **Step 1: Write the failing test in `tests/test_art.py`**

```python
def test_frame_art_ansi_thin_zero_gap_border():
    from rich.text import Text
    from bard.art import frame_art_ansi

    assert frame_art_ansi("") == ""

    sample = "\x1b[38;2;255;0;0m███\x1b[0m\n\x1b[38;2;0;255;0m███\x1b[0m"
    framed = frame_art_ansi(sample, border_hex="#FF7A00", bg_hex="#13141C")
    lines = framed.split("\n")
    assert len(lines) == 4  # 2 art rows + top + bottom

    plain_lines = [Text.from_ansi(line).plain for line in lines]
    assert plain_lines[0] == " ▁▁▁ "
    assert plain_lines[1] == "▕███▏"
    assert plain_lines[2] == "▕███▏"
    assert plain_lines[3] == " ▔▔▔ "
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/test_art.py::test_frame_art_ansi_thin_zero_gap_border -v`
Expected: FAIL with `ImportError: cannot import name 'frame_art_ansi' from 'bard.art'`

- [ ] **Step 3: Implement `frame_art_ansi` in `src/bard/art.py`**

Strip ANSI escapes using a regex (`\x1b\[[0-9;]*m`) to determine visible `art_width`, convert `border_hex` and `bg_hex` to 24-bit ANSI foreground/background sequences, and wrap the lines with `▁`, `▕`, `▏`, and `▔` (using `bg_hex` space at the four diagonal corners).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest.exe tests/test_art.py -v`
Expected: PASS

---

### Task 2: Wire `frame_art_ansi()` into `ZenStage` and remove CSS `border: inner`

**Files:**
- Modify: `src/bard/ui/zen_stage.py`
- Test: `tests/test_ui_stage.py`

**Interfaces:**
- Consumes: `bard.art.frame_art_ansi`

- [ ] **Step 1: Update `test_zen_stage_visual_refinements_footer_pill_border_and_marquee` in `tests/test_ui_stage.py`**

Verify `#art-box` has no Textual CSS border (`art_box.styles.border_top[0] == "none"` or `""`) and that its rendered `Text` includes the thin `▁`, `▕`, `▏`, `▔` zero-gap border around the art.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/test_ui_stage.py::test_zen_stage_visual_refinements_footer_pill_border_and_marquee -v`
Expected: FAIL (currently uses `border: inner`)

- [ ] **Step 3: Update `src/bard/ui/zen_stage.py`**

- Remove `border: inner #FF7A00;` from `#art-box` CSS (keep `width: auto; height: auto; background: #13141C;`).
- Import `frame_art_ansi` from `bard.art`.
- Apply `frame_art_ansi(self._cached_art_ansi, border_hex=..., bg_hex=...)` using `DEFAULT_THEME["palette"]` (`accent_flame` / `canvas_bg`) in `refresh_stage()` and `on_resize()` when calling `art_widget.update(Text.from_ansi(...))`, keeping `self._cached_art_ansi` unframed.

- [ ] **Step 4: Run full `pytest` suite and commit/push**

Run: `.venv\Scripts\pytest.exe`
Expected: All tests pass, then commit and push to `origin/main`.
