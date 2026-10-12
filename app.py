"""
Client Portfolio Review - web app.

Run locally:   streamlit run app.py
Optional:      set ANTHROPIC_API_KEY (env var or Streamlit secret) to enable
               the AI-written client letter. Without it the app uses the
               built-in bilingual template, so it always works for free.
"""

import datetime as dt
import inspect
import os
import re
import threading

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from portfolio_tool import data
from portfolio_tool.i18n import (ASSET_CLASSES, CRISIS_NAMES, CRISIS_NOTES,
                                 PROFILE_DESCRIPTIONS, PROFILE_NAMES, question_text)
from portfolio_tool.profiles import QUESTIONS
from portfolio_tool.projection import chart_floor
from portfolio_tool.pdf_report import build_pdf
from portfolio_tool.report import ai_report, escape_dollars, odds, template_report, usd
from portfolio_tool.review import build_review
from portfolio_tool.sample_clients import SAMPLE_CLIENTS

REPO_URL = "https://github.com/alejandrorochaschiaffino-web/client-portfolio-review"
MAX_AI_LETTERS = 5          # per visitor session
MAX_AI_PER_DAY = 100        # across all visitors; together these cap API cost at cents a day

# Validated categorical palette, fixed order (blue, orange, aqua, yellow).
ASSET_COLORS = {"US Stocks": "#2a78d6", "International Stocks": "#eb6834",
                "Bonds": "#1baf7a", "Cash & T-Bills": "#eda100"}
BLUE, ORANGE = "#2a78d6", "#eb6834"

