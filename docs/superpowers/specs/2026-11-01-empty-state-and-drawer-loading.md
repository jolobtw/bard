# Design Spec: Arcane Empty State & Non-Blocking Drawer Loading

**Date:** 2026-11-01  
**Author:** Antigravity & User  
**Status:** In Review  

---

### 1. Problem Statement & "Why"
1. **Empty State Experience:** When no music is playing, Bard currently falls back to a stark gray `[ NO ARTWORK ]` block and simple text. The user wants a beautiful, atmospheric empty state featuring an **Arcane musical sigil / rune** to match the mystical aesthetic of the player.
2. **Drawer Responsiveness:** When pressing `[Tab]`, there is a noticeable lag while playlists are fetched synchronously before the drawer opens. The drawer should open **instantly**, with an Arcane loading animation / indicator displayed while playlists and tracks are fetched in the background.

---

### 2. Design & Behavior Details

#### A. Arcane Musical Sigil Empty State
* **Sigil Artwork (`src/bard/art.py`):**
  * Create `render_sigil_art(width=32, height=12) -> str` using 24-bit TrueColor ANSI styling and arcane geometric runes:
    ```text
               ✦  ◈  ✦
            ╭─◇─  ♫  ─◇─╮
           │   ( ( ◈ ) )   │
            ╰─◇─  ♫  ─◇─╯
               ✦  ◈  ✦
    ```
    rendered with ember gradient tones (`#FF4500` -> `#FF7A00` -> `#FFD166`).
* **Stage Display (`src/bard/ui/zen_stage.py`):**
  * Artwork center displays the sigil.
  * Title: `[bold #FF7A00]THE STAGE IS SILENT[/]`
  * Subtitle / Meta: `[#A6ADC8]Summon your library with [/][bold #FFD166][Tab][/][#A6ADC8] or press [/][bold #FFD166][Space][/][#A6ADC8] to resume[/]`
  * Transport row indicates ready state with subtle styling.

#### B. Instant Curtain Drawer with Background Loading (`src/bard/ui/curtain_drawer.py`)
* **Instant Opening:**
  * When `toggle()` is called, immediately add `-visible` class and focus the playlist list so the UI responds in 0ms.
* **Non-Blocking Fetch (`@work(thread=True)`):**
  * If playlists are already in memory cache, populate them immediately.
  * If playlists are not yet cached, show an animated / glowing placeholder in the playlist list:
    `✦ ⠋ Deciphering playlists...`
  * Offload `self.client.get_playlists()` to a background worker thread. Upon completion, use `self.call_from_thread()` to populate the OptionList and trigger track loading for the first item.
* **Track Loading Feedback:**
  * When navigating to a playlist whose tracks are not yet cached, immediately clear and show a loading entry in the track list:
    `✦ ⠋ Reading tracklist...`
  * Fetch tracks in a background worker thread and populate without blocking user navigation.

---

### 3. Approaches Considered
1. **Approach A: Instant Open with Dynamic Background Worker (Selected)**
   * Opens the drawer immediately; runs all Spotify fetching on background threads; shows animated loading cues.
   * *Trade-off:* Requires thread-safe UI updates via `call_from_thread`, but provides flawless UI responsiveness and zero keyboard lag.
2. **Approach B: Pre-fetch on Startup (Rejected)**
   * Fetches playlists silently on app boot.
   * *Trade-off:* Burns API tokens immediately even if the user never opens the drawer, and still requires loading states if the cache is empty or cooling down.

---

### 4. Verification Plan
* **Unit Tests:**
  * Test `render_sigil_art()` output and dimensions.
  * Test `ZenStage` rendering with empty playback data displays the sigil.
  * Test `CurtainDrawer` opens instantly and shows loading states when data is pending.
* **Visual Verification:**
  * Run the app and toggle `[Tab]` to verify immediate drawer opening and loading feedback.
  * Inspect the empty state in Zen Stage to ensure centering, color, and formatting.
