"""Integration: replay each outage scenario through the poller at its real polling interval."""

import json
from pathlib import Path

import pytest

from status_board.model import Status, availability
from status_board.simulate import simulate

CALIBRATION = json.loads((Path(__file__).resolve().parents[2] / "calibration.json").read_text(encoding="utf-8"))
TICKS = CALIBRATION["ticks_per_case"]
TICK_SECONDS = CALIBRATION["integration_seconds_per_case"] / TICKS

EXPECTED_AVAILABILITY = {
    "steady": 1.0,
    "flapping": 0.5,
    "cascade": 0.3,
    "recovery": 0.5,
    "brownout": 1.0,
    "partition": 0.5,
    "maintenance": 1.0,
}
EXPECTED_FINAL = {
    "steady": Status.UP,
    "flapping": Status.DOWN,
    "cascade": Status.DOWN,
    "recovery": Status.UP,
    "brownout": Status.DEGRADED,
    "partition": Status.UP,
    "maintenance": Status.UP,
}


@pytest.mark.parametrize("scenario", CALIBRATION["integration_cases"])
def test_scenario_timeline(scenario: str) -> None:
    frames = simulate(scenario, ticks=TICKS, tick_seconds=TICK_SECONDS)
    assert availability([frame.overall for frame in frames]) == EXPECTED_AVAILABILITY[scenario]
    assert frames[-1].overall is EXPECTED_FINAL[scenario]
