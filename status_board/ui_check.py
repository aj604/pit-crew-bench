"""Headless UI check: render the board from a fixture and assert on its DOM.

Run ``python -m status_board.ui_check``. On failure it writes diagnostic SVG and PNG snapshots of
what rendered, with the failed assertions, to ``ui-snapshots/`` and exits 1.
"""

import argparse
import json
import struct
import sys
import zlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
from pathlib import Path

from status_board.model import InvalidServiceError, Service, Status, parse_service
from status_board.render import render_board

type Rgb = tuple[int, int, int]
type Box = tuple[int, int, int, int]

DEFAULT_FIXTURE = Path("fixtures/board.json")
DEFAULT_SNAPSHOT_DIR = Path("ui-snapshots")
SNAPSHOT_NAME = "ui-check.svg"
SNAPSHOT_PNG_NAME = "ui-check.png"
PNG_WIDTH = 640
PNG_HEIGHT = 240

_COLORS = {"up": "#1f883d", "degraded": "#bf8700", "down": "#cf222e"}
_PNG_COLORS: dict[str, Rgb] = {
    "up": (0x1A, 0x7F, 0x37),
    "operational": (0x1A, 0x7F, 0x37),
    "degraded": (0x9A, 0x67, 0x00),
    "down": (0xCF, 0x22, 0x2E),
    "outage": (0xCF, 0x22, 0x2E),
}
_PNG_FALLBACK: Rgb = (0x57, 0x60, 0x6A)
_PNG_BG: Rgb = (0xF6, 0xF7, 0xF9)
_PNG_WHITE: Rgb = (0xFF, 0xFF, 0xFF)
_PNG_INK: Rgb = (0x1D, 0x23, 0x30)
_PNG_RED: Rgb = (0xCF, 0x22, 0x2E)

_BANNER_H = 48
_CARD_W = 140
_CARD_H = 56
_CARDS_PER_ROW = 4
_GLYPH_W = 5

_FONT_5X7: dict[str, bytes] = {
    " ": bytes((0, 0, 0, 0, 0, 0, 0)),
    "A": bytes((14, 17, 17, 31, 17, 17, 17)),
    "B": bytes((30, 17, 17, 30, 17, 17, 30)),
    "C": bytes((14, 17, 16, 16, 16, 17, 14)),
    "D": bytes((30, 17, 17, 17, 17, 17, 30)),
    "E": bytes((31, 16, 16, 30, 16, 16, 31)),
    "F": bytes((31, 16, 16, 30, 16, 16, 16)),
    "G": bytes((14, 17, 16, 23, 17, 17, 14)),
    "H": bytes((17, 17, 17, 31, 17, 17, 17)),
    "I": bytes((14, 4, 4, 4, 4, 4, 14)),
    "J": bytes((7, 2, 2, 2, 18, 18, 12)),
    "K": bytes((17, 18, 20, 24, 20, 18, 17)),
    "L": bytes((16, 16, 16, 16, 16, 16, 31)),
    "M": bytes((17, 27, 21, 21, 17, 17, 17)),
    "N": bytes((17, 25, 21, 19, 17, 17, 17)),
    "O": bytes((14, 17, 17, 17, 17, 17, 14)),
    "P": bytes((30, 17, 17, 30, 16, 16, 16)),
    "Q": bytes((14, 17, 17, 17, 21, 18, 13)),
    "R": bytes((30, 17, 17, 30, 20, 18, 17)),
    "S": bytes((15, 16, 16, 14, 1, 1, 30)),
    "T": bytes((31, 4, 4, 4, 4, 4, 4)),
    "U": bytes((17, 17, 17, 17, 17, 17, 14)),
    "V": bytes((17, 17, 17, 17, 17, 10, 4)),
    "W": bytes((17, 17, 17, 21, 21, 27, 17)),
    "X": bytes((17, 17, 10, 4, 10, 17, 17)),
    "Y": bytes((17, 17, 10, 4, 4, 4, 4)),
    "Z": bytes((31, 1, 2, 4, 8, 16, 31)),
    "0": bytes((14, 17, 19, 21, 25, 17, 14)),
    "1": bytes((4, 12, 4, 4, 4, 4, 14)),
    "2": bytes((14, 17, 1, 6, 8, 16, 31)),
    "3": bytes((30, 1, 1, 14, 1, 1, 30)),
    "4": bytes((2, 6, 10, 18, 31, 2, 2)),
    "5": bytes((31, 16, 30, 1, 1, 17, 14)),
    "6": bytes((6, 8, 16, 30, 17, 17, 14)),
    "7": bytes((31, 1, 2, 4, 8, 8, 8)),
    "8": bytes((14, 17, 17, 14, 17, 17, 14)),
    "9": bytes((14, 17, 17, 15, 1, 2, 12)),
    ":": bytes((0, 4, 4, 0, 4, 4, 0)),
    "-": bytes((0, 0, 0, 31, 0, 0, 0)),
    "_": bytes((0, 0, 0, 0, 0, 0, 31)),
    ".": bytes((0, 0, 0, 0, 0, 12, 12)),
    ",": bytes((0, 0, 0, 0, 4, 4, 8)),
    "'": bytes((4, 4, 8, 0, 0, 0, 0)),
    '"': bytes((10, 10, 0, 0, 0, 0, 0)),
    "(": bytes((2, 4, 8, 8, 8, 4, 2)),
    ")": bytes((8, 4, 2, 2, 2, 4, 8)),
    "[": bytes((14, 8, 8, 8, 8, 8, 14)),
    "]": bytes((14, 2, 2, 2, 2, 2, 14)),
    "/": bytes((1, 2, 2, 4, 8, 8, 16)),
    "?": bytes((14, 17, 1, 6, 4, 0, 4)),
    "!": bytes((4, 4, 4, 4, 4, 0, 4)),
    "=": bytes((0, 0, 31, 0, 31, 0, 0)),
    "+": bytes((0, 4, 4, 31, 4, 4, 0)),
    "#": bytes((10, 31, 10, 10, 31, 10, 0)),
    "%": bytes((25, 26, 2, 4, 8, 19, 19)),
    "<": bytes((2, 4, 8, 16, 8, 4, 2)),
    ">": bytes((8, 4, 2, 1, 2, 4, 8)),
}


