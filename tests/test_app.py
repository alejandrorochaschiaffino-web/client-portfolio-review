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
    assert len(at.tabs) == 6
    assert metric(at, "In stocks") == "20%"          # Maria -> Conservative
    assert any("capped" in i.value for i in at.info)


def test_answers_survive_a_language_switch():
    at = start()
    at.radio(key="q_horizon_en").set_value(4).run()    # Maria now says 10+ years...
    assert metric(at, "In stocks") == "20%"            # ...but her goal is 2 years away: still capped
    assert any("goal is only 2 years away" in i.value for i in at.info)
    at.number_input(key="goal_years").set_value(20).run()
    assert metric(at, "In stocks") == "85%"            # score 25, no cap left: Growth
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


def test_reload_restores_the_sample_answers():
    at = start()
    at.radio(key="q_horizon_en").set_value(4).run()
    at.button(key="reload").click().run()
    assert at.radio(key="q_horizon_en").value == 1
    assert metric(at, "In stocks") == "20%"


def test_dollar_signs_are_escaped_on_screen():
    at = start()
    letter = next(m.value for m in at.markdown if "Your Portfolio Review" in m.value)
    assert "\\$" in letter and "$" not in letter.replace("\\$", "")


def test_no_ai_button_without_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = start()
    assert not [b for b in at.button if b.key == "ai_btn"]


@pytest.fixture
def fake_ai(monkeypatch):
    """Pretend an API key is set and replace the AI call (no network, no cost)."""
    import portfolio_tool.report as report
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    calls = []

    def fake(review, lang, api_key=None, client=None):
        calls.append(lang)
        if fake.ok:
            return report.template_report(review, lang, opening="A warm personal opening."), "ai"
        return report.template_report(review, lang), "template"
    fake.ok = True
    monkeypatch.setattr(report, "ai_report", fake)
    return fake, calls


def letter_text(at):
    return " ".join(m.value for m in at.markdown)


def test_ai_button_adds_the_personal_opening(fake_ai):
    fake, calls = fake_ai
    at = start()
    at.button(key="ai_btn").click().run()
    assert not at.exception
    assert calls == ["en"] and "A warm personal opening." in letter_text(at)
    assert at.button(key="ai_btn").disabled                  # no paying twice for the same letter
    assert any("not allowed to write numbers" in c.value for c in at.caption)


def test_failed_ai_keeps_the_letter_and_explains(fake_ai):
    fake, calls = fake_ai
    fake.ok = False
    at = start()
    at.button(key="ai_btn").click().run()
    assert any("safety checks" in w.value for w in at.warning)
    assert "Thank you for completing" in letter_text(at)


def test_session_ai_limit(fake_ai):
    fake, calls = fake_ai
    fake.ok = False
    at = start()
    for _ in range(5):
        at.button(key="ai_btn").click().run()
    assert len(calls) == 5
    assert at.button(key="ai_btn").disabled                  # disabled right after the 5th use


def test_goal_projection_tab():
    at = start()
    assert at.number_input(key="goal_target").value == 400_000      # Maria's sample goal
    assert any(m.value.startswith("## 8") for m in at.markdown)      # odds in the 80s
    at.number_input(key="goal_target").set_value(2_000_000).run()    # a goal she can't reach
    assert not at.exception
    assert any(m.value == "## 0%" for m in at.markdown)
    assert any("save about" in i.value for i in at.info)


def test_sample_switch_sets_the_goal_and_letter_mentions_it():
    at = start()
    at.sidebar.selectbox[0].set_value("Jordan Lee").run()
    assert at.number_input(key="goal_target").value == 1_000_000
    assert at.number_input(key="goal_years").value == 30
    text = " ".join(m.value for m in at.markdown)
    assert "Reaching your goal" in text and "10,000 possible futures" in text


def test_a_new_client_does_not_inherit_the_sample_goal():
    at = start()
    at.sidebar.text_input[0].set_value("John Smith").run()
    text = " ".join(m.value for m in at.markdown)
    assert "Reaching your goal" not in text                     # Maria's goal no longer applies
    assert any("No goal set for John Smith" in i.value for i in at.info)
    at.button(key="goal_use").click().run()
    assert "Reaching your goal" in " ".join(m.value for m in at.markdown)


def test_selling_everything_caps_and_explains():
    at = start()
    at.sidebar.selectbox[0].set_value("Jordan Lee").run()
    at.radio(key="q_drop_reaction_en").set_value(1).run()
    assert metric(at, "In stocks") == "40%"                     # Moderately Conservative
    assert any("sell everything after a 20% drop" in i.value for i in at.info)