UI = {
    "en": {
        "title": "Client Portfolio Review",
        "subtitle": "Answer seven questions to see a recommended portfolio, how it held up in real crises, and a client letter in English or Spanish.",
        "language": "Language", "sample": "Start from a sample client", "reload": "Reload sample answers",
        "name": "Client name", "amount": "Amount to invest ($)", "questions": "Investor questionnaire",
        "tabs": ["Overview", "Goal projection", "Crisis stress tests", "Client questions", "Interest rates", "Client letter"],
        "goal_title": "Will this plan reach the goal?",
        "goal_target": "Goal ($)", "goal_years": "Years", "goal_monthly": "Monthly savings ($)",
        "goal_headline": "chance of reaching **{target}** in {years}",
        "goal_median": "Typical outcome", "goal_low": "Bad case (1 in 10)", "goal_put_in": "Total you put in",
        "goal_median_help": "The middle result: half the simulated futures end above this, half below.",
        "goal_low_help": "Only 1 in 10 simulated futures ended lower than this.",
        "goal_band_wide": "8 in 10 futures", "goal_band_mid": "Middle half", "goal_line_median": "Typical",
        "goal_line_goal": "Goal", "goal_x": "Years from today", "goal_y": "Portfolio value ($)",
        "goal_levers": "What would raise the odds", "goal_change": "Change", "goal_chance": "Chance of reaching the goal",
        "goal_now": "Current plan", "goal_plus": "Save {extra} more a month", "goal_wait": "Give it 2 more years",
        "goal_on_track": "On track: the odds are already 80% or better.",
        "goal_need": "To reach an 80% chance, save about **{required}** a month in total.",
        "goal_method": "{n} simulated futures, each stitched together from real 12-month stretches of this portfolio's history since {start}. A simulation, not a prediction; before fees, taxes and inflation.",
        "goal_error": "Enter a goal, a number of years (1 to 50) and monthly savings to see the projection.",
        "profile": "Recommended profile", "score": "Risk score: {score} / 28",
        "capped": "The answers alone point to **{score_profile}**, but the money is needed soon, so the profile is capped at **{profile}** (suitability: little time to recover from a loss).",
        "ann": "Annualized return", "vol": "Volatility", "worst": "Worst fall", "stocks": "In stocks",
        "ann_help": "Compound growth rate per year, Jun 2007 to today, rebalanced monthly.",
        "vol_help": "Typical yearly swing: volatility of monthly returns, annualized.",
        "worst_help": "Largest drop from a previous high, using daily values.",
        "alloc": "Asset allocation", "holdings": "Holdings",
        "fund": "Fund", "class": "Asset class", "weight": "Weight", "dollars": "Amount",
        "crisis_title": "What this portfolio did in three real crises",
        "crisis_sub": "Invested at the market peak, measured at the market bottom. Dollar figures use this client's amount.",
        "crisis": "Crisis", "loss": "Loss", "loss_usd": "Loss ($)", "back": "Back to even", "note": "What happened",
        "back_fmt": "{date} ({m} months)", "not_yet": "Not yet",
        "panic_title": "\"Should I sell and wait it out?\"",
        "panic_sub": "Selling at the bottom and buying back a year later, vs. staying invested. Values today.",
        "stayed": "Stayed invested", "panicked": "Sold at bottom, back in 1 year later", "cost": "Cost of panicking",
        "seq_title": "\"Does it matter when a crash happens if I'm retired?\"",
        "seq_sub": "Withdrawing {wd} a year for 10 years. Same monthly returns, same average; only the order differs.",
        "crash_first": "Crash at the start (retired late 2007)", "crash_last": "Same returns, crash at the end",
        "years": "Years into retirement", "yrs": "years", "balance": "Balance ($)",
        "seq_result": "Timing alone made a **{diff}** difference: **{first}** left vs. **{last}**.",
        "rates_title": "If interest rates change",
        "rates_sub": "Bond price change ≈ −duration × change in rates. BND's average duration is 5.8 years; SGOV's about 0.1. Covers the bond and cash part of the portfolio.",
        "rate_change": "Change in rates", "value_change": "Change in value ($)", "pt": "pt",
        "letter_title": "Client letter", "write_ai": "Add a personal touch with AI (Claude)",
        "ai_on": "Claude wrote the opening and the \"In plain terms\" section. It is not allowed to write numbers: every figure comes straight from the analysis.",
        "ai_ready": "Template letter. The AI button adds a personal opening and a plain-language summary; it never changes a number.",
        "ai_off": "Template letter. Add an Anthropic API key to enable the AI personal touch.",
        "ai_fallback": "The AI text didn't pass the safety checks (or the API was unavailable), so the letter was not changed.",
        "ai_limit": "AI limit reached ({n} per session, or the daily limit for the demo).",
        "download": "Download letter (.md)", "pdf": "Download PDF report",
        "no_data": "Market data is unavailable right now, so only the allocation and rate shocks are shown.",
        "src_live": "live (Yahoo Finance)", "src_snap": "saved snapshot through {date}", "src_none": "unavailable",
        "footer": "Educational project, not investment advice. Prices: {source}. Past results don't guarantee future returns; figures are before fees and taxes. [Source code]({url})",
    },
    "es": {
        "title": "Revisión de portafolio para clientes",
        "subtitle": "Responda siete preguntas para ver un portafolio recomendado, cómo resistió crisis reales y una carta para el cliente en inglés o español.",
        "language": "Idioma", "sample": "Empezar con un cliente de ejemplo", "reload": "Restaurar respuestas del ejemplo",
        "name": "Nombre del cliente", "amount": "Monto a invertir ($)", "questions": "Cuestionario del inversionista",
        "tabs": ["Resumen", "Proyección de la meta", "Pruebas de estrés", "Preguntas del cliente", "Tasas de interés", "Carta al cliente"],
        "goal_title": "¿Alcanzará este plan la meta?",
        "goal_target": "Meta ($)", "goal_years": "Años", "goal_monthly": "Ahorro mensual ($)",
        "goal_headline": "de probabilidad de llegar a **{target}** en {years}",
        "goal_median": "Resultado típico", "goal_low": "Caso malo (1 de cada 10)", "goal_put_in": "Total aportado",
        "goal_median_help": "El resultado del medio: la mitad de los futuros simulados terminan por encima y la mitad por debajo.",
        "goal_low_help": "Solo 1 de cada 10 futuros simulados terminó por debajo de esta cifra.",
        "goal_band_wide": "8 de cada 10 futuros", "goal_band_mid": "Mitad central", "goal_line_median": "Típico",
        "goal_line_goal": "Meta", "goal_x": "Años a partir de hoy", "goal_y": "Valor del portafolio ($)",
        "goal_levers": "Qué subiría la probabilidad", "goal_change": "Cambio", "goal_chance": "Probabilidad de alcanzar la meta",
        "goal_now": "Plan actual", "goal_plus": "Ahorrar {extra} más al mes", "goal_wait": "Darle 2 años más",
        "goal_on_track": "Va por buen camino: la probabilidad ya es de 80% o más.",
        "goal_need": "Para llegar a 80% de probabilidad, ahorre alrededor de **{required}** al mes en total.",
        "goal_method": "{n} futuros simulados, cada uno armado con tramos reales de 12 meses de la historia de este portafolio desde {start}. Una simulación, no una predicción; antes de comisiones, impuestos e inflación.",
        "goal_error": "Ingrese una meta, un número de años (de 1 a 50) y el ahorro mensual para ver la proyección.",
        "profile": "Perfil recomendado", "score": "Puntaje de riesgo: {score} / 28",
        "capped": "Las respuestas por sí solas indican **{score_profile}**, pero el dinero se necesitará pronto, así que el perfil se limita a **{profile}** (idoneidad: poco tiempo para recuperarse de una pérdida).",
        "ann": "Rendimiento anualizado", "vol": "Volatilidad", "worst": "Peor caída", "stocks": "En acciones",
        "ann_help": "Tasa de crecimiento compuesta por año, de junio de 2007 a hoy, con rebalanceo mensual.",
        "vol_help": "Altibajo anual típico: volatilidad de los rendimientos mensuales, anualizada.",
        "worst_help": "Mayor caída desde un máximo previo, con valores diarios.",
        "alloc": "Asignación de activos", "holdings": "Inversiones",
        "fund": "Fondo", "class": "Clase de activo", "weight": "Porcentaje", "dollars": "Monto",
        "crisis_title": "Qué hizo este portafolio en tres crisis reales",
        "crisis_sub": "Invertido en el punto máximo del mercado, medido en el punto más bajo. Las cifras en dólares usan el monto de este cliente.",
        "crisis": "Crisis", "loss": "Pérdida", "loss_usd": "Pérdida ($)", "back": "Recuperación", "note": "Qué pasó",
        "back_fmt": "{date} ({m} meses)", "not_yet": "Todavía no",
        "panic_title": "\"¿Debería vender y esperar?\"",
        "panic_sub": "Vender en el punto más bajo y volver a invertir un año después, frente a mantenerse invertido. Valores de hoy.",
        "stayed": "Se mantuvo invertido", "panicked": "Vendió en el mínimo, volvió 1 año después", "cost": "Costo del pánico",
        "seq_title": "\"¿Importa cuándo ocurre una caída si estoy jubilado?\"",
        "seq_sub": "Retirando {wd} al año durante 10 años. Mismos rendimientos mensuales, mismo promedio; solo cambia el orden.",
        "crash_first": "Caída al inicio (jubilación a fines de 2007)", "crash_last": "Mismos rendimientos, caída al final",
        "years": "Años de jubilación", "yrs": "años", "balance": "Saldo ($)",
        "seq_result": "Solo el momento de la caída marcó una diferencia de **{diff}**: quedan **{first}** frente a **{last}**.",
        "rates_title": "Si cambian las tasas de interés",
        "rates_sub": "Cambio en el precio de un bono ≈ −duración × cambio en las tasas. La duración promedio de BND es 5.8 años; la de SGOV, cerca de 0.1. Cubre la parte de bonos y efectivo.",
        "rate_change": "Cambio en las tasas", "value_change": "Cambio de valor ($)", "pt": "pt",
        "letter_title": "Carta al cliente", "write_ai": "Agregar un toque personal con IA (Claude)",
        "ai_on": "Claude escribió la introducción y la sección \"En pocas palabras\". No puede escribir cifras: cada número viene directamente del análisis.",
        "ai_ready": "Carta de plantilla. El botón de IA agrega una introducción personal y un resumen sencillo; nunca cambia una cifra.",
        "ai_off": "Carta de plantilla. Agregue una clave de API de Anthropic para activar el toque personal con IA.",
        "ai_fallback": "El texto de la IA no pasó los controles de seguridad (o la API no estaba disponible), así que la carta no cambió.",
        "ai_limit": "Se alcanzó el límite de IA ({n} por sesión, o el límite diario de la demostración).",
        "download": "Descargar carta (.md)", "pdf": "Descargar informe PDF",
        "no_data": "Los datos de mercado no están disponibles ahora; solo se muestran la distribución y los cambios de tasas.",
        "src_live": "en vivo (Yahoo Finance)", "src_snap": "copia guardada hasta {date}", "src_none": "no disponibles",
        "footer": "Proyecto educativo, no es asesoría de inversión. Precios: {source}. Los resultados pasados no garantizan rendimientos futuros; las cifras son antes de comisiones e impuestos. [Código fuente]({url})",
    },
}

