import json
import struct
import zlib
from collections.abc import Mapping
from pathlib import Path

import pytest

from status_board.ui_check import DEFAULT_FIXTURE, SNAPSHOT_NAME, SNAPSHOT_PNG_NAME, Dom, main, run, snapshot_png

ROOT = Path(__file__).resolve().parents[2]


def _ihdr(png: bytes) -> tuple[int, int, int, int]:
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    length, tag, width, height, depth, color_type = struct.unpack(">I4sIIBB", png[8:26])
    assert (length, tag) == (13, b"IHDR")
    return width, height, depth, color_type


def test_default_fixture_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--fixture", str(ROOT / DEFAULT_FIXTURE), "--snapshot-dir", str(tmp_path)]) == 0
    assert "passed" in capsys.readouterr().out
    assert not (tmp_path / SNAPSHOT_NAME).exists()
    assert not (tmp_path / SNAPSHOT_PNG_NAME).exists()


def _fixture(tmp_path: Path, data: Mapping[str, object]) -> str:
    path = tmp_path / "board.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_failure_writes_snapshot(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = json.loads((ROOT / DEFAULT_FIXTURE).read_text(encoding="utf-8"))
    data["expect"] = {"cards": 5, "overall": "up"}
    snapshots = tmp_path / "snaps"
    assert main(["--fixture", _fixture(tmp_path, data), "--snapshot-dir", str(snapshots)]) == 1
    svg = (snapshots / SNAPSHOT_NAME).read_text(encoding="utf-8")
    assert svg.startswith("<svg")
    assert "4 cards rendered, expected 5" in svg
    assert "api: degraded" in svg
    png = (snapshots / SNAPSHOT_PNG_NAME).read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert _ihdr(png) == (640, 240, 8, 2)
    assert "banner shows" in capsys.readouterr().err


def test_snapshot_png_renders_banner_cards_and_failure_indicator() -> None:
    dom = Dom(
        title="Service status",
        banner={"data-overall": "operational"},
        cards=[
            {"data-service": "web", "data-status": "operational", "class": "card status-up"},
            {"data-service": "api", "data-status": "degraded", "class": "card status-degraded"},
            {"data-service": "db", "data-status": "outage", "class": "card"},
            {"data-service": "cache", "data-status": "unknown", "class": "card"},
        ],
    )
    png = snapshot_png(dom, ["card 'db' has inconsistent status 'outage'"])
    assert _ihdr(png) == (640, 240, 8, 2)
    idat_len = struct.unpack(">I", png[33:37])[0]
    assert png[37:41] == b"IDAT"
    raw = zlib.decompress(png[41 : 41 + idat_len])
    assert len(raw) == 240 * (1 + 640 * 3)
    assert bytes((0x1A, 0x7F, 0x37)) in raw
    assert bytes((0xCF, 0x22, 0x2E)) in raw


def test_malformed_service_is_reported(tmp_path: Path) -> None:
    data = {"title": "T", "services": [{"name": "db", "status": "sideways"}], "expect": {"cards": 0, "overall": "up"}}
    fixture = Path(_fixture(tmp_path, data))
    assert run(fixture, tmp_path)
    assert "unknown status" in (tmp_path / SNAPSHOT_NAME).read_text(encoding="utf-8")
    png = (tmp_path / SNAPSHOT_PNG_NAME).read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert _ihdr(png) == (640, 240, 8, 2)
