"""End to end: poll a scenario in real time, render every frame, and check the page."""

import json
from pathlib import Path

import pytest

from status_board.render import render_board
from status_board.simulate import simulate
from status_board.ui_check import check, parse_dom

CALIBRATION = json.loads((Path(__file__).resolve().parents[2] / "calibration.json").read_text(encoding="utf-8"))
TICKS = CALIBRATION["ticks_per_case"]


@pytest.mark.parametrize("scenario", CALIBRATION["e2e_cases"])
def test_rendered_board_tracks_scenario(scenario: str) -> None:
    frames = simulate(scenario, ticks=TICKS, tick_seconds=CALIBRATION["e2e_seconds_per_case"] / TICKS)
    for frame in frames:
        dom = parse_dom(render_board(frame.services, "Live"))
        expect: dict[str, object] = {"cards": len(frame.services), "overall": frame.overall}
        assert check(dom, "Live", frame.services, expect) == []
