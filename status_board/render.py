"""Render the board as a standalone HTML page."""

from collections.abc import Sequence
from html import escape

from status_board.model import Service, Status, overall

BANNERS = {
    Status.UP: "All systems operational",
    Status.DEGRADED: "Some systems are degraded",
    Status.DOWN: "Major outage",
}

_STYLE = """
body { font-family: system-ui, sans-serif; margin: 0; background: #f6f7f9; color: #1d2330; }
.banner { padding: 16px 24px; color: #fff; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; padding: 24px; }
.card { background: #fff; border-radius: 8px; padding: 12px 16px; border-left: 6px solid; }
.status-up { background-color: #1f883d; border-color: #1f883d; }
.status-degraded { background-color: #bf8700; border-color: #bf8700; }
.status-down { background-color: #cf222e; border-color: #cf222e; }
.card.status-up, .card.status-degraded, .card.status-down { background-color: #fff; }
"""


def render_board(services: Sequence[Service], title: str = "Service status") -> str:
    """The full page: a banner with the overall status, then one card per service."""
    state = overall(services)
    cards = "\n".join(_card(service) for service in services)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        f'<head><meta charset="utf-8"><title>{escape(title)}</title><style>{_STYLE}</style></head>\n'
        "<body>\n"
        f'<header class="banner status-{state}" data-overall="{state}">'
        f"<h1>{escape(title)}</h1><p>{BANNERS[state]}</p></header>\n"
        f'<main class="grid">\n{cards}\n</main>\n'
        "</body>\n"
        "</html>\n"
    )


def _card(service: Service) -> str:
    shown = service.shown_status
    name = escape(service.name)
    return (
        f'<section class="card status-{service.status}" data-service="{name}" data-status="{shown}">'
        f'<h2>{name}</h2><p class="latency">{service.latency_ms} ms</p></section>'
    )
