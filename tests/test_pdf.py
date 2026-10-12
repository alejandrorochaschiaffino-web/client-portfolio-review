"""The PDF report: it builds, it says the right things, in the right language."""

import io

import pytest

pypdf = pytest.importorskip("pypdf")

from portfolio_tool.data import SNAPSHOT, load_snapshot  # noqa: E402
from portfolio_tool.pdf_report import build_pdf, md_inline  # noqa: E402
from portfolio_tool.report import odds, template_report, usd  # noqa: E402
from portfolio_tool.review import build_review  # noqa: E402
from portfolio_tool.sample_clients import SAMPLE_CLIENTS  # noqa: E402

needs_data = pytest.mark.skipif(not SNAPSHOT.exists(), reason="no price snapshot yet")


def review_for(i, prices=None, name=None):
    c = SAMPLE_CLIENTS[i]
    return build_review(name or c["name"], c["answers"], c["amount"], prices, c["goal"])


def pdf_text(data: bytes):
    reader = pypdf.PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text() for page in reader.pages)
    return reader, " ".join(text.split())


@pytest.fixture(scope="module")
def prices():
    return load_snapshot()


@needs_data
@pytest.mark.parametrize("lang", ["en", "es"])
def test_pdf_contains_the_key_numbers(prices, lang):
    r = review_for(2, prices)
    data = build_pdf(r, template_report(r, lang), lang)
    assert data.startswith(b"%PDF")
    reader, text = pdf_text(data)
    assert len(reader.pages) == 4
    assert "Maria Gonzalez" in text
    for h in r["holdings"]:
        assert usd(h["dollars"]) in text
    assert odds(r["goal"]["probability"]) in text
    assert usd(r["crises"][0]["dollar_change"]) in text
    assert usd(r["goal"]["ending"][50]) in text


@needs_data
def test_spanish_pdf_keeps_accents_and_has_no_english(prices):
    r = review_for(2, prices)
    reader, text = pdf_text(build_pdf(r, template_report(r, "es"), "es"))
    for phrase in ("Revisión de portafolio", "Proyección de la meta", "Cómo resistió", "Página 1",
                   "Atentamente"):
        assert phrase in text
    for english in ("Portfolio Review", "Goal projection", "Page 1", "Sincerely"):
        assert english not in text
    assert reader.metadata.title.startswith("Revisión de portafolio")


def test_pdf_without_price_history_still_builds():
    r = review_for(0)                                   # no prices: allocation + rates only
    reader, text = pdf_text(build_pdf(r, template_report(r, "en"), "en"))
    assert "Jordan Lee" in text and "If interest rates change" in text
    assert "Goal projection" not in text


@needs_data
def test_pdf_shows_odd_names_literally(prices):
    r = review_for(1, prices, name="*Ana* & <Bob> $5")
    _, text = pdf_text(build_pdf(r, template_report(r, "en"), "en"))
    assert "*Ana* & <Bob> $5" in text


def test_markdown_to_pdf_markup():
    assert md_inline("**$400,000** and *note*") == "<b>$400,000</b> and <i>note</i>"
    assert md_inline("\\*Ana\\* \\<b\\> \\$5 & co") == "*Ana* &lt;b&gt; $5 &amp; co"
    assert md_inline("2 * 3 * 4") == "2 * 3 * 4"            # lone asterisks aren't italics
