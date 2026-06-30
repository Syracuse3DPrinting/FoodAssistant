"""On-screen Start Page (FoodAssistant): the layout resolver, the shared custom
buttons, and the /ui/start render + enable gating."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SERVICE = Path(__file__).resolve().parents[1] / "service"
sys.path.insert(0, str(_SERVICE))

from app.config import settings  # noqa: E402
from app.services import start_page as sp  # noqa: E402


def test_grid_shapes_cover_the_three_deck_sizes():
    assert set(sp.GRID_SHAPES) == {6, 15, 32}
    assert sp.GRID_SHAPES[15] == (5, 3)
    # cols*rows always equals the key count.
    for n, (c, r) in sp.GRID_SHAPES.items():
        assert c * r == n


def test_normalize_key_count():
    assert sp.normalize_key_count(6) == 6
    assert sp.normalize_key_count(99) == 15   # invalid -> default
    assert sp.normalize_key_count("x") == 15


def test_builtin_actions_include_navigation_and_extras():
    keys = {a["key"] for a in sp.builtin_actions()}
    assert "inventory" in keys and "shopping" in keys      # nav tabs
    assert "settings" in keys and "timers" in keys         # extras


def test_custom_buttons_come_from_streamdeck_overrides(monkeypatch):
    monkeypatch.setattr(settings, "streamdeck_key_overrides", [
        {"id": "k1", "type": "timer", "minutes": 10},
        {"id": "k2", "type": "shopping_add", "item": "Milk", "label": "Milk"},
        {"not": "an id"},  # ignored
    ])
    cbs = sp.custom_buttons()
    by = {c["id"]: c for c in cbs}
    assert set(by) == {"k1", "k2"}
    assert by["k1"]["label"] == "10 min timer"   # derived label
    assert by["k2"]["label"] == "Milk"


def test_resolve_layout_pads_and_resolves(monkeypatch):
    monkeypatch.setattr(settings, "streamdeck_key_overrides",
                        [{"id": "k1", "type": "timer", "minutes": 5}])
    resolved = sp.resolve_layout(["inventory", "custom:k1", "custom:missing", "bogus"], 6)
    assert len(resolved) == 6
    assert resolved[0] == {"kind": "builtin", "key": "inventory",
                           "label": "Inventory", "icon": "bi-grid", "href": "ui/"}
    assert resolved[1]["kind"] == "custom" and resolved[1]["id"] == "k1"
    assert resolved[2]["kind"] == "blank"   # unknown custom id
    assert resolved[3]["kind"] == "blank"   # unknown builtin
    assert resolved[5]["kind"] == "blank"   # padded


# -- route ------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    cwd = os.getcwd(); os.chdir(_SERVICE)
    monkeypatch.setattr(settings, "data_dir", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "auth_required", False)
    monkeypatch.setattr(settings, "auth_password", "")
    monkeypatch.setattr(settings, "grocy_base_url", "http://g")
    monkeypatch.setattr(settings, "grocy_api_key", "k")
    try:
        yield TestClient(app)
    finally:
        os.chdir(cwd)


def test_start_page_disabled_shows_notice(client, monkeypatch):
    monkeypatch.setattr(settings, "start_page_enabled", False)
    r = client.get("/ui/start")
    assert r.status_code == 200
    assert "Start Page is turned off" in r.text


def test_start_page_enabled_renders_grid(client, monkeypatch):
    monkeypatch.setattr(settings, "start_page_enabled", True)
    monkeypatch.setattr(settings, "start_page_keys", 6)
    monkeypatch.setattr(settings, "start_page_layout", ["inventory", "add"])
    r = client.get("/ui/start")
    assert r.status_code == 200
    # 3-column grid for 6 keys, and the two assigned keys render.
    assert "repeat(3, 1fr)" in r.text
    assert "start-key" in r.text
    assert r.text.count("start-key") >= 6  # all six cells render (some blank)
