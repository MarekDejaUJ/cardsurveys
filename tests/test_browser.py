"""Browser tests of the widgets and of a complete multi-module survey (Playwright, Chromium).

Run with: python -m pytest -m browser
"""
from __future__ import annotations

import socket
import threading
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser

playwright_api = pytest.importorskip("playwright.sync_api")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    from werkzeug.serving import make_server

    from cardsurveys import create_app
    from cardsurveys.extensions import db
    from cardsurveys.models import User, utcnow
    from cardsurveys.seeds.demos import all_demos, tap_demo
    from cardsurveys.survey import bundle as bundles

    tmp: Path = tmp_path_factory.mktemp("browser")
    app = create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///" + (tmp / "b.sqlite3").as_posix(), "SECRET_KEY": "browser",
                      "MAIL_BACKEND": "file", "MAIL_DIR": str(tmp / "mail")})
    slugs = {}
    with app.app_context():
        db.create_all()
        u = User(email="admin@uj.edu.pl", role="admin", active=True, verified_at=utcnow())
        u.set_password("Browser-pass-1")
        db.session.add(u)
        db.session.flush()
        for name, b in all_demos():
            s = bundles.create_from_bundle(u, b, ["pl", "en"], is_demo=True)
            s.status = "open"
            slugs[name] = s.slug
        closing = tap_demo()
        for m in closing["modules"]:
            if m["key"] == "value":
                m.update(anchor_closes=True, attention_position="first",
                         anchor_note={"pl": "Karta odniesienia zamyka blok.", "en": "The reference card closes the block."})
        s = bundles.create_from_bundle(u, closing, ["pl", "en"])
        s.status = "open"
        slugs["tap_closing"] = s.slug
        db.session.commit()
    port = _free_port()
    srv = make_server("127.0.0.1", port, app, threaded=True)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield {"base": f"http://127.0.0.1:{port}/cards", "slugs": slugs, "app": app}
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


VIEWPORTS = {"desktop": {"width": 1280, "height": 900}, "phone": {"width": 390, "height": 844}}


@pytest.fixture(params=list(VIEWPORTS))
def page(request, browser):
    ctx = browser.new_context(viewport=VIEWPORTS[request.param], locale="en-US", has_touch=request.param == "phone")
    pg = ctx.new_page()
    errors: list[str] = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.errors = errors  # type: ignore[attr-defined]
    yield pg
    ctx.close()
    assert errors == [], errors


def test_tier_board_demo(server, page):
    page.goto(server["base"] + "/demo/board/tier_aside?lang=en")
    page.click("text=research question")
    page.click(".stratum[data-tier='0']")
    page.click("text=analysis")
    page.click(".stratum[data-tier='2']")
    page.click("text=literature review")
    page.click(".sidebin")
    txt = page.inner_text("#readout")
    assert "research question" in txt and "≺" in txt and "||" in txt


def test_arrow_board_refuses_a_circle(server, page):
    page.goto(server["base"] + "/demo/board/arrow?lang=en")
    page.click("g.card[data-card='0']")
    page.click("g.card[data-card='1']")
    page.click("g.card[data-card='1']")
    page.click("g.card[data-card='2']")
    assert page.locator("line.arrow.implied").count() == 1
    page.click("g.card[data-card='2']")
    page.click("g.card[data-card='0']")
    assert "would close a circle" in page.inner_text("#readout")


def test_pairs_and_plane_demos(server, page):
    page.goto(server["base"] + "/demo/board/pairs?lang=en")
    buttons = page.locator(".seg button[data-value='apart']")
    for i in range(buttons.count()):
        buttons.nth(i).click()
    assert "consistent arrangement" in page.inner_text("#readout")
    page.goto(server["base"] + "/demo/board/plane?lang=en")
    page.click(".chip >> nth=0")
    page.locator("svg.plane").click(position={"x": 60, "y": 200})
    assert page.locator("circle.dot").count() == 1


def test_polish_interface(server, page):
    page.goto(server["base"] + "/demo/board/pile?lang=pl")
    assert "Plansza stosów" in page.inner_text("h1")
    assert "karty do ułożenia" in page.inner_text("#boardArea").lower()


def _tap_all(page):
    page.wait_for_selector("button.tapcard:not(.done)")
    cards = page.locator("button.tapcard")
    n = cards.count()
    assert cards.nth(n - 1).get_attribute("class").find("anchor") >= 0 or page.locator("button.tapcard.anchor").count() == 0
    order = []
    for i in range(n):
        if "attention" in (cards.nth(i).get_attribute("class") or ""):
            continue
        order.append(i)
    for i in range(n):
        if "attention" in (cards.nth(i).get_attribute("class") or ""):
            order.append(i)
    for i in order:
        cards.nth(i).click()


