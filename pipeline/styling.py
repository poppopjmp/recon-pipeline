"""Lightweight, self-contained terminal styling helper.

Historically recon-pipeline imported ``style`` from ``cmd2.ansi``.  cmd2
removed that helper (string color names were dropped in 2.x and the whole
module was rewritten on top of ``rich`` in 3.x), which broke every import
site in the project.

Rather than chase cmd2's styling API across releases, we provide a small,
dependency-free ``style`` function here.  It emits the exact same SGR escape
sequences that ``cmd2.ansi.style`` produced in the 1.x era, so existing call
sites -- and the tests that assert on specific escape codes -- keep working
regardless of which cmd2 version is installed.
"""

# Standard foreground SGR codes; bright_* use the 90-97 range.
_FG = {
    "black": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "white": 37,
    "bright_black": 90,
    "bright_red": 91,
    "bright_green": 92,
    "bright_yellow": 93,
    "bright_blue": 94,
    "bright_magenta": 95,
    "bright_cyan": 96,
    "bright_white": 97,
}

# Background codes are the matching foreground codes shifted by 10.
_BG = {name: code + 10 for name, code in _FG.items()}

_FG_RESET = "\x1b[39m"
_BG_RESET = "\x1b[49m"


def style(value, *, fg="", bg="", bold=False, dim=False, underline=False):
    """Wrap ``value`` in ANSI escape sequences for the requested attributes.

    Mirrors the behaviour of the old ``cmd2.ansi.style``: each enabled
    attribute is prepended as an SGR sequence and a matching reset is
    appended, in the order fg, bg, bold, dim, underline.

    Args:
        value: text (or any stringifiable object) to style.
        fg: foreground color name (e.g. ``"bright_red"``).
        bg: background color name.
        bold/dim/underline: text attribute toggles.

    Returns:
        The styled string.  When no attributes are requested the input is
        returned unchanged (apart from being coerced to ``str``).
    """
    additions = []
    removals = []

    if fg:
        try:
            additions.append(f"\x1b[{_FG[fg]}m")
        except KeyError:
            raise ValueError(f"Unknown foreground color: {fg!r}") from None
        removals.append(_FG_RESET)

    if bg:
        try:
            additions.append(f"\x1b[{_BG[bg]}m")
        except KeyError:
            raise ValueError(f"Unknown background color: {bg!r}") from None
        removals.append(_BG_RESET)

    if bold:
        additions.append("\x1b[1m")
        removals.append("\x1b[22m")

    if dim:
        additions.append("\x1b[2m")
        removals.append("\x1b[22m")

    if underline:
        additions.append("\x1b[4m")
        removals.append("\x1b[24m")

    return "".join(additions) + str(value) + "".join(removals)
