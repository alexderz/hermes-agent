"""Enabled bundled plugins publish their desktop half to the app's desktop-plugins folder."""
from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli import desktop_plugin_halves as halves


@pytest.fixture
def layout(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "plugins").mkdir(parents=True)
    bundled = tmp_path / "bundled"
    meter = bundled / "meter" / "desktop"
    meter.mkdir(parents=True)
    (meter / "plugin.js").write_text("export default {}\n", encoding="utf-8")
    (bundled / "agent-only").mkdir()
    (bundled / "agent-only" / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("HERMES_BUNDLED_PLUGINS", str(bundled))
    app_root = tmp_path / "desktop-plugins"
    app_root.mkdir()
    return home, bundled, app_root


def _config(home: Path, enabled: list[str], disabled: list[str] | None = None) -> None:
    lines = ["plugins:", "  enabled:"] + [f"    - {n}" for n in enabled]
    if disabled:
        lines += ["  disabled:"] + [f"    - {n}" for n in disabled]
    (home / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_enabled_bundled_half_is_published(layout):
    home, _, app_root = layout
    _config(home, ["meter", "agent-only"])

    halves.reconcile_desktop_halves(home, app_root)

    assert (app_root / "meter" / "plugin.js").read_text() == "export default {}\n"
    assert halves.read_package_marker(app_root / "meter")["defaultEnabled"] is True
    assert not (app_root / "agent-only").exists()


def test_unlisted_or_disabled_bundled_half_is_not_published(layout):
    home, _, app_root = layout
    _config(home, ["meter"], disabled=["meter"])
    halves.reconcile_desktop_halves(home, app_root)
    assert not (app_root / "meter").exists()

    _config(home, [])
    halves.reconcile_desktop_halves(home, app_root)
    assert not (app_root / "meter").exists()


def test_disabling_prunes_the_published_copy(layout):
    home, _, app_root = layout
    _config(home, ["meter"])
    halves.reconcile_desktop_halves(home, app_root)
    assert (app_root / "meter" / "plugin.js").exists()

    _config(home, [])
    halves.reconcile_desktop_halves(home, app_root)
    assert not (app_root / "meter").exists()


def test_home_package_of_the_same_name_wins(layout):
    home, _, app_root = layout
    _config(home, ["meter"])
    own = home / "plugins" / "meter" / "desktop"
    own.mkdir(parents=True)
    (own / "plugin.js").write_text("export const own = 1\n", encoding="utf-8")

    halves.reconcile_desktop_halves(home, app_root)

    assert (app_root / "meter" / "plugin.js").read_text() == "export const own = 1\n"
    assert not halves.read_package_marker(app_root / "meter").get("defaultEnabled")


def test_missing_config_publishes_nothing_extra(layout):
    home, _, app_root = layout
    halves.reconcile_desktop_halves(home, app_root)
    assert list(app_root.iterdir()) == []


def test_previously_published_bundled_half_gets_enabled_marker(layout):
    home, bundled, app_root = layout
    halves.materialize_desktop_half(bundled / "meter", app_root, "meter")
    assert not halves.read_package_marker(app_root / "meter").get("defaultEnabled")
    _config(home, ["meter"])

    halves.reconcile_desktop_halves(home, app_root)

    assert halves.read_package_marker(app_root / "meter")["defaultEnabled"] is True