MONTHS_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MONTHS_ES_LONG = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                  "septiembre", "octubre", "noviembre", "diciembre"]


def month_year(ts, lang):
    return f"{MONTHS_ES[ts.month - 1]} {ts.year}" if lang == "es" else f"{ts:%b %Y}"


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_prices():
    try:
        return data.load_prices(live=True)
    except Exception:
        return None, "unavailable"


@st.cache_data(max_entries=200, show_spinner=False)
def cached_review(name, answers_items, amount, goal_items, data_version, _prices):
    """build_review() is the slow part; reruns with the same inputs reuse it."""
    return build_review(name, dict(answers_items), amount, _prices,
                        goal=dict(goal_items) if goal_items else None)


@st.cache_resource
def ai_counter():
    """Shared by every visitor of this server: today's date and AI calls so far."""
    return {"day": None, "count": 0, "lock": threading.Lock()}


def take_ai_slot() -> bool:
    c = ai_counter()
    with c["lock"]:
        today = dt.date.today()
        if c["day"] != today:
            c["day"], c["count"] = today, 0
        if c["count"] >= MAX_AI_PER_DAY:
            return False
        c["count"] += 1
        return True


def api_key():
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        key = None
    return key or os.environ.get("ANTHROPIC_API_KEY")


def signed_usd(x):
    return "+" + usd(x) if round(x) > 0 else usd(x)