def test_tap_widget_with_undo_gate_and_anchor(server, page):
    page.goto(server["base"] + f"/s/{server['slugs']['tap']}?lang=en")
    page.click("button[value='agree']")
    # practice block: three cards, no anchor
    page.locator("button.tapcard").nth(0).click()
    page.click("#undoTap")
    assert page.locator("button.tapcard.done").count() == 0
    _tap_all(page)
    page.click("#submitBlock")
    # first real block: anchor last, gate required
    cards = page.locator("button.tapcard")
    assert "anchor" in cards.nth(cards.count() - 1).get_attribute("class")
    _tap_all(page)
    assert page.locator("#submitBlock").is_disabled()
    page.check("input[name=gate][value=yes]")
    assert page.locator("#submitBlock").is_enabled()
    page.click("#submitBlock")
    assert "Block 2 of" in page.inner_text(".progress")


def test_tap_widget_closed_by_the_anchor(server, page):
    page.goto(server["base"] + f"/s/{server['slugs']['tap_closing']}?lang=en")
    page.click("button[value='agree']")
    _tap_all(page)
    with page.expect_navigation():
        page.click("#submitBlock")
    # first real block: the note on the reference card, one source, then the anchor closes the block
    assert "closes the block" in page.inner_text(".anchor-note")
    sources = page.locator("button.tapcard:not(.anchor):not(.attention)")
    assert sources.count() == 3
    sources.nth(0).click()
    page.locator("button.tapcard.anchor").click()
    assert page.locator("button.tapcard.tied").count() == 2
    assert page.locator("button.tapcard.tied").nth(0).is_disabled()
    assert "all equal" in page.inner_text(".taplist li.tied")
    page.check("input[name=gate][value=yes]")
    assert page.locator("#submitBlock").is_enabled()
    # undo reopens the block; tapping every source places the anchor last by itself
    page.click("#undoTap")
    assert page.locator("button.tapcard.tied").count() == 0 and page.locator("#submitBlock").is_disabled()
    sources.nth(1).click()
    sources.nth(2).click()
    assert "done" in page.locator("button.tapcard.anchor").get_attribute("class")
    assert page.inner_text("button.tapcard.anchor .tapno") == "4"
    assert page.locator("#submitBlock").is_enabled()
    with page.expect_navigation():
        page.click("#submitBlock")
    assert "Block 2 of" in page.inner_text(".progress")

def test_full_experiment_run(server, page):
    page.goto(server["base"] + f"/s/{server['slugs']['experiment']}?lang=en")
    page.click("button[value='agree']")
    page.check("input[name=level][value=phd]")
    assert page.locator("input[name=thesis_lang]").first.is_visible()
    page.check("input[name=level][value=ma]")
    assert not page.locator("input[name=thesis_lang]").first.is_visible()
    page.select_option("select[name=field]", "hum")
    page.click("button[type=submit]")
    if page.locator("input[name=choice]").count():
        page.check("input[name=choice] >> nth=0")
        page.click("button[type=submit]")
    assert page.locator(".stimulus").count() == 1
    page.click("button[type=submit]")
    for _ in range(7):
        _tap_all(page)
        page.check("input[name=gate][value=no]")
        with page.expect_navigation():
            page.click("#submitBlock")
    assert "About the study" in page.inner_text("h1") or page.locator("text=Thank you").count()
    page.click("button.primary")
    assert "Thank you" in page.inner_text("body")


def test_sob_survey_run(server, page):
    page.goto(server["base"] + f"/s/{server['slugs']['sob']}?lang=en")
    page.click("button[value='agree']")
    for _ in range(7):
        chips = page.locator("#sobArea .tray .chip")
        page.locator("#sobArea .tray .chip").nth(0).click()
        page.click(".stratum[data-tier='0']")
        page.locator("#sobArea .tray .chip").nth(0).click()
        page.click(".stratum[data-tier='1']")
        page.locator("#sobArea .tray .chip").nth(0).click()
        page.click(".sidebin")
        assert chips.count() == 0
        page.click("#submitBlock")
    assert "Thank you" in page.inner_text("body")


def test_board_survey_with_confirmation(server, page):
    page.goto(server["base"] + f"/s/{server['slugs']['board-arrow']}?lang=en")
    page.click("button[value='agree']")
    page.click("g.card[data-card='0']")
    page.click("g.card[data-card='1']")
    page.click("#submitBoard")
    radios = page.locator("input[value=unrelated]")
    for i in range(radios.count()):
        radios.nth(i).check()
    page.click("button[type=submit]")
    assert "Thank you" in page.inner_text("body")
