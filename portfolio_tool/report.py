"""
The client review letter, in English or Spanish.

Two ways to write it:
1. Template (always available, free): fills the analysis into a fixed letter.
2. AI-written (optional): Claude rewrites the letter in a warmer, more
   personal voice. A safety check then compares every number in the AI's
   letter against the numbers in the analysis. If the AI invented or changed
   ANY number, its letter is thrown away and the template is used instead.
"""

from __future__ import annotations

import json
import os
import re

from .i18n import ASSET_CLASSES, CRISIS_NAMES, CRISIS_NOTES, PROFILE_DESCRIPTIONS, PROFILE_NAMES

AI_MODEL = "claude-haiku-5-5"


def usd(x: float) -> str:
    x = round(x)
    return f"-${abs(x):,}" if x < 0 else f"${x:,}"


def pct(x: float) -> str:
    return f"{x:.1%}"


def months(x: float) -> str:
    return f"{round(x)}"


TEXT = {
    "en": {
        "title": "Your Portfolio Review",
        "dear": "Dear {name},",
        "intro": "Thank you for completing your investor questionnaire. Here is a summary of the portfolio that fits your situation, how it has behaved in past markets, and what to expect.",
        "h_profile": "Your investor profile",
        "profile": "Your answers scored **{score} out of 28**, which places you in the **{profile}** profile. {desc}",
        "capped": "Your answers alone pointed to a **{score_profile}** profile. Because you expect to need this money soon, we recommend **{profile}**: there would be little time to recover from a large loss.",
        "h_portfolio": "Your recommended portfolio",
        "portfolio_intro": "For your investment of **{amount}**, we recommend this mix of low-cost index funds ({stocks} in stocks):",
        "col_fund": "Fund", "col_class": "Asset class", "col_weight": "Weight", "col_amount": "Amount",
        "h_expect": "What to expect",
        "expect": "From {start} to {end}, this portfolio grew at an annualized rate of **{ret}** per year, with typical yearly swings (volatility) of about **{vol}**. At its worst it fell **{dd}** from a high point, a loss of **{dd_usd}** on your investment.",
        "h_crises": "How it handled past crises",
        "crisis_line": "**{crisis}:** {ret} ({usd} on your investment). {recovery} {note}",
        "recovered": "It was back to even about {m} months after the market peak.",
        "not_recovered": "It has not yet fully recovered.",
        "h_stay": "Why staying invested matters",
        "stay": "If you had invested {amount} at the 2008 peak and stayed invested, it would be worth about **{stayed}** today. Selling at the bottom and waiting a year to buy back in would have left about **{panicked}**: a cost of **{cost}** from one decision.",
        "h_timing": "If you will be withdrawing money",
        "timing": "Timing matters once withdrawals begin. Taking out **{wd}** a year for 10 years, with the 2008 crash at the start, would have left **{first}**. The exact same returns with the crash at the end would have left **{last}**. That is why we keep money you will need soon in safer investments.",
        "h_rates": "If interest rates change",
        "rates": "If interest rates rose by 1 percentage point, the bond and cash part of your portfolio would lose about **{up1}** in value. If rates fell by 1 point, it would gain about **{down1}**.",
        "h_next": "Next steps",
        "next": "I would be glad to walk through this review with you, answer any questions, and adjust the plan if your situation changes.",
        "closing": "Sincerely,",
        "advisor": "Your advisor",
        "disclaimer": "This review is for educational purposes and is not personalized investment advice. Past results do not guarantee future returns. Figures use historical prices through {through}, before fees and taxes.",
    },
    "es": {
        "title": "Revisión de su portafolio",
        "dear": "Estimado/a {name}:",
        "intro": "Gracias por completar su cuestionario de inversionista. A continuación encontrará un resumen del portafolio que se ajusta a su situación, cómo se ha comportado en mercados pasados y qué puede esperar.",
        "h_profile": "Su perfil de inversionista",
        "profile": "Sus respuestas sumaron **{score} de 28** puntos, con lo cual su perfil es **{profile}**. {desc}",
        "capped": "Sus respuestas por sí solas indicaban un perfil **{score_profile}**. Como espera necesitar este dinero pronto, le recomendamos **{profile}**: habría poco tiempo para recuperarse de una pérdida grande.",
        "h_portfolio": "Su portafolio recomendado",
        "portfolio_intro": "Para su inversión de **{amount}**, recomendamos esta combinación de fondos indexados de bajo costo ({stocks} en acciones):",
        "col_fund": "Fondo", "col_class": "Tipo de activo", "col_weight": "Porcentaje", "col_amount": "Monto",
        "h_expect": "Qué puede esperar",
        "expect": "De {start} a {end}, este portafolio creció a una tasa anualizada de **{ret}** por año, con altibajos anuales típicos (volatilidad) de alrededor de **{vol}**. En su peor momento cayó **{dd}** desde un punto máximo, una pérdida de **{dd_usd}** sobre su inversión.",
        "h_crises": "Cómo resistió crisis pasadas",
        "crisis_line": "**{crisis}:** {ret} ({usd} sobre su inversión). {recovery} {note}",
        "recovered": "Volvió a su valor inicial unos {m} meses después del punto máximo del mercado.",
        "not_recovered": "Todavía no se ha recuperado por completo.",
        "h_stay": "Por qué conviene mantenerse invertido",
        "stay": "Si hubiera invertido {amount} en el punto máximo de 2008 y se hubiera mantenido invertido, hoy valdría alrededor de **{stayed}**. Vender en el punto más bajo y esperar un año para volver a invertir habría dejado alrededor de **{panicked}**: un costo de **{cost}** por una sola decisión.",
        "h_timing": "Si va a retirar dinero",
        "timing": "El momento importa cuando empiezan los retiros. Retirando **{wd}** al año durante 10 años, con la caída de 2008 al principio, habrían quedado **{first}**. Los mismos rendimientos con la caída al final habrían dejado **{last}**. Por eso mantenemos en inversiones más seguras el dinero que necesitará pronto.",
        "h_rates": "Si cambian las tasas de interés",
        "rates": "Si las tasas de interés subieran 1 punto porcentual, la parte de bonos y efectivo de su portafolio perdería alrededor de **{up1}** de valor. Si bajaran 1 punto, ganaría alrededor de **{down1}**.",
        "h_next": "Próximos pasos",
        "next": "Con gusto revisaré este análisis con usted, responderé sus preguntas y ajustaré el plan si su situación cambia.",
        "closing": "Atentamente,",
        "advisor": "Su asesor",
        "disclaimer": "Esta revisión tiene fines educativos y no constituye asesoría de inversión personalizada. Los resultados pasados no garantizan rendimientos futuros. Las cifras usan precios históricos hasta el {through}, antes de comisiones e impuestos.",
    },
}

MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _month_year(ts, lang):
    return f"{MONTHS_ES[ts.month - 1]} de {ts.year}" if lang == "es" else f"{ts:%b %Y}"


def _date(ts, lang):
    return f"{ts.day} de {MONTHS_ES[ts.month - 1]} de {ts.year}" if lang == "es" else f"{ts:%b %-d, %Y}"


def template_report(review: dict, lang: str = "en") -> str:
    """The client letter as Markdown, filled in from build_review()'s results."""
    t = TEXT[lang]
    profile = PROFILE_NAMES[lang][review["profile"]]
    lines = [f"# {t['title']}", "", t["dear"].format(name=review["name"]), "", t["intro"], "",
             f"## {t['h_profile']}", "",
             t["profile"].format(score=review["score"], profile=profile,
                                 desc=PROFILE_DESCRIPTIONS[lang][review["profile"]])]
    if review["capped"]:
        lines += ["", t["capped"].format(score_profile=PROFILE_NAMES[lang][review["score_profile"]],
                                         profile=profile)]
    lines += ["", f"## {t['h_portfolio']}", "",
              t["portfolio_intro"].format(amount=usd(review["amount"]), stocks=f"{review['stock_share']:.0%}"),
              "", f"| {t['col_fund']} | {t['col_class']} | {t['col_weight']} | {t['col_amount']} |",
              "|---|---|---|---|"]
    for h in review["holdings"]:
        lines.append(f"| {h['ticker']} | {ASSET_CLASSES[lang][h['asset_class']]} | "
                     f"{h['weight']:.0%} | {usd(h['dollars'])} |")

    if review["has_history"]:
        s = review["stats"]
        lines += ["", f"## {t['h_expect']}", "",
                  t["expect"].format(start=_month_year(s["start"], lang), end=_month_year(s["end"], lang),
                                     ret=pct(s["annual_return"]), vol=pct(s["volatility"]),
                                     dd=pct(abs(s["max_drawdown"])),
                                     dd_usd=usd(abs(s["max_drawdown"]) * review["amount"])),
                  "", f"## {t['h_crises']}", ""]
        for c in review["crises"]:
            recovery = (t["recovered"].format(m=months(c["months_total"])) if c["recovered"]
                        else t["not_recovered"])
            lines.append("- " + t["crisis_line"].format(
                crisis=CRISIS_NAMES[lang][c["name"]], ret=pct(c["return"]),
                usd=usd(c["dollar_change"]), recovery=recovery,
                note=CRISIS_NOTES[lang][c["name"]]))
        c08 = review["crises"][0]
        lines += ["", f"## {t['h_stay']}", "",
                  t["stay"].format(amount=usd(review["amount"]), stayed=usd(c08["stayed"]),
                                   panicked=usd(c08["panicked"]), cost=usd(c08["panic_cost"]))]
        seq = review["sequence"]
        lines += ["", f"## {t['h_timing']}", "",
                  t["timing"].format(wd=usd(seq["yearly_withdrawal"]),
                                     first=usd(seq["crash_first"]["ending"]),
                                     last=usd(seq["crash_last"]["ending"]))]

    shocks = review["rate_shocks"]
    lines += ["", f"## {t['h_rates']}", "",
              t["rates"].format(up1=usd(abs(shocks[0.01]["total_dollar_change"])),
                                down1=usd(abs(shocks[-0.01]["total_dollar_change"]))),
              "", f"## {t['h_next']}", "", t["next"], "", t["closing"], "", t["advisor"], "",
              "---", ""]
    through = review.get("data_through")
    lines.append("*" + t["disclaimer"].format(
        through=_date(through, lang) if through is not None else "—") + "*")
    return "\n".join(lines)


