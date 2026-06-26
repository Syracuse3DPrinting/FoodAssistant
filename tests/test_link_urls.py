"""Browser-facing link helpers for co-hosted Grocy/Mealie (FoodAssistant-pmcu, -wjua).

A loopback API base (127.0.0.1 / localhost / the docker service name) is not
reachable from a browser on another device. The link helpers rewrite it to a
LAN-reachable address, preferring the current LAN IP so the link works even when
mDNS (.local) does not resolve on the network, and falling back to the mDNS
hostname when the IP cannot be determined.
"""
from __future__ import annotations

import app.config as config
from app.config import settings


def test_mdns_rewrite_prefers_lan_ip(monkeypatch):
    monkeypatch.setattr(config, "_lan_ip", lambda: "192.168.1.50")
    monkeypatch.setattr(config, "browser_host", lambda: "pi.local")
    assert config._mdns_rewrite("http://127.0.0.1:9383", 9383) == "http://192.168.1.50:9383"


def test_mdns_rewrite_falls_back_to_hostname_without_ip(monkeypatch):
    monkeypatch.setattr(config, "_lan_ip", lambda: "")
    monkeypatch.setattr(config, "browser_host", lambda: "pi.local")
    assert config._mdns_rewrite("http://localhost:9285", 9285) == "http://pi.local:9285"


def test_mdns_rewrite_leaves_non_loopback_untouched(monkeypatch):
    monkeypatch.setattr(config, "_lan_ip", lambda: "192.168.1.50")
    url = "http://192.168.1.10:9383"
    assert config._mdns_rewrite(url, 9383) == url


def test_grocy_link_url_uses_lan_ip_for_loopback_base(monkeypatch):
    monkeypatch.setattr(config, "_lan_ip", lambda: "10.0.0.7")
    monkeypatch.setattr(config, "browser_host", lambda: "pi.local")
    monkeypatch.setattr(settings, "grocy_public_url", "", raising=False)
    monkeypatch.setattr(settings, "grocy_base_url", "http://127.0.0.1:9383", raising=False)
    monkeypatch.setattr(settings, "deployment_mode", "pi_hosted", raising=False)
    assert settings.grocy_link_url() == "http://10.0.0.7:9383"


def test_grocy_public_url_still_wins(monkeypatch):
    monkeypatch.setattr(config, "_lan_ip", lambda: "10.0.0.7")
    monkeypatch.setattr(settings, "grocy_public_url", "https://grocy.example.com", raising=False)
    monkeypatch.setattr(settings, "grocy_base_url", "http://127.0.0.1:9383", raising=False)
    assert settings.grocy_link_url() == "https://grocy.example.com"


def test_mealie_link_url_uses_lan_ip_for_loopback_base(monkeypatch):
    monkeypatch.setattr(config, "_lan_ip", lambda: "10.0.0.7")
    monkeypatch.setattr(config, "browser_host", lambda: "pi.local")
    monkeypatch.setattr(settings, "mealie_public_url", "", raising=False)
    monkeypatch.setattr(settings, "mealie_base_url", "http://localhost:9285", raising=False)
    monkeypatch.setattr(settings, "deployment_mode", "pi_hosted", raising=False)
    assert settings.mealie_link_url() == "http://10.0.0.7:9285"
