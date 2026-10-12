"""
Real-browser checks (Playwright + Chromium) for things Streamlit's AppTest can't
see: what the browser actually shows after reruns. Skipped automatically when
Playwright or a browser isn't installed (for example in the weekly data job).
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from portfolio_tool.data import SNAPSHOT

sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not SNAPSHOT.exists(), reason="no price snapshot yet")


@pytest.fixture(scope="module")
def page():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "ANTHROPIC_API_KEY": ""}
    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true",
         "--server.port", str(port), "--browser.gatherUsageStats", "false"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with sync_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:                      # no browser installed
                pytest.skip(f"no Chromium: {e}")
            pg = browser.new_page(viewport={"width": 1400, "height": 1000})
            for _ in range(60):
                try:
                    pg.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
                    pg.wait_for_selector("text=Recommended profile", timeout=60000)
                    break
                except Exception:
                    time.sleep(1)
            yield pg
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)


def settle(pg):
    pg.wait_for_timeout(500)
    pg.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')",
                         timeout=60000)
    pg.wait_for_timeout(1500)


def sidebar(pg):
    return pg.locator('[data-testid="stSidebar"]')


def checked_answers(pg):
    boxes = sidebar(pg).locator("input[type=radio]:checked")
    labels = [boxes.nth(i).evaluate("e => e.closest('label').innerText") for i in range(boxes.count())]
    return labels[1:]                                   # first radio is the language


def profile(pg):
    return pg.locator("h4").first.inner_text()


def pick_sample(pg, name):
    sidebar(pg).locator('[data-testid="stSelectbox"]').first.click()
    pg.get_by_role("option", name=name).click()
    settle(pg)


def test_picking_a_sample_moves_the_buttons(page):
    pick_sample(page, "Carlos and Ana Rivera")
    assert checked_answers(page)[0] == "In 6 to 10 years"
    assert profile(page).endswith("Moderate")
    pick_sample(page, "Maria Gonzalez")
    assert checked_answers(page)[0] == "In less than 3 years"
    assert profile(page).endswith("Conservative")


def test_clicking_an_answer_changes_the_result(page):
    pick_sample(page, "Maria Gonzalez")
    sidebar(page).get_by_text("More than 10 years from now").click()
    settle(page)
    assert profile(page).endswith("Growth")             # score 22 -> 25, no horizon cap
    sidebar(page).get_by_text("Reload sample answers").click()
    settle(page)
    assert checked_answers(page)[0] == "In less than 3 years"
    assert profile(page).endswith("Conservative")


def test_language_switch_keeps_answers_and_open_tab(page):
    pick_sample(page, "Jordan Lee")
    page.get_by_role("tab", name="Client letter").click()
    settle(page)
    sidebar(page).get_by_text("Español").click()
    settle(page)
    assert page.get_by_role("tab", name="Carta al cliente").get_attribute("aria-selected") == "true"
    assert profile(page) == "Perfil recomendado: Crecimiento"
    assert "Precios: copia guardada hasta" in page.locator("body").inner_text()
    sidebar(page).get_by_text("English").click()
    settle(page)
    assert page.get_by_role("tab", name="Client letter").get_attribute("aria-selected") == "true"
    page.get_by_role("tab", name="Overview").click()
    settle(page)


def test_odd_client_names_render_safely(page):
    box = sidebar(page).get_by_label("Client name")
    box.fill("*Ana* $5")
    box.press("Enter")
    settle(page)
    page.get_by_role("tab", name="Client letter").click()
    settle(page)
    assert "Dear *Ana* $5," in page.locator("body").inner_text()
    box.fill("")
    box.press("Enter")
    settle(page)
    assert "Dear Client," in page.locator("body").inner_text()
    page.get_by_role("tab", name="Overview").click()
    sidebar(page).get_by_text("Reload sample answers").click()
    settle(page)


def goal_odds(pg):
    return pg.locator('[data-testid="stMarkdownContainer"] h2').filter(has_text="%").first.inner_text()


def test_goal_inputs_follow_samples_edits_and_language(page):
    pick_sample(page, "Jordan Lee")
    page.get_by_role("tab", name="Goal projection").click()
    settle(page)
    target = page.get_by_label("Goal ($)")
    assert target.input_value() == "1000000"
    assert goal_odds(page) == "66%"
    target.fill("20000000")
    target.press("Enter")
    settle(page)
    assert goal_odds(page) == "0%"                      # far out of reach
    sidebar(page).get_by_text("Español").click()
    settle(page)
    assert page.get_by_label("Meta ($)").input_value() == "20000000"   # survives the switch
    sidebar(page).get_by_text("English").click()
    settle(page)
    sidebar(page).get_by_text("Reload sample answers").click()
    settle(page)
    assert page.get_by_label("Goal ($)").input_value() == "1000000"
    page.get_by_role("tab", name="Overview").click()
    settle(page)


def test_pdf_download_works_in_both_languages(page):
    pick_sample(page, "Maria Gonzalez")
    for lang_label, button in (("English", "Download PDF report"), ("Español", "Descargar informe PDF")):
        sidebar(page).get_by_text(lang_label).click()
        settle(page)
        with page.expect_download(timeout=60000) as info:
            page.get_by_role("button", name=button).first.click()
        path = info.value.path()
        data = open(path, "rb").read()
        assert data.startswith(b"%PDF") and len(data) > 50_000
        assert info.value.suggested_filename.startswith("portfolio_review_Maria_Gonzalez_")
    sidebar(page).get_by_text("English").click()
    settle(page)
