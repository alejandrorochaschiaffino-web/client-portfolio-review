"""
The client review letter, in English or Spanish.

Two ways to write it:
1. Template (always available, free): fills the analysis into a fixed letter.
2. With AI touches (optional): Claude writes a personal opening and a
   plain-language summary. The AI is never allowed to write a number: both
   passages are rejected if they contain any digit, number word or promise
   about returns, and every figure in the letter still comes from the
   template. If anything fails, the plain template letter is used.
"""

from __future__ import annotations

import json
import logging
import math
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
        "dear": "Dear {name},", "client": "Client",
        "intro": "Thank you for completing your investor questionnaire. Here is a summary of the portfolio that fits your situation, how it has behaved in past markets, and what to expect.",
        "h_profile": "Your investor profile",
        "profile": "Your answers scored **{score} out of 28**, which places you in the **{profile}** profile. {desc}",
        "profile_capped": "Your answers scored **{score} out of 28**, which on its own points to the **{score_profile}** profile. {why} {desc}",
        "why_horizon": "Because you expect to need this money soon, we recommend the more cautious **{profile}** profile: there would be little time to recover from a large loss.",
        "why_goal": "Because your goal is only {years} away, we recommend the more cautious **{profile}** profile: there would be little time to recover from a large loss.",
        "why_losses": "Because you told us you would sell everything after a 20% drop, we recommend the more cautious **{profile}** profile: a mix you can stay with through a downturn will serve you better than one you might sell at the bottom.",
        "h_portfolio": "Your recommended portfolio",
        "portfolio_intro": "For your investment of **{amount}**, we recommend this mix of low-cost index funds ({stocks} in stocks):",
        "col_fund": "Fund", "col_class": "Asset class", "col_weight": "Weight", "col_amount": "Amount",
        "h_goal": "Reaching your goal",
        "goal": "Your goal is to have **{target}** in {years}. We simulated {n} possible futures for this portfolio, built from how it has actually behaved since {start}{saving}. You reached your goal in **{prob}** of them. In a typical future you would have about **{median}**; in a bad one (1 in 10), about **{low}**.",
        "goal_saving": ", with you adding **{monthly}** a month",
        "goal_on_track": "That puts your plan on track.",
        "goal_raise": "Saving about **{required}** a month in total would raise the odds to 80%.",
        "year": "{n} year", "years": "{n} years",
        "h_expect": "How it has behaved historically",
        "expect": "From {start} to {end}, this portfolio grew at an annualized rate of **{ret}**, with typical yearly swings (volatility) of about **{vol}**. At its worst it fell **{dd}** from a high point, a loss of **{dd_usd}** on your investment.",
        "h_crises": "How it handled past crises",
        "crisis_line": "**{crisis}:** {ret} ({usd} on your investment). {recovery} {note}",
        "recovered": "It was back to even about {m} months after the market peak.",
        "not_recovered": "It has not yet fully recovered.",
        "h_stay": "Why staying invested matters",
        "stay": "If you had invested {amount} at the October 2007 market peak, just before the 2008 crisis, and stayed invested, it would be worth about **{stayed}** today. Selling at the bottom and waiting a year to buy back in would have left about **{panicked}**: a cost of **{cost}** from one decision.",
        "h_timing": "If you will be withdrawing money",
        "timing": "Timing matters once withdrawals begin. Taking out **{wd}** a year for 10 years, with the 2008 crash at the start, would have left **{first}**. The exact same returns with the crash at the end would have left **{last}**. That is why we keep money you will need soon in safer investments.",
        "h_rates": "If interest rates change",
        "rates": "If interest rates rose by 1 percentage point, the bond and cash part of your portfolio would lose about **{up1}** in value. If rates fell by 1 point, it would gain about **{down1}**.",
        "h_summary": "In plain terms",
        "h_next": "Next steps",
        "next": "I would be glad to walk through this review with you, answer any questions, and adjust the plan if your situation changes.",
        "closing": "Sincerely,",
        "advisor": "Your advisor",
        "disclaimer": "This review is an educational example, not personalized investment advice. Past results do not guarantee future returns. Figures use historical index-fund prices through {through} and are before fees and taxes. The goal projection is a simulation, not a prediction, and is not adjusted for inflation.",
    },
    "es": {
        "title": "Revisión de su portafolio",
        "dear": "Estimado/a {name}:", "client": "cliente",
        "intro": "Gracias por completar su cuestionario de inversionista. A continuación encontrará un resumen del portafolio que se ajusta a su situación, cómo se ha comportado en mercados pasados y qué puede esperar.",
        "h_profile": "Su perfil de inversionista",
        "profile": "Sus respuestas sumaron **{score} de 28** puntos, con lo cual su perfil es **{profile}**. {desc}",
        "profile_capped": "Sus respuestas sumaron **{score} de 28** puntos, lo que por sí solo indica el perfil **{score_profile}**. {why} {desc}",
        "why_horizon": "Como espera necesitar este dinero pronto, le recomendamos el perfil más prudente **{profile}**: habría poco tiempo para recuperarse de una pérdida grande.",
        "why_goal": "Como su meta está a solo {years}, le recomendamos el perfil más prudente **{profile}**: habría poco tiempo para recuperarse de una pérdida grande.",
        "why_losses": "Como nos dijo que vendería todo tras una caída del 20%, le recomendamos el perfil más prudente **{profile}**: una combinación que pueda mantener durante una caída le servirá más que una que podría vender en el peor momento.",
        "h_portfolio": "Su portafolio recomendado",
        "portfolio_intro": "Para su inversión de **{amount}**, recomendamos esta combinación de fondos indexados de bajo costo ({stocks} en acciones):",
        "col_fund": "Fondo", "col_class": "Clase de activo", "col_weight": "Porcentaje", "col_amount": "Monto",
        "h_goal": "Cómo alcanzar su meta",
        "goal": "Su meta es tener **{target}** en {years}. Simulamos {n} futuros posibles para este portafolio, a partir de cómo se ha comportado realmente desde {start}{saving}. Alcanzó su meta en el **{prob}** de ellos. En un futuro típico tendría alrededor de **{median}**; en uno malo (1 de cada 10), alrededor de **{low}**.",
        "goal_saving": ", aportando **{monthly}** al mes",
        "goal_on_track": "Eso indica que su plan va por buen camino.",
        "goal_raise": "Ahorrar alrededor de **{required}** al mes en total subiría la probabilidad al 80%.",
        "year": "{n} año", "years": "{n} años",
        "h_expect": "Cómo se ha comportado históricamente",
        "expect": "De {start} a {end}, este portafolio creció a una tasa anualizada de **{ret}**, con altibajos anuales típicos (volatilidad) de alrededor de **{vol}**. En su peor momento cayó **{dd}** desde un punto máximo, una pérdida de **{dd_usd}** sobre su inversión.",
        "h_crises": "Cómo resistió crisis pasadas",
        "crisis_line": "**{crisis}:** {ret} ({usd} sobre su inversión). {recovery} {note}",
        "recovered": "Volvió a su valor inicial unos {m} meses después del punto máximo del mercado.",
        "not_recovered": "Todavía no se ha recuperado por completo.",
        "h_stay": "Por qué conviene mantenerse invertido",
        "stay": "Si hubiera invertido {amount} en el punto máximo del mercado de octubre de 2007, justo antes de la crisis de 2008, y se hubiera mantenido invertido, hoy valdría alrededor de **{stayed}**. Vender en el punto más bajo y esperar un año para volver a invertir habría dejado alrededor de **{panicked}**: un costo de **{cost}** por una sola decisión.",
        "h_timing": "Si va a retirar dinero",
        "timing": "El momento importa cuando empiezan los retiros. Retirando **{wd}** al año durante 10 años, con la caída de 2008 al principio, habrían quedado **{first}**. Los mismos rendimientos con la caída al final habrían dejado **{last}**. Por eso mantenemos en inversiones más seguras el dinero que necesitará pronto.",
        "h_rates": "Si cambian las tasas de interés",
        "rates": "Si las tasas de interés subieran 1 punto porcentual, la parte de bonos y efectivo de su portafolio perdería alrededor de **{up1}** de valor. Si bajaran 1 punto, ganaría alrededor de **{down1}**.",
        "h_summary": "En pocas palabras",
        "h_next": "Próximos pasos",
        "next": "Con gusto revisaré este análisis con usted, responderé sus preguntas y ajustaré el plan si su situación cambia.",
        "closing": "Atentamente,",
        "advisor": "Su asesor",
        "disclaimer": "Esta revisión es un ejemplo educativo y no constituye asesoría de inversión personalizada. Los resultados pasados no garantizan rendimientos futuros. Las cifras usan precios históricos de fondos indexados hasta el {through} y no incluyen comisiones ni impuestos. La proyección de la meta es una simulación, no una predicción, y no está ajustada por inflación.",
    },
}

MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _month_year(ts, lang):
    return f"{MONTHS_ES[ts.month - 1]} de {ts.year}" if lang == "es" else f"{ts:%b %Y}"


def _date(ts, lang):
    return f"{ts.day} de {MONTHS_ES[ts.month - 1]} de {ts.year}" if lang == "es" else f"{ts:%b} {ts.day}, {ts.year}"


_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>#|~])")


def md_escape(text: str) -> str:
    """Make user-typed text (the client name) show literally inside Markdown."""
    return _MD_SPECIAL.sub(r"\\\1", text)


def odds(p: float) -> str:
    """A probability as a whole percent, rounded DOWN so 79.6% never reads as 80%."""
    return f"{math.floor(p * 100 + 1e-9)}%"


def goal_paragraph(g: dict, start, lang: str) -> str:
    """The goal projection in one paragraph (also used by the PDF report)."""
    t = TEXT[lang]
    years = (t["year"] if g["years"] == 1 else t["years"]).format(n=g["years"])
    saving = t["goal_saving"].format(monthly=usd(g["monthly"])) if g["monthly"] > 0 else ""
    text = t["goal"].format(target=usd(g["goal"]), years=years, n=f"{g['n_paths']:,}",
                            start=_month_year(start, lang), saving=saving,
                            prob=odds(g["probability"]), median=usd(g["ending"][50]),
                            low=usd(g["ending"][10]))
    advice = (t["goal_on_track"] if g["probability"] >= 0.80
              else t["goal_raise"].format(required=usd(g["required_monthly"])))
    return text + " " + advice