CHART_CONFIG = {"displayModeBar": False}     # the hover toolbar overlaps titles on phones


def day_month_year(ts, lang):
    return f"{ts.day} de {MONTHS_ES_LONG[ts.month - 1]} de {ts.year}" if lang == "es" else f"{ts:%b} {ts.day}, {ts.year}"


def two_lines(label):
    """Break a chart label at the space nearest its middle, so it fits on a phone."""
    if " " not in label:
        return label
    mid = len(label) / 2
    cut = min((i for i, ch in enumerate(label) if ch == " "), key=lambda i: abs(i - mid))
    return label[:cut] + "<br>" + label[cut + 1:]


# Tabs keep their place when the language changes. Each language has its own
# tab widget (labels differ); the open tab's position is stored separately and
# the widget is driven only through its session-state key, like the radios.

def _remember_tab(lang):
    labels = UI[lang]["tabs"]
    st.session_state.tab_index = labels.index(st.session_state[f"tabs_{lang}"])


def language_tabs(lang):
    labels = UI[lang]["tabs"]
    if "key" not in inspect.signature(st.tabs).parameters:    # Streamlit < 1.52: no tab state
        return st.tabs(labels)
    other = "es" if lang == "en" else "en"
    st.session_state.pop(f"tabs_{other}", None)
    key = f"tabs_{lang}"
    if key not in st.session_state:
        st.session_state[key] = labels[st.session_state.get("tab_index", 0)]
    return st.tabs(labels, key=key, on_change=_remember_tab, args=(lang,))


def style(fig, height=360):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=-0.15), hoverlabel=dict(namelength=-1))
    return fig


# ------------------------------------------------------------------ sidebar

# The answers live in st.session_state.answers, separate from the radio
# buttons. Each language gets its own buttons (labels differ). The buttons are
# always driven through their session-state keys, never a default index:
# deleting a key and passing a new index leaves the browser showing the OLD
# selection (the bug where picking a sample client didn't move the buttons).

def _clear_answer_widgets(lang):
    for q in QUESTIONS:
        st.session_state.pop(f"q_{q['id']}_{lang}", None)


def _set_answer_widgets(answers):
    for code in ("en", "es"):
        for q in QUESTIONS:
            st.session_state[f"q_{q['id']}_{code}"] = answers[q["id"]]


def apply_sample():
    choice = st.session_state.sample
    for c in SAMPLE_CLIENTS:
        if c["name"] == choice:
            st.session_state.name = c["name"]
            st.session_state.amount = float(c["amount"])
            st.session_state.answers = dict(c["answers"])
            st.session_state.goal_target = float(c["goal"]["target"])
            st.session_state.goal_years = int(c["goal"]["years"])
            st.session_state.goal_monthly = float(c["goal"]["monthly"])
            _set_answer_widgets(c["answers"])


st.set_page_config(page_title="Client Portfolio Review", layout="wide", initial_sidebar_state="auto")

