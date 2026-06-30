"""On-screen Start Page: a full-screen launcher that works like an on-screen
Stream Deck (FoodAssistant).

The page renders a grid of keys (6, 15, or 32, matching the physical Stream Deck
sizes). Each slot in ``start_page_layout`` is one of:

* a built-in action key (see ``BUILTIN_ACTIONS``) that opens an app page,
* ``"custom:<id>"`` referencing a custom button in ``streamdeck_key_overrides``
  (the SAME store the physical deck uses, so custom buttons are shared both
  ways), or
* ``""`` for a blank key.

Pure helpers here resolve a stored layout into render-ready key dicts so the
template and tests stay simple. Browser-side behaviour for each key lives in the
start page template.
"""
from __future__ import annotations

from .. import navigation

# Grid shapes per key count, mirroring the Stream Deck hardware (cols x rows).
GRID_SHAPES = {6: (3, 2), 15: (5, 3), 32: (8, 4)}
VALID_KEY_COUNTS = tuple(GRID_SHAPES.keys())
_DEFAULT_KEYS = 15

# Built-in launcher actions. Each opens an app page (href is root-relative so it
# resolves against the ingress base). The list is derived from the navigation
# registry plus a few app destinations the deck also offers (timers, settings).
_EXTRA_ACTIONS = [
    {"key": "timers",   "label": "Timers",   "icon": "bi-stopwatch", "href": "ui/timers"},
    {"key": "settings", "label": "Settings", "icon": "bi-gear",       "href": "setup"},
]

# Grouping + tile colours so the Start Page grid and palette render like the
# Stream Deck (colored keys, grouped palette). Each action takes its group's
# colour; the group also labels the palette row. Keys not listed fall in "More".
_ACTION_GROUPS = [
    ("Inventory", "#2563eb", ("inventory", "expiring", "add", "pending", "audit", "shopping", "nutrition")),
    ("Recipes",   "#c2410c", ("recipes", "cook", "current_recipe", "mealplan")),
    ("Tools",     "#0d9488", ("convert", "weather", "camera", "guide", "shop", "defaults", "timers")),
    ("System",    "#475569", ("about", "settings", "start")),
]
_DEFAULT_GROUP = ("More", "#374151")


def _group_for(key: str) -> tuple[str, str]:
    for name, color, keys in _ACTION_GROUPS:
        if key in keys:
            return name, color
    return _DEFAULT_GROUP


def builtin_actions() -> list[dict]:
    """All built-in launcher actions: every navigation tab plus a few extras,
    each tagged with a palette group and tile colour so the editor renders like
    the Stream Deck."""
    out: list[dict] = []
    for tab in navigation.NAV_TABS:
        out.append({"key": tab["key"], "label": tab["label"],
                    "icon": tab["icon"], "href": tab["href"]})
    out.extend(_EXTRA_ACTIONS)
    for a in out:
        a["group"], a["color"] = _group_for(a["key"])
    return out


def _builtin_by_key() -> dict[str, dict]:
    return {a["key"]: a for a in builtin_actions()}


def custom_buttons(overrides: list | None = None) -> list[dict]:
    """Shared custom buttons (from ``streamdeck_key_overrides``) as render dicts.

    Returns one entry per defined custom key with a stable id, a display label,
    an icon, and its action ``type`` so the page can decide how to fire it."""
    from ..config import settings
    raw = overrides if overrides is not None else (settings.streamdeck_key_overrides or [])
    seen: set[str] = set()
    out: list[dict] = []
    for ov in raw:
        if not isinstance(ov, dict):
            continue
        cid = str(ov.get("id") or "").strip()
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append({
            "id": cid,
            "type": ov.get("type", ""),
            "label": ov.get("label") or _label_for_type(ov),
            "icon": ov.get("icon") or _icon_for_type(ov.get("type", "")),
            "def": ov,
        })
    return out


_TYPE_ICONS = {
    "ha_action": "bi-toggle-on", "timer": "bi-stopwatch", "weather": "bi-cloud-sun",
    "shopping_add": "bi-cart-plus", "macro": "bi-collection-play",
    "camera": "bi-camera-video", "media": "bi-music-note-beamed",
}


def _icon_for_type(t: str) -> str:
    return _TYPE_ICONS.get(t, "bi-grid-1x2")


def _label_for_type(ov: dict) -> str:
    t = ov.get("type", "")
    if t == "timer":
        return f"{ov.get('minutes', 0)} min timer"
    if t == "shopping_add":
        return ov.get("item", "Add to list")
    if t == "weather":
        return "Weather"
    return t.replace("_", " ").title() or "Custom"


def normalize_key_count(value) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_KEYS
    return n if n in VALID_KEY_COUNTS else _DEFAULT_KEYS


def resolve_layout(layout: list | None, key_count: int,
                   overrides: list | None = None) -> list[dict]:
    """Resolve a stored layout into exactly ``key_count`` render-ready keys.

    Each result is ``{"kind": "builtin"|"custom"|"blank", ...}``. Unknown or
    missing tokens become blank keys, and the list is padded/truncated to the
    grid size so the template can render a fixed grid."""
    key_count = normalize_key_count(key_count)
    builtins = _builtin_by_key()
    customs = {c["id"]: c for c in custom_buttons(overrides)}
    slots = list(layout or [])[:key_count]
    out: list[dict] = []
    for tok in slots:
        tok = str(tok or "")
        if tok.startswith("custom:"):
            cid = tok.split(":", 1)[1]
            c = customs.get(cid)
            if c:
                out.append({"kind": "custom", "id": cid, "type": c["type"],
                            "label": c["label"], "icon": c["icon"]})
                continue
        elif tok in builtins:
            b = builtins[tok]
            out.append({"kind": "builtin", "key": tok, "label": b["label"],
                        "icon": b["icon"], "href": b["href"]})
            continue
        out.append({"kind": "blank"})
    while len(out) < key_count:
        out.append({"kind": "blank"})
    return out