def template_report(review: dict, lang: str = "en", opening: str | None = None,
                    summary: str | None = None) -> str:
    """
    The client letter as Markdown, filled in from build_review()'s results.
    opening / summary are optional number-free passages (see ai_report); the
    opening replaces the standard intro and the summary adds an extra section.
    """
    t = TEXT[lang]
    profile = PROFILE_NAMES[lang][review["profile"]]
    key = "profile_capped" if review["capped"] else "profile"
    why = ""
    if review["capped"]:
        years = review.get("goal_years") or 0
        why = t["why_" + (review.get("cap_reason") or "horizon")].format(
            profile=profile, years=(t["year"] if years == 1 else t["years"]).format(n=years))
    lines = [f"# {t['title']}", "", t["dear"].format(name=md_escape(review["name"]) or t["client"]), "",
             opening or t["intro"], "", f"## {t['h_profile']}", "",
             t[key].format(score=review["score"], profile=profile, why=why,
                           score_profile=PROFILE_NAMES[lang][review["score_profile"]],
                           desc=PROFILE_DESCRIPTIONS[lang][review["profile"]])]
    lines += ["", f"## {t['h_portfolio']}", "",
              t["portfolio_intro"].format(amount=usd(review["amount"]), stocks=f"{review['stock_share']:.0%}"),
              "", f"| {t['col_fund']} | {t['col_class']} | {t['col_weight']} | {t['col_amount']} |",
              "|---|---|---|---|"]
    for h in review["holdings"]:
        lines.append(f"| {h['ticker']} | {ASSET_CLASSES[lang][h['asset_class']]} | "
                     f"{h['weight']:.0%} | {usd(h['dollars'])} |")

    if review["has_history"]:
        s = review["stats"]
        g = review.get("goal")
        if g:
            lines += ["", f"## {t['h_goal']}", "", goal_paragraph(g, s["start"], lang)]
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
                                down1=usd(abs(shocks[-0.01]["total_dollar_change"])))]
    if summary:
        lines += ["", f"## {t['h_summary']}", "", summary]
    lines += ["", f"## {t['h_next']}", "", t["next"], "", t["closing"], "", t["advisor"], "",
              "---", ""]
    through = review.get("data_through")
    lines.append("*" + t["disclaimer"].format(
        through=_date(through, lang) if through is not None else "—") + "*")
    return "\n".join(lines)