if "name" not in st.session_state:
    st.session_state.sample = SAMPLE_CLIENTS[2]["name"]
    apply_sample()

with st.sidebar:
    lang_label = st.radio("Language / Idioma", ["English", "Español"], horizontal=True)
    lang = "es" if lang_label == "Español" else "en"
    t = UI[lang]
    st.selectbox(t["sample"], [c["name"] for c in SAMPLE_CLIENTS], key="sample", on_change=apply_sample)
    st.button(t["reload"], on_click=apply_sample, key="reload")
    name = st.text_input(t["name"], key="name", max_chars=80)
    amount = st.number_input(t["amount"], min_value=1000.0, max_value=100_000_000.0,
                             step=5000.0, format="%.0f", key="amount")
    st.subheader(t["questions"])
    _clear_answer_widgets("es" if lang == "en" else "en")   # rebuilt from answers on switch
    answers = st.session_state.answers
    for q in QUESTIONS:
        text, options = question_text(q, lang)
        key = f"q_{q['id']}_{lang}"
        if key not in st.session_state:                     # first run, or just switched language
            st.session_state[key] = answers[q["id"]]
        answers[q["id"]] = st.radio(text, [1, 2, 3, 4], key=key,
                                    format_func=lambda p, o=options: o[p - 1])
    answers = dict(answers)

# ------------------------------------------------------------------ analysis

prices, source = load_prices()
data_version = (source, str(prices.index[-1])) if prices is not None else None
DEFAULT_GOAL = SAMPLE_CLIENTS[2]["goal"]
goal = {"target": float(st.session_state.get("goal_target", DEFAULT_GOAL["target"])),
        "years": int(st.session_state.get("goal_years", DEFAULT_GOAL["years"])),
        "monthly": float(st.session_state.get("goal_monthly", DEFAULT_GOAL["monthly"]))}
goal_ok = goal["target"] > 0 and 1 <= goal["years"] <= 50 and goal["monthly"] >= 0
review = cached_review(name, tuple(sorted(answers.items())), amount,
                       tuple(sorted(goal.items())) if goal_ok else None, data_version, prices)
profile = PROFILE_NAMES[lang][review["profile"]]

st.title(t["title"])
st.caption(t["subtitle"])
if prices is None:
    st.warning(t["no_data"])

# The letter for these exact inputs: an AI-assisted one if this visitor made
# one, otherwise the template. Keyed on everything the letter's numbers use.
letter_key = (name, amount, tuple(sorted(answers.items())), tuple(sorted(goal.items())), lang,
              str(review.get("data_through")))
letters = st.session_state.setdefault("letters", {})


def current_letter():
    return letters.get(letter_key, (template_report(review, lang), "template"))


def _downloads_take_callables() -> bool:
    """Newer Streamlit can build a download only when it's clicked."""
    try:
        from streamlit.elements.widgets.button import DownloadButtonDataType
        return "Callable" in str(DownloadButtonDataType)
    except Exception:                                    # internal name moved: play safe
        return False


CALLABLE_DOWNLOADS = _downloads_take_callables()


@st.cache_data(max_entries=50, show_spinner=False)
def cached_pdf(key, _review, letter_text, lang_):
    return build_pdf(_review, letter_text, lang_)


def pdf_button(key):
    """PDF of the current review and letter, built only when someone clicks (if supported)."""
    letter_text = current_letter()[0]
    snapshot, lang_ = review, lang
    if CALLABLE_DOWNLOADS:
        data = lambda: build_pdf(snapshot, letter_text, lang_)   # noqa: E731
    else:                                                        # older Streamlit: build now, cached
        data = cached_pdf((letter_key, letter_text), snapshot, letter_text, lang_)
    safe = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") or "client"
    st.download_button(t["pdf"], data, file_name=f"portfolio_review_{safe}_{lang}.pdf",
                       mime="application/pdf", key=key, type="primary", icon=":material/picture_as_pdf:")


tabs = language_tabs(lang)