# ------------------------------------------------------------- AI version

NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> set:
    """Every number in a text, normalized (commas removed, trailing .0 dropped)."""
    out = set()
    for raw in NUMBER.findall(text):
        n = raw.replace(",", "").rstrip(".")
        if "." in n:
            n = n.rstrip("0").rstrip(".")
        out.add(n)
    return out


def invented_numbers(ai_text: str, reference_text: str) -> set:
    """Numbers in the AI letter that do NOT appear anywhere in the reference letter."""
    return numbers_in(ai_text) - numbers_in(reference_text)


PROMPT = """You are helping a financial advisor write a client portfolio review letter.

Rewrite the draft letter below in a warmer, clearer, more personal voice for the client, in {language}.
Rules:
- Keep it under 450 words and keep every section heading and the table.
- Use ONLY the facts in the draft. Copy every number, dollar amount, percentage and date EXACTLY as written; do not round, convert or add numbers.
- Do not give advice beyond what the draft says, do not make promises about future returns, and keep the disclaimer at the end word for word.
- Write in plain language a non-expert understands. Return only the letter in Markdown.

Draft letter:
{draft}
"""


def ai_report(review: dict, lang: str = "en", api_key: str | None = None,
              client=None) -> tuple:
    """
    Returns (letter, source). source is "ai" if Claude's letter passed the
    number check, otherwise "template" (no key, an error, or invented numbers).
    """
    draft = template_report(review, lang)
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if client is None:
        if not api_key:
            return draft, "template"
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
        except Exception:
            return draft, "template"
    try:
        msg = client.messages.create(
            model=AI_MODEL, max_tokens=1500,
            messages=[{"role": "user", "content": PROMPT.format(
                language="Spanish" if lang == "es" else "English", draft=draft)}])
        text = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text").strip()
    except Exception:
        return draft, "template"
    if not text or invented_numbers(text, draft):
        return draft, "template"
    return text, "ai"


def review_facts_json(review: dict) -> str:
    """Compact JSON of the review (useful for debugging or other tools)."""
    return json.dumps(review, default=str, indent=2)
