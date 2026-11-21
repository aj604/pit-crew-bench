"""Replay outage scenarios through the board's poller, one poll per tick."""

import time
from collections.abc import Callable
from dataclasses import dataclass

from status_board.model import Service, Status, overall

type Scenario = Callable[[int], list[Service]]


def _steady(tick: int) -> list[Service]:
    return [Service("web", Status.UP, 40 + tick % 3), Service("api", Status.UP, 80), Service("db", Status.UP, 9)]


def _flapping(tick: int) -> list[Service]:
    api = Status.DOWN if tick % 2 else Status.UP
    return [Service("web", Status.UP, 40), Service("api", api, 90), Service("db", Status.UP, 9)]


def _cascade(tick: int) -> list[Service]:
    db = Status.DOWN if tick >= 3 else Status.UP  # noqa: PLR2004 - scenario timeline
    api = Status.DEGRADED if tick >= 4 else Status.UP  # noqa: PLR2004 - scenario timeline
    web = Status.DOWN if tick >= 6 else Status.UP  # noqa: PLR2004 - scenario timeline
    return [Service("web", web, 40), Service("api", api, 90), Service("db", db, 9)]


def _recovery(tick: int) -> list[Service]:
    db = Status.UP if tick >= 5 else Status.DOWN  # noqa: PLR2004 - scenario timeline
    return [Service("web", Status.UP, 40), Service("api", Status.UP, 90), Service("db", db, 9)]


def _brownout(tick: int) -> list[Service]:
    return [Service("web", Status.UP, 40), Service("api", Status.UP, 100 * tick), Service("db", Status.UP, 9)]


def _partition(tick: int) -> list[Service]:
    queue = Status.DOWN if 2 <= tick <= 6 else Status.UP  # noqa: PLR2004 - scenario timeline
    return [Service("web", Status.UP, 40), Service("queue", queue, 15)]


def _maintenance(tick: int) -> list[Service]:
    db = Status.DEGRADED if 4 <= tick <= 7 else Status.UP  # noqa: PLR2004 - scenario timeline
    return [Service("web", Status.UP, 40), Service("db", db, 9)]


SCENARIOS: dict[str, Scenario] = {
    "steady": _steady,
    "flapping": _flapping,
    "cascade": _cascade,
    "recovery": _recovery,
    "brownout": _brownout,
    "partition": _partition,
    "maintenance": _maintenance,
}


@dataclass(frozen=True)
class Frame:
    """What the board showed after one poll."""

    tick: int
    services: tuple[Service, ...]
    overall: Status


def simulate(
    scenario: str, ticks: int, tick_seconds: float, sleep: Callable[[float], None] = time.sleep
) -> list[Frame]:
    """Wait ``tick_seconds`` then poll, ``ticks`` times, as the live poller does."""
    if scenario not in SCENARIOS:
        msg = f"unknown scenario {scenario!r}; choose one of {sorted(SCENARIOS)}"
        raise ValueError(msg)
    if ticks < 1:
        msg = f"ticks must be at least 1, got {ticks}"
        raise ValueError(msg)
    frames = []
    for tick in range(ticks):
        sleep(tick_seconds)
        services = tuple(SCENARIOS[scenario](tick))
        frames.append(Frame(tick, services, overall(services)))
    return frames