# Overview -----------------------------------------------------------------
with tabs[0]:
    left, right = st.columns([3, 2])
    with left:
        st.markdown(f"#### {t['profile']}: {profile}")
        st.caption(t["score"].format(score=review["score"]))
        st.write(PROFILE_DESCRIPTIONS[lang][review["profile"]])
        if review["capped"]:
            st.info(t["capped"].format(score_profile=PROFILE_NAMES[lang][review["score_profile"]],
                                       profile=profile))
        if review["has_history"]:
            s = review["stats"]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(t["ann"], f"{s['annual_return']:.1%}", help=t["ann_help"])
            c2.metric(t["vol"], f"{s['volatility']:.1%}", help=t["vol_help"])
            c3.metric(t["worst"], f"{s['max_drawdown']:.1%}", help=t["worst_help"])
            c4.metric(t["stocks"], f"{review['stock_share']:.0%}")
        pdf_button("pdf_overview")
        st.markdown(f"##### {t['holdings']}")
        st.dataframe(pd.DataFrame([{
            t["fund"]: h["ticker"], t["class"]: ASSET_CLASSES[lang][h["asset_class"]],
            t["weight"]: f"{h['weight']:.0%}", t["dollars"]: usd(h["dollars"])}
            for h in review["holdings"]]), hide_index=True, width="stretch")
    with right:
        st.markdown(f"##### {t['alloc']}")
        classes = {}
        for h in review["holdings"]:
            classes[h["asset_class"]] = classes.get(h["asset_class"], 0) + h["dollars"]
        fig = go.Figure(go.Pie(
            labels=[ASSET_CLASSES[lang][k] for k in classes], values=list(classes.values()),
            marker=dict(colors=[ASSET_COLORS[k] for k in classes], line=dict(color="white", width=2)),
            hole=0.55, sort=False, textinfo="percent", textposition="outside",
            hovertemplate="%{label}<br>$%{value:,.0f} (%{percent})<extra></extra>"))
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"))
        fig = style(fig, 380)
        fig.update_layout(margin=dict(l=40, r=40, t=30, b=10))
        st.plotly_chart(fig, width="stretch", theme="streamlit", config=CHART_CONFIG)

# Goal projection ----------------------------------------------------------
with tabs[1]:
    st.markdown(f"#### {t['goal_title']}")
    g1, g2, g3 = st.columns(3)
    g1.number_input(t["goal_target"], min_value=1000.0, max_value=1_000_000_000.0, step=10_000.0,
                    format="%.0f", key="goal_target")
    g2.number_input(t["goal_years"], min_value=1, max_value=50, step=1, key="goal_years")
    g3.number_input(t["goal_monthly"], min_value=0.0, max_value=1_000_000.0, step=50.0,
                    format="%.0f", key="goal_monthly")
    g = review.get("goal")
    if not review["has_history"]:
        st.info(t["no_data"])
    elif not g:
        st.info(t["goal_error"])
    else:
        years_txt = (f"{g['years']} " + ("year" if g["years"] == 1 else "years") if lang == "en"
                     else f"{g['years']} " + ("año" if g["years"] == 1 else "años"))
        st.markdown(f"## {odds(g['probability'])}")
        st.markdown(escape_dollars(t["goal_headline"].format(target=usd(g["goal"]), years=years_txt)))
        m1, m2, m3 = st.columns(3)
        m1.metric(t["goal_median"], usd(g["ending"][50]), help=t["goal_median_help"])
        m2.metric(t["goal_low"], usd(g["ending"][10]), help=t["goal_low_help"])
        m3.metric(t["goal_put_in"], usd(g["contributed"]))

        x = [m / 12 for m in range(g["months"] + 1)]
        b = g["bands"]
        fig = go.Figure()
        for lo, hi, label, alpha in ((10, 90, t["goal_band_wide"], 0.18), (25, 75, t["goal_band_mid"], 0.35)):
            fig.add_trace(go.Scatter(x=x, y=b[hi], mode="lines", line=dict(width=0),
                                     showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=x, y=b[lo], mode="lines", line=dict(width=0), fill="tonexty",
                                     fillcolor=f"rgba(42,120,214,{alpha})", name=label, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=x, y=b[50], mode="lines", line=dict(color=BLUE, width=2),
                                 name=t["goal_line_median"],
                                 hovertemplate="%{x:.1f} " + t["yrs"] + ": $%{y:,.0f}<extra></extra>"))
        fig.add_hline(y=g["goal"], line=dict(color=ORANGE, width=2, dash="dash"),
                      annotation_text=f"{t['goal_line_goal']}: {usd(g['goal'])}",
                      annotation_position="top left")
        fig.update_xaxes(title=t["goal_x"])
        top = max(max(b[90]), g["goal"]) * 1.05
        fig.update_yaxes(title=t["goal_y"], tickformat="$,.0f", range=[chart_floor(g), top])
        fig = style(fig, 400)
        fig.update_layout(legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
                          margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, width="stretch", theme="streamlit", config=CHART_CONFIG)

        st.markdown(f"##### {t['goal_levers']}")
        lev = g["levers"]
        rows = [(t["goal_now"], g["probability"])]
        rows += [(t["goal_plus"].format(extra=usd(e)), lev[f"plus_{e}"]) for e in (100, 250, 500)]
        rows.append((t["goal_wait"], lev["plus_2_years"]))
        st.dataframe(pd.DataFrame([{t["goal_change"]: r, t["goal_chance"]: odds(p)} for r, p in rows]),
                     hide_index=True, width="stretch")
        if g["probability"] >= 0.80:
            st.success(t["goal_on_track"])
        else:
            st.info(escape_dollars(t["goal_need"].format(required=usd(g["required_monthly"]))))
        st.caption(t["goal_method"].format(n=f"{g['n_paths']:,}",
                                           start=month_year(review["stats"]["start"], lang)))

