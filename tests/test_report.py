import json

import pytest

from portfolio_tool.data import SNAPSHOT, load_snapshot
from portfolio_tool.report import (TEXT, ai_report, escape_dollars, invented_numbers,
                                   numbers_in, template_report, unsafe_reason, usd)
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


class FakeToolBlock:
    type = "tool_use"

    def __init__(self, data):
        self.input = data


class FakeClient:
    """
    Stands in for the Anthropic client so tests need no API key. By default it
    answers through the tool, as the real API does with tool_choice; text=True
    makes it answer in plain text instead (the fallback path).
    """

    def __init__(self, reply=None, error=False, text=False):
        self.reply, self.error, self.text, self.calls, self.prompts = reply, error, text, 0, []
        self.kwargs = None
        self.messages = self

    def create(self, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        self.prompts.append(kwargs["messages"][0]["content"])
        if self.error:
            raise RuntimeError("API down")
        block = FakeBlock(self.reply)
        if not self.text:
            try:
                data = json.loads(self.reply)
            except (TypeError, ValueError):
                data = None
            if isinstance(data, dict):
                block = FakeToolBlock(data)
        return type("Msg", (), {"content": [block], "stop_reason": "tool_use"})()


def reply(opening, summary):
    return json.dumps({"opening": opening, "summary": summary})


GOOD_EN = reply("Thank you for taking the time to share your goals with me. This letter walks "
                "through the portfolio I recommend and how it has held up in hard markets.",
                "Because you will need this money soon, most of it sits in bonds and cash, "
                "which tend to move less than stocks. Downturns are normal; the plan is built "
                "so you are not forced to sell at a bad time.")
GOOD_ES = reply("Gracias por compartir sus objetivos conmigo. En esta carta le explico el "
                "portafolio que le recomiendo y cómo se ha comportado en mercados difíciles.",
                "Como necesitará este dinero pronto, la mayor parte está en bonos y efectivo, "
                "que suelen moverse menos que las acciones.")


@needs_data
@pytest.mark.parametrize("lang,good", [("en", GOOD_EN), ("es", GOOD_ES)])
def test_ai_passages_are_added_and_every_number_is_unchanged(lang, good):
    r = maria(load_snapshot())
    draft = template_report(r, lang)
    text, source = ai_report(r, lang, client=FakeClient(good))
    assert source == "ai"
    parts = json.loads(good)
    assert parts["opening"] in text and parts["summary"] in text
    assert TEXT[lang]["intro"] not in text                # opening replaced the intro
    assert TEXT[lang]["h_summary"] in text
    assert numbers_in(text) == numbers_in(draft)          # no number added or lost
    assert all(line in text for line in draft.splitlines() if any(ch.isdigit() for ch in line))


@pytest.mark.parametrize("opening", [
    "Your portfolio grew 7% last year.",                   # digit
    "You have about twenty years to go.",                  # number word
    "Half of your money is in bonds.",                     # fraction word
    "This mix will grow steadily over time.",              # prediction
    "We guarantee a smooth ride.",                         # promise
    "Your **Conservative** plan",                          # markdown
    "It costs $ nothing.",                                 # currency sign
    "",                                                    # empty
    " ".join(["word"] * 200),                              # too long
])
def test_unsafe_passages_fall_back_to_template(opening):
    r = maria()
    draft = template_report(r, "en")
    text, source = ai_report(r, "en", client=FakeClient(reply(opening, "Fine summary.")))
    assert (text, source) == (draft, "template")


def test_unsafe_spanish_passages_are_caught():
    assert unsafe_reason("Tiene veinte años por delante.", "es") == "number word"
    assert unsafe_reason("Le garantizamos buenos resultados.", "es") == "promise"
    assert unsafe_reason("Su portafolio crecerá mucho.", "es") == "promise"
    assert unsafe_reason("Una carta para usted, con todo detalle.", "es") is None   # "una" is fine
    assert unsafe_reason("Someone will call you.", "en") is None


def test_client_name_with_digits_is_allowed():
    assert unsafe_reason("Thank you, Client 2, for your time.", "en", name="Client 2") is None


def test_prompt_contains_no_numbers_to_copy():
    r = maria()
    fake = FakeClient(GOOD_EN)
    ai_report(r, "en", client=fake)
    facts = fake.prompts[0].split("Write two short passages")[0]
    assert not any(ch.isdigit() for ch in facts.replace(r["name"], ""))


def test_falls_back_without_key_or_on_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = maria()
    assert ai_report(r, "es")[1] == "template"
    assert ai_report(r, "en", client=FakeClient(error=True))[1] == "template"
    assert ai_report(r, "en", client=FakeClient(""))[1] == "template"
    assert ai_report(r, "en", client=FakeClient("not json"))[1] == "template"
    assert ai_report(r, "en", client=FakeClient('["a list"]'))[1] == "template"


def test_dollars_are_escaped_for_markdown():
    assert escape_dollars("$400,000 and -$3") == "\\$400,000 and -\\$3"
    assert escape_dollars(escape_dollars("$5")) == "\\$5"           # never double-escaped


def test_capped_wording_is_not_contradictory():
    text = template_report(maria(), "en")
    assert "points to the **Moderate** profile" in text
    assert "places you in" not in text                   # no "you are Moderate ... we recommend Conservative"
    assert "le recomendamos el perfil más prudente **Conservador**" in template_report(maria(), "es")


@pytest.mark.parametrize("lang,text", [
    ("en", "Your portfolio will likely grow over the long run."),
    ("en", "Markets have always recovered over time."),
    ("en", "It\u2019ll grow nicely and you\u2019ll come out ahead."),   # curly apostrophes
    ("en", "Stocks are going to recover."),
    ("en", "You can expect steady growth."),
    ("en", "You can\u2019t lose with this mix."),
    ("en", "There is zero chance of a big loss."),
    ("en", "It could grow fourfold."),
    ("en", "There's no doubt we guarantee it."),
    ("en", "Safe.\n\n---\nVisit the site."),                          # line-start markdown
    ("en", "Read more at https://example.com"),
    ("es", "Su dinero seguirá creciendo."),
    ("es", "Su dinero recuperará su valor."),
    ("es", "Va a crecer de forma segura."),
    ("es", "Puede esperar ganancias constantes."),
    ("es", "Son quinientos dólares."),
    ("es", "Su portafolio no perderá valor."),
    ("es", "Los mercados siempre se recuperan."),
    ("en", "Your portfolio is likely to grow over time."),
    ("en", "This mix will keep your money safe."),
    ("en", "This portfolio will protect you from big losses."),
    ("en", "About a third of your money is in stocks."),
    ("en", "Over the next decade it adds up."),
    ("en", "We expect your savings to grow."),
    ("es", "Su portafolio debería crecer."),
    ("es", "Su dinero estará seguro."),
    ("es", "Este portafolio protegerá su dinero."),
    ("es", "Un tercio está en acciones."),
    ("es", "En año y medio."),
    ("es", "Esperamos que su portafolio crezca."),
])
def test_promises_and_numbers_are_caught(lang, text):
    assert unsafe_reason(text, lang) is not None


@pytest.mark.parametrize("lang,text", [
    ("en", "Past results are not a guarantee of future returns."),
    ("en", "We never promise outcomes, and there is no guarantee."),
    ("en", "No one can predict markets."),
    ("en", "This is one of the most important parts."),
    ("en", "Please double-check the details with me."),
    ("en", "Prices can fall before they recover."),
    ("es", "Los resultados pasados no garantizan rendimientos futuros."),
    ("es", "Nadie puede predecir los mercados, y no hay garantía de resultados."),
    ("es", "Como necesitará este dinero pronto, la mayor parte está en bonos."),
    ("en", "Bonds tend to move less than stocks, which can soften a downturn."),
    ("en", "Because you will need this money soon, most of it is in bonds."),
    ("es", "Los bonos suelen moverse menos que las acciones."),
])
def test_normal_disclaimer_wording_is_allowed(lang, text):
    assert unsafe_reason(text, lang) is None


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_blank_name_uses_each_languages_own_word(raw):
    c = SAMPLE_CLIENTS[2]
    r = build_review(raw, c["answers"], c["amount"])
    assert "Dear Client," in template_report(r, "en")
    assert "Estimado/a cliente:" in template_report(r, "es")


def test_client_name_shows_literally_in_markdown():
    c = SAMPLE_CLIENTS[2]
    r = build_review("  *Ana* [x](http://x.com) <b>  ", c["answers"], c["amount"])
    text = template_report(r, "en")
    assert "Dear \\*Ana\\* \\[x\\](http://x.com) \\<b\\>," in text


def test_ai_passage_keeps_a_markdown_name_literal():
    c = SAMPLE_CLIENTS[2]
    r = build_review("Ana_Lee", c["answers"], c["amount"])
    text, source = ai_report(r, "en", client=FakeClient(reply(
        "Thank you, Ana_Lee, for sharing your goals with me.", "A calm, steady plan.")))
    assert source == "ai" and "Thank you, Ana\\_Lee," in text


def test_api_is_asked_for_structured_passages():
    fake = FakeClient(GOOD_EN)
    ai_report(maria(), "en", client=fake)
    assert fake.kwargs["tool_choice"] == {"type": "tool", "name": "write_letter_passages"}
    assert fake.kwargs["tools"][0]["input_schema"]["required"] == ["opening", "summary"]


def test_text_reply_with_line_breaks_and_code_fence_still_works():
    raw = '```json\n{"opening": "Thank you for sharing your goals.\nIt helps a lot.",\n "summary": "A calm, steady plan."}\n```'
    text, source = ai_report(maria(), "en", client=FakeClient(raw, text=True))
    assert source == "ai" and "A calm, steady plan." in text


@pytest.mark.parametrize("answers,reason,phrase_en,phrase_es", [
    (dict(horizon=4, goal=4, drop_reaction=1, experience=4, income=4, emergency_fund=4, tradeoff=4),
     "losses", "sell everything after a 20% drop", "vendería todo tras una caída del 20%"),
])
def test_cap_explanation_matches_the_reason(answers, reason, phrase_en, phrase_es):
    r = build_review("Ana", answers, 100_000)
    assert r["capped"] and r["cap_reason"] == reason and r["profile"] == "Moderately Conservative"
    assert phrase_en in template_report(r, "en") and phrase_es in template_report(r, "es")
    assert "need this money soon" not in template_report(r, "en")


def test_near_goal_caps_the_profile_and_says_why():
    c = SAMPLE_CLIENTS[0]                                   # Jordan: Growth on his answers
    goal = dict(c["goal"], years=2)
    r = build_review(c["name"], c["answers"], c["amount"], goal=goal)
    assert r["profile"] == "Conservative" and r["cap_reason"] == "goal"
    assert "your goal is only 2 years away" in template_report(r, "en")
    assert "su meta está a solo 2 años" in template_report(r, "es")