@dataclass
class Dom:
    """The parts of the rendered page the check asserts on."""

    title: str = ""
    banner: dict[str, str] = field(default_factory=dict)
    cards: list[dict[str, str]] = field(default_factory=list)


class _DomParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.dom = Dom()
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = values.get("class", "").split()
        if tag == "title":
            self._in_title = True
        elif tag == "header" and "banner" in classes:
            self.dom.banner = values
        elif tag == "section" and "card" in classes:
            self.dom.cards.append(values)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.dom.title += data


def parse_dom(html: str) -> Dom:
    """Parse the rendered page into the elements the check cares about."""
    parser = _DomParser()
    parser.feed(html)
    parser.close()
    return parser.dom


def check(dom: Dom, title: str, services: Sequence[Service], expect: dict[str, object]) -> list[str]:
    """Every assertion that failed; empty when the page is right."""
    problems = []
    if dom.title != title:
        problems.append(f"title is {dom.title!r}, expected {title!r}")
    if dom.banner.get("data-overall") != expect.get("overall"):
        problems.append(f"banner shows {dom.banner.get('data-overall')!r}, expected {expect.get('overall')!r}")
    if len(dom.cards) != expect.get("cards"):
        problems.append(f"{len(dom.cards)} cards rendered, expected {expect.get('cards')}")
    names = [card.get("data-service") for card in dom.cards]
    if names != [service.name for service in services]:
        problems.append(f"cards are {names}, expected {[s.name for s in services]}")
    for card in dom.cards:
        status = card.get("data-status", "")
        if status not in set(Status) or f"status-{status}" not in card.get("class", "").split():
            problems.append(f"card {card.get('data-service')!r} has inconsistent status {status!r}")
    return problems


