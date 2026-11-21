import pytest

from status_board.model import (
    SLOW_LATENCY_MS,
    InvalidServiceError,
    Service,
    Status,
    availability,
    overall,
    parse_service,
)


def test_slow_up_service_shows_degraded() -> None:
    assert Service("api", Status.UP, SLOW_LATENCY_MS).shown_status is Status.DEGRADED
    assert Service("api", Status.UP, SLOW_LATENCY_MS - 1).shown_status is Status.UP
    assert Service("api", Status.DOWN, 10_000).shown_status is Status.DOWN


def test_overall_is_worst_shown_status() -> None:
    assert overall([]) is Status.UP
    assert overall([Service("a", Status.UP, 1), Service("b", Status.DEGRADED, 1)]) is Status.DEGRADED
    assert overall([Service("a", Status.DOWN, 1), Service("b", Status.DEGRADED, 1)]) is Status.DOWN


def test_parse_service_round_trip() -> None:
    assert parse_service({"name": "db", "status": "down", "latency_ms": 3}) == Service("db", Status.DOWN, 3)
    assert parse_service({"name": "db", "status": "up"}).latency_ms == 0


@pytest.mark.parametrize(
    "raw",
    [
        {"status": "up"},
        {"name": "", "status": "up"},
        {"name": "db", "status": "sideways"},
        {"name": "db", "status": "up", "latency_ms": -1},
        {"name": "db", "status": "up", "latency_ms": True},
        {"name": "db", "status": "up", "latency_ms": "fast"},
    ],
)
def test_parse_service_rejects_malformed(raw: dict[str, object]) -> None:
    with pytest.raises(InvalidServiceError):
        parse_service(raw)


def test_availability() -> None:
    assert availability([]) == 1.0
    assert availability([Status.UP, Status.DEGRADED, Status.DOWN, Status.UP]) == 0.75