# ------------------------------------------------------------- AI version
#
# Design: the AI never touches a number. It writes only two short, number-free
# passages (a personal opening and a plain-language summary). Every sentence
# with a figure in it comes from the template above, unchanged. Each AI passage
# is rejected if it contains a digit, a number word, a currency or percent sign,
# Markdown structure, or promise language ("guarantee", "will earn", ...).

log = logging.getLogger(__name__)

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
    """Numbers in one text that do NOT appear anywhere in a reference text."""
    return numbers_in(ai_text) - numbers_in(reference_text)


NUMBER_WORDS = {
    # "one" and "double" are left out: "one of the most important..." and "double-check"
    # are normal phrases, and on their own they can't misstate a figure.
    "en": r"zero|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
          r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
          r"eighty|ninety|hundreds?|thousands?|millions?|billions?|dozens?|percent|percentage|"
          r"half|halve[sd]|doubled|doubles|twice|triple[sd]?|quarters?|\w+fold|thirds?|fourths?|"
          r"fifths?|sixths?|sevenths?|eighths?|ninths?|tenths?|decades?|couple|dozen|"
          r"second|third|fourth|fifth",
    "es": r"cero|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|"
          r"dieci\w+|veinte|veinti\w+|treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|"
          r"cien|\w*cient[oa]s|quinient[oa]s|mil|miles|mill[oó]n|millones|docenas?|porcentaje|"
          r"por ciento|mitad|doble|triple|tercios?|cuartos?|quintos?|décimos?|medio|décadas?|"
          r"par de|segund[oa]|tercer[oa]?",
}

# Predictions and promises. Checked on lowercase text with curly apostrophes
# straightened. Negated disclaimers ("past results are no guarantee") are allowed.
_GAIN_EN = (r"grow|earn|gain|recover|rise|increase|outperform|beat|bounce|come back|pay off|"
            r"go up|make money|come out ahead|double|do well|be fine|be safe")
_GAIN_ES = (r"crec\w*|gan\w*|recuper\w*|sub\w*|aument\w*|rend\w*|duplic\w*|"
            r"valoriz\w*|vuelv\w*|salir ganando")
PROMISES = {
    "en": [rf"\b(?:will|'ll|going to|gonna|should|bound to|sure to|certain(?:ly)? to)\s+"
           rf"(?:\w+\s+){{0,2}}(?:{_GAIN_EN})",
           r"\balways\s+(?:\w+\s+)?(?:recover|come back|bounce|go up|rise|grow|win)",
           r"\bexpect\w*\s+(?:\w+\s+){0,2}(?:growth|gains?|returns?|profits?)",
           r"(?:can't|cannot|can not|won't|will not|never|impossible to)\s+(?:\w+\s+)?lose",
           r"risk[- ]?free|no risk|safe bet|sure thing|certain(?:ty)? of (?:gains|growth|returns)",
           rf"\blikely to\s+(?:\w+\s+)?(?:{_GAIN_EN})",
           r"\b(?:will|'ll|going to|should)\s+(?:\w+\s+){0,2}(?:keep|protect|shield|guard|secure|preserve)\b",
           r"\bprotects? you from|\bsafe from\b|\bkeeps? (?:your )?(?:money|savings|portfolio|investment) safe",
           r"\bexpect(?:s|ed)?\s+(?:\w+\s+){0,3}to\s+(?:grow|rise|gain|recover|increase|do well)"],
    "es": [r"\b(?:ganar|crecer|rendir|duplicar|subir|recuperar|aumentar|valorizar)[aá]n?\b",
           r"\bseguir[aá]n?\s+\w+(?:ando|iendo)\b",
           rf"\bvan? a\s+(?:\w+\s+)?(?:{_GAIN_ES})",
           r"\b(?:puede|podr[aá]|debe|deber[ií]a)\s+esperar\s+(?:\w+\s+)?"
           r"(?:ganancias?|rendimientos?|crecimiento|beneficios?)",
           r"\bsiempre\s+(?:se\s+)?(?:recuper|sub|vuelv|crec|gan)\w*",
           r"\b(?:no|nunca)\s+(?:\w+\s+)?(?:perder[aá]n?|(?:puede|podr[aá]|va a)\s+perder)\b",
           r"sin riesgo|cero riesgo|apuesta segura|seguro que",
           rf"\b(?:deber[ií]an?|podr[ií]an?)\s+(?:\w+\s+)?(?:{_GAIN_ES})",
           r"\bestar[aá]n?\s+(?:\w+\s+)?(?:segur|proteg|a salvo)",
           r"\bproteger[aá]n?\b|\bmantendr[aá]n? (?:su )?(?:dinero|inversi[oó]n|portafolio) (?:segur|a salvo)",
           r"\besperamos que\b|\bes probable que\s+(?:\w+\s+)?(?:crezc|gane|suba|se recupere)"],
}
GUARANTEE = r"guarant\w*|promis\w*|garantiz\w*|garant[ií]a\w*|promet\w*"
NEGATED = (r"\b(?:no|not|never|cannot|can't|don't|doesn't|isn't|aren't|won't|nunca|ni|sin)\b"
           r"(?:\W+\w+){0,1}?\W+(?:" + GUARANTEE + ")")