# Crisis stress tests ------------------------------------------------------
with tabs[2]:
    st.markdown(f"#### {t['crisis_title']}")
    st.caption(t["crisis_sub"])
    if review["has_history"]:
        crises = review["crises"]
        names = [CRISIS_NAMES[lang][c["name"]] for c in crises]
        fig = go.Figure(go.Bar(
            y=[two_lines(n) for n in names], x=[c["dollar_change"] for c in crises], orientation="h",
            marker=dict(color=BLUE, cornerradius=4),
            text=[f"{usd(c['dollar_change'])} ({c['return']:.1%})" for c in crises],
            textposition="inside", insidetextanchor="start", textfont=dict(color="white"),
            hovertemplate="%{y}<br>%{text}<extra></extra>"))
        fig.update_xaxes(tickformat="$,.0f", zeroline=True)
        fig.update_yaxes(autorange="reversed")
        fig = style(fig, 280)
        fig.update_layout(margin=dict(l=10, r=30, t=10, b=10))      # keeps the "$0" tick on screen
        st.plotly_chart(fig, width="stretch", theme="streamlit", config=CHART_CONFIG)
        st.dataframe(pd.DataFrame([{
            t["crisis"]: CRISIS_NAMES[lang][c["name"]],
            t["loss"]: f"{c['return']:.1%}", t["loss_usd"]: usd(c["dollar_change"]),
            t["back"]: (t["back_fmt"].format(date=month_year(c["recovery_date"], lang),
                                             m=round(c["months_total"]))
                        if c["recovered"] else t["not_yet"]),
            t["note"]: CRISIS_NOTES[lang][c["name"]]} for c in crises]),
            hide_index=True, width="stretch")
    else:
        st.info(t["no_data"])

# Client questions ---------------------------------------------------------
with tabs[3]:
    if review["has_history"]:
        crises = review["crises"]
        names = [CRISIS_NAMES[lang][c["name"]] for c in crises]
        st.markdown(f"#### {t['panic_title']}")
        st.caption(t["panic_sub"])
        short = [two_lines(n) for n in names]
        fig = go.Figure([
            go.Bar(name=t["stayed"], x=short, y=[c["stayed"] for c in crises],
                   marker=dict(color=BLUE, cornerradius=4),
                   text=[usd(c["stayed"]) for c in crises], textposition="outside"),
            go.Bar(name=t["panicked"], x=short, y=[c["panicked"] for c in crises],
                   marker=dict(color=ORANGE, cornerradius=4),
                   text=[usd(c["panicked"]) for c in crises], textposition="outside"),
        ])
        fig.update_traces(cliponaxis=False, hovertemplate="%{x}<br>%{fullData.name}: %{text}<extra></extra>")
        top = max(max(c["stayed"], c["panicked"]) for c in crises)
        fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
        fig.update_xaxes(tickangle=0)
        fig.update_yaxes(tickformat="$,.0f", range=[0, top * 1.15])   # room for the value labels
        fig = style(fig, 400)
        fig.update_layout(legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0),
                          margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, width="stretch", theme="streamlit", config=CHART_CONFIG)
        st.dataframe(pd.DataFrame([{t["crisis"]: n, t["cost"]: usd(c["panic_cost"])}
                                   for n, c in zip(names, crises)]),
                     hide_index=True, width="stretch")

        seq = review["sequence"]
        st.markdown(f"#### {t['seq_title']}")
        st.caption(escape_dollars(t["seq_sub"].format(wd=usd(seq["yearly_withdrawal"]))))
        fig = go.Figure()
        for key, label, color in (("crash_last", t["crash_last"], BLUE),
                                  ("crash_first", t["crash_first"], ORANGE)):
            path = seq[key]["path"]
            fig.add_trace(go.Scatter(x=[m / 12 for m in range(len(path))], y=path, name=label,
                                     mode="lines", line=dict(color=color, width=2),
                                     hovertemplate="%{x:.1f} " + t["yrs"] + ": $%{y:,.0f}<extra>"
                                                   + label + "</extra>"))
        fig.update_layout(hovermode="x unified")
        fig.update_xaxes(title=t["years"], dtick=1)
        fig.update_yaxes(title=t["balance"], tickformat="$,.0f")
        st.plotly_chart(style(fig, 380), width="stretch", theme="streamlit", config=CHART_CONFIG)
        st.markdown(escape_dollars(t["seq_result"].format(diff=usd(abs(seq["difference"])),
                                                          first=usd(seq["crash_first"]["ending"]),
                                                          last=usd(seq["crash_last"]["ending"]))))
    else:
        st.info(t["no_data"])

