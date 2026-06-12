"""
Nyxora TUI v3.0.0 — markup escaping for dynamic content.

Any dynamic value (generated password, user entry field, remote release
tag, exception text) interpolated into a Textual markup f-string must go
through escape() first. A tag-shaped substring like [on=^D3oNz] in a raw
value makes Textual raise MarkupError at render time — after update()
returns, past every local try/except — and crashes the whole app.

rich.markup.escape (and textual.markup.escape, same regex) is NOT
sufficient: both only escape complete [tag]-shaped sequences, so an
unclosed trailing fragment like "a[on=" passes through raw and still
crashes Textual's parser when a closing tag follows. Textual treats any
backslash directly before '[' as escaping that bracket (consuming one
backslash from the run), so escaping every '[' round-trips the value
exactly. A value ending in a backslash would escape the template's next
closing tag — inexpressible in Textual markup — which degrades to a
cosmetic styling bleed, never a MarkupError.
"""
from __future__ import annotations


def escape(text: str) -> str:
    """Escape text for safe interpolation into Textual markup."""
    text = text.replace("[", "\\[")
    if text.endswith("\\"):
        # A lone trailing backslash would escape the template's next
        # opening bracket (e.g. eat a closing tag); doubling it keeps
        # the backslash visible and limits damage to styling.
        text += "\\"
    return text
