"""Enables true terminal background transparency in Textual.

By default, Textual maps transparent backgrounds (Color with alpha 0) to RGB (0, 0, 0)
and explicitly emits `\x1b[48;2;0;0;0m` for every empty cell. Terminal emulators
(like Windows Terminal, Ghostty, Alacritty, Kitty, and iTerm2) interpret this explicit
background color as a command to paint solid, opaque black rectangles over the window's
acrylic / mica / blur glass.

This module patches Textual's ANSI generator to omit background escape sequences for
transparent / canvas black cells, allowing the terminal emulator's native background
transparency to show through—matching Tome, Chalice, and Forge.
"""

from __future__ import annotations

from rich.style import Style as RichStyle
from textual.strip import SGR_STYLES, Strip

_patched = False


def enable_terminal_transparency() -> None:
    """Patch Textual's ANSI generator to support transparent terminal backgrounds."""
    global _patched
    if _patched:
        return
    _patched = True

    def patched_render_ansi(cls, style: RichStyle, color_system) -> str:
        if (ansi := style._ansi) is not None:
            return ansi
        sgr: list[str] = []
        if attributes := style._attributes & style._set_attributes:
            sgr = [
                SGR_STYLES[bit_offset]
                for bit_offset in range(attributes.bit_length())
                if attributes & (1 << bit_offset)
            ]
        if (color := style._color) is not None:
            sgr.extend(color.downgrade(color_system).get_ansi_codes())
        if (bgcolor := style._bgcolor) is not None:
            is_canvas_black = False
            if (
                bgcolor.triplet
                and bgcolor.triplet.red == 0
                and bgcolor.triplet.green == 0
                and bgcolor.triplet.blue == 0
            ):
                is_canvas_black = True
            elif getattr(bgcolor, "number", None) == 0:
                is_canvas_black = True

            if not is_canvas_black:
                sgr.extend(bgcolor.downgrade(color_system).get_ansi_codes(False))

        ansi = style._ansi = ";".join(sgr)
        return ansi

    Strip.render_ansi = classmethod(patched_render_ansi)
