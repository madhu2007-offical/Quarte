"""Tests for Carbon-styled Streamlit dashboard and AppTest execution."""

import json
from pathlib import Path
from unittest.mock import patch
import pytest
from streamlit.testing.v1 import AppTest

from dashboard.theme import CARBON_PALETTE, CARBON_WHITE


def test_carbon_palette_and_tokens():
    """Verify Carbon Design System color tokens and palette ordering."""
    expected_palette = [
        "#6929c4",  # purple
        "#1192e8",  # cyan
        "#005d5d",  # teal
        "#9f1853",  # magenta
        "#fa4d56",  # red
        "#002d9c",  # blue
        "#198038",  # green
    ]
    assert CARBON_PALETTE == expected_palette

    assert CARBON_WHITE["page_bg"] == "#ffffff"
    assert CARBON_WHITE["layer_bg"] == "#f4f4f4"
    assert CARBON_WHITE["subtle_border"] == "#e0e0e0"
    assert CARBON_WHITE["strong_border"] == "#8d8d8d"
    assert CARBON_WHITE["interactive_primary"] == "#0f62fe"


def test_offline_bundled_fonts_exist():
    """Verify IBM Plex Sans and IBM Plex Mono fonts are bundled locally for offline use."""
    fonts_dir = Path(__file__).resolve().parent.parent / "dashboard" / "static" / "fonts"
    assert fonts_dir.exists()

    required_fonts = [
        "IBMPlexSans.ttf",
        "IBMPlexMono-Regular.ttf",
        "IBMPlexMono-SemiBold.ttf",
    ]
    for font_name in required_fonts:
        font_path = fonts_dir / font_name
        assert font_path.exists(), f"Font file missing: {font_name}"
        assert font_path.stat().st_size > 50000, f"Font file suspiciously small: {font_name}"


def test_dashboard_apptest_with_hardware_json():
    """Verify dashboard starts with AppTest and renders Panel 7 when hardware JSON exists."""
    app_path = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")
    at = AppTest.from_file(app_path)
    at.run(timeout=15)

    assert len(at.exception) == 0, f"App threw unhandled exceptions: {at.exception}"

    # Panel 7 should be present because results/hardware/*.json with mode == "hardware" exists
    headers = [h.value for h in at.header]
    assert any("7. Hardware run" in h for h in headers)
    assert any("1. Input circuit" in h for h in headers)
    assert any("4. Baseline comparison" in h for h in headers)
    assert any("5. Noisy simulation" in h for h in headers)
    assert any("6. Honest results" in h for h in headers)


def test_dashboard_apptest_without_hardware_json(tmp_path):
    """Verify dashboard starts with AppTest and Panel 7 is completely absent when no hardware files exist."""
    app_path = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")

    with patch("scripts.aggregate_hardware.aggregate_hardware_results", return_value={}), \
         patch("dashboard.app.aggregated_hw", {}):
        at = AppTest.from_file(app_path)
        at.run(timeout=15)

        assert len(at.exception) == 0, f"App threw unhandled exceptions: {at.exception}"

        headers = [h.value for h in at.header]
        assert not any("7. Hardware run" in h for h in headers), (
            f"Panel 7 should NOT be present when no hardware records exist, but found in: {headers}"
        )