def snapshot_svg(dom: Dom, problems: Sequence[str]) -> str:
    """A picture of what rendered (banner and cards) above the failed assertions."""
    width, card_w, card_h = PNG_WIDTH, _CARD_W, _CARD_H
    rows = (len(dom.cards) + 3) // _CARDS_PER_ROW
    height = 80 + rows * (card_h + 12) + 24 * len(problems) + 24
    overall = dom.banner.get("data-overall", "")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#f6f7f9"/>',
        f'<rect width="{width}" height="{_BANNER_H}" fill="{_COLORS.get(overall, "#57606a")}"/>',
        f'<text x="16" y="30" fill="#fff" font-size="18">{_text(dom.title)} - {_text(overall or "no banner")}</text>',
    ]
    for i, card in enumerate(dom.cards):
        x, y = 16 + (i % _CARDS_PER_ROW) * (card_w + 12), 64 + (i // _CARDS_PER_ROW) * (card_h + 12)
        color = _COLORS.get(card.get("data-status", ""), "#57606a")
        parts.append(f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" fill="#fff" stroke="{color}"/>')
        label = _text(f"{card.get('data-service', '?')}: {card.get('data-status', '?')}")
        parts.append(f'<text x="{x + 8}" y="{y + 32}" font-size="14">{label}</text>')
    top = 80 + rows * (card_h + 12)
    for i, problem in enumerate(problems):
        parts.append(f'<text x="16" y="{top + 24 * i}" fill="#cf222e" font-size="13">{_text(problem)}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)


class _Canvas:
    def __init__(self, width: int, height: int, bg: Rgb) -> None:
        self.width = width
        self.height = height
        self._stride = 1 + width * 3
        self._buf = bytearray((b"\x00" + bytes(bg) * width) * height)

    def rect(self, box: Box, rgb: Rgb) -> None:
        x, y, w, h = box
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + w), min(self.height, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        row_bytes = bytes(rgb) * (x1 - x0)
        for ry in range(y0, y1):
            start = ry * self._stride + 1 + x0 * 3
            self._buf[start : start + len(row_bytes)] = row_bytes

    def border(self, box: Box, rgb: Rgb, thickness: int = 1) -> None:
        x, y, w, h = box
        self.rect((x, y, w, thickness), rgb)
        self.rect((x, y + h - thickness, w, thickness), rgb)
        self.rect((x, y, thickness, h), rgb)
        self.rect((x + w - thickness, y, thickness, h), rgb)

    def _glyph(self, pos: tuple[int, int], rows: bytes, rgb: Rgb, scale: int) -> None:
        gx, gy = pos
        for row_idx, mask in enumerate(rows):
            for col_idx in range(_GLYPH_W):
                if mask & (1 << (_GLYPH_W - 1 - col_idx)):
                    self.rect((gx + col_idx * scale, gy + row_idx * scale, scale, scale), rgb)

    def text(self, pos: tuple[int, int], value: str, rgb: Rgb, scale: int = 1) -> None:
        x, y = pos
        step = (_GLYPH_W + 1) * scale
        for i, ch in enumerate(value.upper()):
            px = x + i * step
            if px >= self.width - 8:
                break
            self._glyph((px, y), _FONT_5X7.get(ch, _FONT_5X7["?"]), rgb, scale)

    def to_png(self) -> bytes:
        ihdr = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        idat = zlib.compress(self._buf, level=6)
        return b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", idat) + _png_chunk(b"IEND", b"")


def _draw_png_card(canvas: _Canvas, index: int, card: dict[str, str]) -> None:
    col, row = index % _CARDS_PER_ROW, index // _CARDS_PER_ROW
    x, y = 16 + col * (_CARD_W + 12), 60 + row * (_CARD_H + 8)
    status = card.get("data-status", "")
    color = _PNG_COLORS.get(status, _PNG_FALLBACK)
    canvas.rect((x, y, _CARD_W, _CARD_H), _PNG_WHITE)
    canvas.border((x, y, _CARD_W, _CARD_H), color)
    canvas.rect((x, y, 6, _CARD_H), color)
    if status not in set(Status) or f"status-{status}" not in card.get("class", "").split():
        canvas.rect((x, y, _CARD_W, 3), _PNG_RED)
    label = f"{card.get('data-service', '?')}: {status or '?'}"
    canvas.text((x + 12, y + 24), label[:19], _PNG_INK)


def snapshot_png(dom: Dom, problems: Sequence[str]) -> bytes:
    """Render a 640x240 RGB PNG snapshot of the dashboard and failed assertions."""
    canvas = _Canvas(PNG_WIDTH, PNG_HEIGHT, _PNG_BG)
    overall = dom.banner.get("data-overall", "")
    canvas.rect((0, 0, PNG_WIDTH, _BANNER_H), _PNG_COLORS.get(overall, _PNG_FALLBACK))
    if problems:
        canvas.rect((0, _BANNER_H - 4, PNG_WIDTH, 4), _PNG_RED)
    header = f"{dom.title or 'Service status'} - {overall or 'no banner'}"
    canvas.text((16, 17), header, _PNG_WHITE, scale=2)
    for i, card in enumerate(dom.cards):
        _draw_png_card(canvas, i, card)
    rows = max(1, (len(dom.cards) + _CARDS_PER_ROW - 1) // _CARDS_PER_ROW)
    top = min(PNG_HEIGHT - 36, 60 + rows * (_CARD_H + 8) + 6)
    if problems:
        block_h = min(PNG_HEIGHT - top - 4, 18 + 12 * len(problems))
        canvas.rect((16, top, PNG_WIDTH - 32, 2), _PNG_RED)
        canvas.rect((16, top, 4, max(12, block_h)), _PNG_RED)
        canvas.text((26, top + 6), "UI CHECK FAILED", _PNG_RED)
        for i, problem in enumerate(problems):
            canvas.text((26, top + 20 + 12 * i), f"- {problem}", _PNG_RED)
    return canvas.to_png()


def _text(value: str) -> str:
    return escape(value, quote=False)


def run(fixture: Path, snapshot_dir: Path) -> list[str]:
    """Render the fixture, check the page, and write snapshots when anything failed."""
    data = json.loads(fixture.read_text(encoding="utf-8"))
    title = str(data.get("title", "Service status"))
    expect = data.get("expect", {})
    try:
        services = [parse_service(raw) for raw in data.get("services", [])]
    except InvalidServiceError as exc:
        services, problems = [], [str(exc)]
    else:
        problems = []
    dom = parse_dom(render_board(services, title))
    problems += check(dom, title, services, expect)
    if problems:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / SNAPSHOT_NAME).write_text(snapshot_svg(dom, problems), encoding="utf-8")
        (snapshot_dir / SNAPSHOT_PNG_NAME).write_bytes(snapshot_png(dom, problems))
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entry point; returns the exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR)
    args = parser.parse_args(argv)
    problems = run(args.fixture, args.snapshot_dir)
    if problems:
        sys.stderr.write("ui-check failed:\n" + "".join(f"  - {p}\n" for p in problems))
        sys.stderr.write(f"snapshot written to {args.snapshot_dir / SNAPSHOT_NAME}\n")
        return 1
    sys.stdout.write(f"ui-check passed: {args.fixture}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