MAX_WORDS = 130


def unsafe_reason(text: str, lang: str, name: str = "") -> str | None:
    """Why an AI passage is unsafe to show, or None if it passes every check."""
    if not isinstance(text, str) or not text.strip():
        return "empty"
    if name:
        text = text.replace(name, "")          # a client name may contain digits
    if re.search(r"\d", text):
        return "digit"
    if re.search(r"[$%#|*_`<>\[\]\n\r]|https?:|www\.", text):
        return "symbol, link or markdown"
    if len(text.split()) > MAX_WORDS:
        return "too long"
    low = text.lower().replace("\u2019", "'").replace("\u2018", "'")
    if re.search(rf"\b(?:{NUMBER_WORDS[lang]})\b", low):
        return "number word"
    if any(re.search(p, low) for p in PROMISES[lang]):
        return "promise"
    if re.search(GUARANTEE, re.sub(NEGATED, " ", low)):
        return "promise"
    return None


HORIZON_WORDS = {1: "very soon", 2: "in the next few years", 3: "in the medium term",
                 4: "in the long term"}

PROMPT = """You help a financial advisor write the personal parts of a client portfolio review letter, in {language}.
The numbers, tables and analysis are written separately; you must not repeat or invent any of them.

Facts about the client (use only these):
- Name: {name}
- Recommended profile: {profile} ({desc})
- {capped}
- Needs the money: {horizon}
- Main goal: {goal}
- If the portfolio fell sharply, they said they would: {reaction}
- Investing experience: {experience}

Write two short passages:
1. "opening": two or three warm sentences that thank the client and say what the letter covers (their profile, how this mix has behaved in past downturns, and what interest-rate changes mean). Do not start with a greeting; "Dear ..." is added for you.
2. "summary": three to five sentences, in plain language, explaining why this mix fits the client's goal and timeline and what to keep in mind when markets fall.

Strict rules:
- NO numbers of any kind: no digits, no number words, no fractions or ordinals (not even "one", "half", "a third", "double" or "decade"), no dates, percentages or dollar amounts.
- No promises or predictions about returns or safety. Never say "guarantee", that the portfolio "will", "should" or is "likely to" grow, recover or keep money safe, or that it protects against losses.
- No advice beyond the facts above. Plain sentences only: no headings, lists, bold, or symbols.
- Under {words} words per passage.

Return the two passages with the write_letter_passages tool."""

# Asking for the passages through a "tool" makes the API hand back structured
# data ({"opening": ..., "summary": ...}) instead of free text we would have to
# parse; free text is still accepted as a fallback.
PASSAGES_TOOL = {
    "name": "write_letter_passages",
    "description": "Submit the personal opening and the plain-language summary for the client letter.",
    "input_schema": {
        "type": "object",
        "properties": {
            "opening": {"type": "string", "description": "Two or three warm sentences, no numbers."},
            "summary": {"type": "string", "description": "Three to five plain sentences, no numbers."},
        },
        "required": ["opening", "summary"],
    },
}


