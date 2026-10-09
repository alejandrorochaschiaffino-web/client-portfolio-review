import pytest

from portfolio_tool.data import SNAPSHOT, load_snapshot
from portfolio_tool.report import (ai_report, invented_numbers, numbers_in,
                                   template_report, usd)
from portfolio_tool.review import build_review
from portfolio_tool.sample_clients import SAMPLE_CLIENTS

needs_data = pytest.mark.skipif(not SNAPSHOT.exists(), reason="no price snapshot yet")


def maria(prices=None):
    c = SAMPLE_CLIENTS[2]
    return build_review(c["name"], c["answers"], c["amount"], prices)


# ---------- Template letter ----------

@needs_data
@pytest.mark.parametrize("lang", ["en", "es"])
def test_template_contains_the_key_numbers(lang):
    r = maria(load_snapshot())
    text = template_report(r, lang)
    assert "Maria Gonzalez" in text
    for h in r["holdings"]:
        assert usd(h["dollars"]) in text
    for c in r["crises"]:
        assert usd(c["dollar_change"]) in text
    assert usd(r["crises"][0]["stayed"]) in text
    assert usd(r["sequence"]["crash_first"]["ending"]) in text


@needs_data
def test_capped_client_gets_the_explanation():
    r = maria(load_snapshot())
    assert r["capped"]
    assert "Moderate" in template_report(r, "en")      # what the score alone said
    assert "Moderado" in template_report(r, "es")


def test_template_works_without_price_history():
    r = maria(prices=None)
    for lang in ("en", "es"):
        text = template_report(r, lang)
        assert "$400,000" in text and "—" in text      # no history sections, no crash


@needs_data
def test_spanish_letter_is_actually_spanish():
    text = template_report(maria(load_snapshot()), "es")
    for phrase in ("Su perfil de inversionista", "Crisis financiera de 2008", "Atentamente"):
        assert phrase in text
    assert "Dear" not in text and "Sincerely" not in text


# ---------- Number safety check ----------

def test_numbers_are_normalized():
    assert numbers_in("$1,234 and 4.0% and 22 out of 28") == {"1234", "4", "22", "28"}


def test_invented_numbers_are_caught():
    ref = "You invested $400,000. It fell 10.3% in 2008."
    assert invented_numbers("You put in $400,000 and it dropped 10.3% in 2008.", ref) == set()
    assert invented_numbers("You put in $400,000 and it dropped 12% in 2008.", ref) == {"12"}
    assert invented_numbers("About $400k fell 10.3%", ref) == {"400"}     # rounding counts


class FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeClient:
    """Stands in for the Anthropic client so tests need no API key."""

    def __init__(self, reply=None, error=False):
        self.reply, self.error, self.calls = reply, error, 0
        self.messages = self

    def create(self, **kwargs):
        self.calls += 1
        if self.error:
            raise RuntimeError("API down")
        reply = self.reply(kwargs["messages"][0]["content"]) if callable(self.reply) else self.reply
        return type("Msg", (), {"content": [FakeBlock(reply)]})()


@needs_data
def test_ai_letter_used_when_numbers_match():
    r = maria(load_snapshot())
    draft = template_report(r, "en")
    warm = draft.replace("Thank you for completing", "Thanks so much for completing")
    text, source = ai_report(r, "en", client=FakeClient(warm))
    assert source == "ai" and "Thanks so much" in text


@needs_data
def test_ai_letter_rejected_if_it_changes_a_number():
    r = maria(load_snapshot())
    draft = template_report(r, "en")
    wrong = draft.replace(usd(r["crises"][0]["stayed"]), "$900,000")
    text, source = ai_report(r, "en", client=FakeClient(wrong))
    assert source == "template" and text == draft


def test_falls_back_without_key_or_on_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = maria()
    assert ai_report(r, "es")[1] == "template"
    assert ai_report(r, "en", client=FakeClient(error=True))[1] == "template"
    assert ai_report(r, "en", client=FakeClient(""))[1] == "template"
