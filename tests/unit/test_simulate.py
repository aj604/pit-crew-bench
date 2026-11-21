import pytest

from status_board.model import Status
from status_board.simulate import SCENARIOS, simulate


def test_simulate_sleeps_once_per_tick() -> None:
    waits: list[float] = []
    frames = simulate("cascade", ticks=8, tick_seconds=0.5, sleep=waits.append)
    assert waits == [0.5] * 8
    assert [f.overall for f in frames] == [Status.UP] * 3 + [Status.DOWN] * 5
    assert [f.tick for f in frames] == list(range(8))


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_every_scenario_polls(scenario: str) -> None:
    frames = simulate(scenario, ticks=10, tick_seconds=0, sleep=lambda _: None)
    assert len(frames) == 10
    assert all(frame.services for frame in frames)


def test_simulate_rejects_bad_input() -> None:
    with pytest.raises(ValueError, match="unknown scenario"):
        simulate("meteor", ticks=1, tick_seconds=0)
    with pytest.raises(ValueError, match="at least 1"):
        simulate("steady", ticks=0, tick_seconds=0)