# Interest rates -----------------------------------------------------------
with tabs[4]:
    st.markdown(f"#### {t['rates_title']}")
    st.caption(t["rates_sub"])
    shocks = review["rate_shocks"]
    order = [-0.01, 0.01, 0.02]
    fig = go.Figure(go.Bar(
        x=[f"{c * 100:+.0f} {t['pt']}" for c in order], y=[shocks[c]["total_dollar_change"] for c in order],
        marker=dict(color=BLUE, cornerradius=4),
        text=[signed_usd(shocks[c]["total_dollar_change"]) for c in order], textposition="outside",
        cliponaxis=False, hovertemplate="%{x}: %{text}<extra></extra>"))
    fig.update_xaxes(title=t["rate_change"], type="category")
    fig.update_yaxes(title=t["value_change"], tickformat="$,.0f", zeroline=True)
    st.plotly_chart(style(fig, 320), width="stretch", theme="streamlit", config=CHART_CONFIG)

# Client letter ------------------------------------------------------------
with tabs[5]:
    st.markdown(f"#### {t['letter_title']}")
    letter, source_kind = current_letter()

    key = api_key()
    if key:
        used = st.session_state.get("ai_used", 0)
        if st.button(t["write_ai"], key="ai_btn", disabled=used >= MAX_AI_LETTERS or source_kind == "ai"):
            if take_ai_slot():
                st.session_state.ai_used = used + 1
                with st.spinner("Claude..."):
                    new_letter, new_kind = ai_report(review, lang, api_key=key)
                if new_kind == "ai":
                    letters[letter_key] = (new_letter, new_kind)
                else:
                    st.session_state.ai_notice = "ai_fallback"
            else:
                st.session_state.ai_notice = "ai_limit"
            st.rerun()                         # redraw with the new letter and counts
        notice = st.session_state.pop("ai_notice", None)
        if notice:
            st.warning(t[notice].format(n=MAX_AI_LETTERS))
        elif used >= MAX_AI_LETTERS:
            st.caption(t["ai_limit"].format(n=MAX_AI_LETTERS))
    st.caption(t["ai_on"] if source_kind == "ai" else t["ai_ready"] if key else t["ai_off"])
    pdf_button("pdf_letter")
    st.download_button(t["download"], letter, file_name=f"portfolio_review_{lang}.md",
                       mime="text/markdown")
    safe = escape_dollars(letter)              # on screen, "$" would otherwise start a LaTeX formula
    with st.container(border=True):
        shown = "\n".join(("#### " + line[3:]) if line.startswith("## ") else
                           ("### " + line[2:]) if line.startswith("# ") else line
                           for line in safe.splitlines())
        st.markdown(shown)

st.divider()
if prices is None:
    source_text = t["src_none"]
elif source.startswith("live"):
    source_text = t["src_live"]
else:
    source_text = t["src_snap"].format(date=day_month_year(prices.index[-1], lang))
st.caption(t["footer"].format(source=source_text, url=REPO_URL))
