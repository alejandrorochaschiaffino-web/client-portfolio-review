"""Click-through tests for the web app, run headlessly with Streamlit's AppTest."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from portfolio_tool.data import SNAPSHOT  # noqa: E402
from portfolio_tool.sample_clients import SAMPLE_CLIENTS  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")
pytestmark = pytest.mark.skipif(not SNAPSHOT.exists(), reason="no price snapshot yet")


def start():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def metric(at, label):
    return next(m.value for m in at.metric if m.label == label)


def test_app_loads_with_default_client():
    at = start()
    assert at.title[0].value == "Client Portfolio Review"
    assert len(at.tabs) == 5
    assert metric(at, "In stocks") == "20%"          # Maria -> Conservative
    assert any("capped" in i.value for i in at.info)


def test_answers_survive_a_language_switch():
    at = start()
    at.radio(key="q_horizon_en").set_value(4).run()    # Maria now has 10+ years
    assert metric(at, "In stocks") == "85%"            # score 22 -> 25: Growth, no cap
    at.sidebar.radio[0].set_value("Español").run()
    assert not at.exception
    assert at.radio(key="q_horizon_es").value == 4     # still selected in Spanish
    assert metric(at, "En acciones") == "85%"
    at.sidebar.radio[0].set_value("English").run()
    assert at.radio(key="q_horizon_en").value == 4     # and back again


def test_sample_client_fills_every_answer():
    at = start()
    jordan = next(c for c in SAMPLE_CLIENTS if c["name"] == "Jordan Lee")
    at.sidebar.selectbox[0].set_value("Jordan Lee").run()
    assert not at.exception
    for qid, pts in jordan["answers"].items():
        assert at.radio(key=f"q_{qid}_en").value == pts
    assert at.sidebar.text_input[0].value == "Jordan Lee"
    assert metric(at, "In stocks") == "85%"            # Growth


def test_spanish_letter_and_labels():
    at = start()
    at.sidebar.radio[0].set_value("Español").run()
    text = " ".join(m.value for m in at.markdown)
    assert "Revisión de su portafolio" in text and "Atentamente" in text
    assert at.title[0].value == "Revisión de portafolio para clientes"
