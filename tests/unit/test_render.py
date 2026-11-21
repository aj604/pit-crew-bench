from status_board.model import Service, Status
from status_board.render import BANNERS, render_board


def test_banner_and_cards() -> None:
    html = render_board([Service("web", Status.UP, 10), Service("db", Status.DOWN, 0)], "Prod")
    assert "<title>Prod</title>" in html
    assert 'data-overall="down"' in html
    assert BANNERS[Status.DOWN] in html
    assert html.count('<section class="card') == 2
    assert 'data-service="db" data-status="down"' in html


def test_names_are_escaped() -> None:
    html = render_board([Service("<script>", Status.UP, 1)], "a & b")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<title>a &amp; b</title>" in html