def _prompt(review: dict, lang: str) -> str:
    from .profiles import QUESTIONS
    opts = {q["id"]: q["answers"] for q in QUESTIONS}
    a = review["answers"]
    names = PROFILE_NAMES[lang]                 # so a Spanish letter uses the Spanish profile name
    because = {"horizon": "they need the money soon", "goal": "their goal is close",
               "losses": "they said they would sell everything after a large drop"}
    capped = (f"Their answers alone pointed to {names[review['score_profile']]}, but because "
              f"{because[review.get('cap_reason') or 'horizon']} the recommendation was lowered to "
              f"{names[review['profile']]}."
              if review["capped"] else "The recommendation matches their answers.")
    return PROMPT.format(
        language="Spanish (formal usted)" if lang == "es" else "English",
        name=review["name"], profile=names[review["profile"]],
        desc=PROFILE_DESCRIPTIONS["en"][review["profile"]], capped=capped,
        horizon=HORIZON_WORDS[a["horizon"]], goal=opts["goal"][a["goal"] - 1],
        reaction=opts["drop_reaction"][a["drop_reaction"] - 1],
        experience=opts["experience"][a["experience"] - 1], words=MAX_WORDS - 20)


def _parse(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        out = json.loads(match.group(0), strict=False)    # allow line breaks inside strings
    except ValueError:
        return None
    return out if isinstance(out, dict) else None


def _passages(msg) -> dict | None:
    """The {opening, summary} dict from the API reply: the tool call, else parsed text."""
    content = getattr(msg, "content", None) or []
    for block in content:
        if getattr(block, "type", "") == "tool_use" and isinstance(getattr(block, "input", None), dict):
            return block.input
    text = "".join(getattr(b, "text", "") for b in content if getattr(b, "type", "") == "text")
    return _parse(text)


def ai_report(review: dict, lang: str = "en", api_key: str | None = None,
              client=None) -> tuple:
    """
    Returns (letter, source). source is "ai" if Claude's opening and summary
    both passed every check, otherwise "template" (no key, an API error, or an
    unsafe passage). Numbers in the letter always come from the template.
    """
    draft = template_report(review, lang)
    if client is None:
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return draft, "template"
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key, timeout=30, max_retries=1)
        except Exception as e:                  # SDK missing or bad config
            log.warning("AI letter: could not create client (%s)", type(e).__name__)
            return draft, "template"
    prompt = _prompt(review, lang)
    try:
        msg = client.messages.create(
            model=AI_MODEL, max_tokens=700,
            tools=[PASSAGES_TOOL],
            tool_choice={"type": "tool", "name": PASSAGES_TOOL["name"]},
            messages=[{"role": "user", "content": prompt}])
    except Exception as e:
        log.warning("AI letter: API call failed (%s)", type(e).__name__)
        return draft, "template"
    parts = _passages(msg)
    if not parts:
        log.warning("AI letter: reply had no usable passages (stop_reason=%s)",
                    getattr(msg, "stop_reason", "?"))
        return draft, "template"
    # One paragraph each: line breaks become spaces (this also rules out Markdown
    # that only works at the start of a line, like lists or headings).
    opening, summary = (" ".join(p.split()) if isinstance(p, str) else p
                        for p in (parts.get("opening"), parts.get("summary")))
    for label, passage in (("opening", opening), ("summary", summary)):
        reason = unsafe_reason(passage, lang, review["name"])
        if reason:
            log.warning("AI letter: %s rejected (%s)", label, reason)
            return draft, "template"
    name = review["name"]
    if name:                                    # the name was exempt from the symbol check
        opening, summary = (p.replace(name, md_escape(name)) for p in (opening, summary))
    return template_report(review, lang, opening=opening.strip(), summary=summary.strip()), "ai"


def escape_dollars(text: str) -> str:
    """
    Escape $ so Markdown renderers that support math (Streamlit, GitHub) show
    "$400,000 ... $12,000" as money instead of a LaTeX formula. "\\$" renders
    as a plain dollar sign in any CommonMark viewer.
    """
    return re.sub(r"(?<!\\)\$", r"\\$", text)


def review_facts_json(review: dict) -> str:
    """Compact JSON of the review (useful for debugging or other tools)."""
    return json.dumps(review, default=str, indent=2)
