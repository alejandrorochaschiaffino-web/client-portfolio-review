"""
Client Portfolio Review - web app.

Run locally:   streamlit run app.py
Optional:      set ANTHROPIC_API_KEY (env var or Streamlit secret) to enable
               the AI-written client letter. Without it the app uses the
               built-in bilingual template, so it always works for free.
"""

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from portfolio_tool import data
from portfolio_tool.i18n import (ASSET_CLASSES, CRISIS_NAMES, CRISIS_NOTES,
                                 PROFILE_DESCRIPTIONS, PROFILE_NAMES, question_text)
from portfolio_tool.profiles import QUESTIONS
from portfolio_tool.report import ai_report, template_report, usd
from portfolio_tool.review import build_review
from portfolio_tool.sample_clients import SAMPLE_CLIENTS

REPO_URL = "https://github.com/alejandrorochaschiaffino-web/client-portfolio-review"
MAX_AI_LETTERS = 5          # per visitor session, keeps API costs tiny

# Validated categorical palette, fixed order (blue, orange, aqua, yellow).
ASSET_COLORS = {"US Stocks": "#2a78d6", "International Stocks": "#eb6834",
                "Bonds": "#1baf7a", "Cash & T-Bills": "#eda100"}
BLUE, ORANGE = "#2a78d6", "#eb6834"

UI = {
    "en": {
        "title": "Client Portfolio Review",
        "subtitle": "Answer seven questions to see a recommended portfolio, how it held up in real crises, and a client letter in English or Spanish.",
        "language": "Language", "sample": "Start from a sample client", "custom": "Custom client",
        "name": "Client name", "amount": "Amount to invest ($)", "questions": "Investor questionnaire",
        "tabs": ["Overview", "Crisis stress tests", "Client questions", "Interest rates", "Client letter"],
        "profile": "Recommended profile", "score": "Risk score: {score} / 28",
        "capped": "The answers alone point to **{score_profile}**, but the money is needed soon, so the profile is capped at **{profile}** (suitability: little time to recover from a loss).",
        "ann": "Annualized return", "vol": "Volatility", "worst": "Worst fall", "stocks": "In stocks",
        "ann_help": "Compound growth rate per year, Jun 2007 to today, rebalanced monthly.",
        "vol_help": "Typical yearly swing: volatility of monthly returns, annualized.",
        "worst_help": "Largest drop from a previous high, using daily values.",
        "alloc": "Allocation", "holdings": "Holdings",
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
        "years": "Years into retirement", "balance": "Balance ($)",
        "seq_result": "Timing alone made a **{diff}** difference: **{first}** left vs. **{last}**.",
        "rates_title": "If interest rates change",
        "rates_sub": "Bond price change ≈ −duration × change in rates. BND's average duration is 5.8 years; SGOV's about 0.1. Covers the bond and cash part of the portfolio.",
        "rate_change": "Change in rates", "value_change": "Change in value ($)",
        "letter_title": "Client letter", "write_ai": "Rewrite with AI (Claude)",
        "ai_on": "AI-written letter. Every number was checked against the analysis.",
        "ai_off": "Template letter. Add an Anthropic API key to enable the AI-written version.",
        "ai_fallback": "The AI letter didn't pass the number check (or the API was unavailable), so the template is shown.",
        "ai_limit": "AI letter limit reached for this session.",
        "download": "Download letter (.md)",
        "no_data": "Market data is unavailable right now, so only the allocation and rate shocks are shown.",
        "footer": "Educational project, not investment advice. Prices: {source}. Past results don't guarantee future returns; figures are before fees and taxes. [Source code]({url})",
    },
    "es": {
        "title": "Revisión de portafolio para clientes",
        "subtitle": "Responda siete preguntas para ver un portafolio recomendado, cómo resistió crisis reales y una carta para el cliente en inglés o español.",
        "language": "Idioma", "sample": "Empezar con un cliente de ejemplo", "custom": "Cliente personalizado",
        "name": "Nombre del cliente", "amount": "Monto a invertir ($)", "questions": "Cuestionario del inversionista",
        "tabs": ["Resumen", "Pruebas de crisis", "Preguntas del cliente", "Tasas de interés", "Carta al cliente"],
        "profile": "Perfil recomendado", "score": "Puntaje de riesgo: {score} / 28",
        "capped": "Las respuestas por sí solas indican **{score_profile}**, pero el dinero se necesitará pronto, así que el perfil se limita a **{profile}** (idoneidad: poco tiempo para recuperarse de una pérdida).",
        "ann": "Rendimiento anualizado", "vol": "Volatilidad", "worst": "Peor caída", "stocks": "En acciones",
        "ann_help": "Tasa de crecimiento compuesta por año, de junio de 2007 a hoy, con rebalanceo mensual.",
        "vol_help": "Altibajo anual típico: volatilidad de los rendimientos mensuales, anualizada.",
        "worst_help": "Mayor caída desde un máximo previo, con valores diarios.",
        "alloc": "Distribución", "holdings": "Inversiones",
        "fund": "Fondo", "class": "Tipo de activo", "weight": "Porcentaje", "dollars": "Monto",
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
        "years": "Años de jubilación", "balance": "Saldo ($)",
        "seq_result": "Solo el momento de la caída marcó una diferencia de **{diff}**: quedan **{first}** frente a **{last}**.",
        "rates_title": "Si cambian las tasas de interés",
        "rates_sub": "Cambio en el precio de un bono ≈ −duración × cambio en las tasas. La duración promedio de BND es 5.8 años; la de SGOV, cerca de 0.1. Cubre la parte de bonos y efectivo.",
        "rate_change": "Cambio en las tasas", "value_change": "Cambio de valor ($)",
        "letter_title": "Carta al cliente", "write_ai": "Reescribir con IA (Claude)",
        "ai_on": "Carta escrita con IA. Cada cifra se verificó contra el análisis.",
        "ai_off": "Carta de plantilla. Agregue una clave de API de Anthropic para activar la versión escrita con IA.",
        "ai_fallback": "La carta de IA no pasó la verificación de cifras (o la API no estaba disponible), así que se muestra la plantilla.",
        "ai_limit": "Se alcanzó el límite de cartas con IA para esta sesión.",
        "download": "Descargar carta (.md)",
        "no_data": "Los datos de mercado no están disponibles ahora; solo se muestran la distribución y los cambios de tasas.",
        "footer": "Proyecto educativo, no es asesoría de inversión. Precios: {source}. Los resultados pasados no garantizan rendimientos futuros; las cifras son antes de comisiones e impuestos. [Código fuente]({url})",
    },
}

MONTHS_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def month_year(ts, lang):
    return f"{MONTHS_ES[ts.month - 1]} {ts.year}" if lang == "es" else f"{ts:%b %Y}"


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_prices():
    try:
        return data.load_prices(live=True)
    except Exception:
        return None, "unavailable"


def api_key():
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        key = None
    return key or os.environ.get("ANTHROPIC_API_KEY")


def style(fig, height=360):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", y=-0.15), hoverlabel=dict(namelength=-1))
    return fig


# ------------------------------------------------------------------ sidebar

# The answers live in st.session_state.answers, separate from the radio
# buttons. Each language gets its own buttons (labels differ), created from
# the stored answers, so switching language never loses a selection.

def _clear_answer_widgets(lang=None):
    for code in ([lang] if lang else ["en", "es"]):
        for q in QUESTIONS:
            st.session_state.pop(f"q_{q['id']}_{code}", None)


def apply_sample():
    choice = st.session_state.sample
    for c in SAMPLE_CLIENTS:
        if c["name"] == choice:
            st.session_state.name = c["name"]
            st.session_state.amount = float(c["amount"])
            st.session_state.answers = dict(c["answers"])
            _clear_answer_widgets()


st.set_page_config(page_title="Client Portfolio Review", layout="wide")

if "name" not in st.session_state:
    st.session_state.sample = SAMPLE_CLIENTS[2]["name"]
    apply_sample()

with st.sidebar:
    lang_label = st.radio("Language / Idioma", ["English", "Español"], horizontal=True)
    lang = "es" if lang_label == "Español" else "en"
    t = UI[lang]
    st.selectbox(t["sample"], [c["name"] for c in SAMPLE_CLIENTS], key="sample", on_change=apply_sample)
    name = st.text_input(t["name"], key="name")
    amount = st.number_input(t["amount"], min_value=1000.0, max_value=100_000_000.0,
                             step=5000.0, format="%.0f", key="amount")
    st.subheader(t["questions"])
    _clear_answer_widgets("es" if lang == "en" else "en")   # rebuilt from answers on switch
    answers = st.session_state.answers
    for q in QUESTIONS:
        text, options = question_text(q, lang)
        answers[q["id"]] = st.radio(text, [1, 2, 3, 4], index=answers[q["id"]] - 1,
                                    key=f"q_{q['id']}_{lang}",
                                    format_func=lambda p, o=options: o[p - 1])
    answers = dict(answers)

# ------------------------------------------------------------------ analysis

prices, source = load_prices()
review = build_review(name, answers, amount, prices)
profile = PROFILE_NAMES[lang][review["profile"]]

st.title(t["title"])
st.caption(t["subtitle"])
if prices is None:
    st.warning(t["no_data"])

tabs = st.tabs(t["tabs"])

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
        st.plotly_chart(fig, width="stretch", theme="streamlit")

# Crisis stress tests ------------------------------------------------------
with tabs[1]:
    st.markdown(f"#### {t['crisis_title']}")
    st.caption(t["crisis_sub"])
    if review["has_history"]:
        crises = review["crises"]
        names = [CRISIS_NAMES[lang][c["name"]] for c in crises]
        fig = go.Figure(go.Bar(
            y=names, x=[c["dollar_change"] for c in crises], orientation="h",
            marker=dict(color=BLUE, cornerradius=4),
            text=[f"{usd(c['dollar_change'])} ({c['return']:.1%})" for c in crises],
            textposition="inside", insidetextanchor="start", textfont=dict(color="white"),
            hovertemplate="%{y}<br>%{text}<extra></extra>"))
        fig.update_xaxes(tickformat="$,.0f", zeroline=True)
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(style(fig, 280), width="stretch", theme="streamlit")
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
with tabs[2]:
    if review["has_history"]:
        crises = review["crises"]
        names = [CRISIS_NAMES[lang][c["name"]] for c in crises]
        st.markdown(f"#### {t['panic_title']}")
        st.caption(t["panic_sub"])
        fig = go.Figure([
            go.Bar(name=t["stayed"], x=names, y=[c["stayed"] for c in crises],
                   marker=dict(color=BLUE, cornerradius=4),
                   text=[usd(c["stayed"]) for c in crises], textposition="outside"),
            go.Bar(name=t["panicked"], x=names, y=[c["panicked"] for c in crises],
                   marker=dict(color=ORANGE, cornerradius=4),
                   text=[usd(c["panicked"]) for c in crises], textposition="outside"),
        ])
        fig.update_traces(cliponaxis=False, hovertemplate="%{x}<br>%{fullData.name}: %{text}<extra></extra>")
        fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
        fig.update_yaxes(tickformat="$,.0f")
        st.plotly_chart(style(fig, 380), width="stretch", theme="streamlit")
        st.dataframe(pd.DataFrame([{t["crisis"]: n, t["cost"]: usd(c["panic_cost"])}
                                   for n, c in zip(names, crises)]),
                     hide_index=True, width="stretch")

        seq = review["sequence"]
        st.markdown(f"#### {t['seq_title']}")
        st.caption(t["seq_sub"].format(wd=usd(seq["yearly_withdrawal"])))
        fig = go.Figure()
        for key, label, color in (("crash_last", t["crash_last"], BLUE),
                                  ("crash_first", t["crash_first"], ORANGE)):
            path = seq[key]["path"]
            fig.add_trace(go.Scatter(x=[m / 12 for m in range(len(path))], y=path, name=label,
                                     mode="lines", line=dict(color=color, width=2),
                                     hovertemplate="%{x:.1f}: $%{y:,.0f}<extra>" + label + "</extra>"))
        fig.update_layout(hovermode="x unified")
        fig.update_xaxes(title=t["years"], dtick=1)
        fig.update_yaxes(title=t["balance"], tickformat="$,.0f")
        st.plotly_chart(style(fig, 380), width="stretch", theme="streamlit")
        st.markdown(t["seq_result"].format(diff=usd(abs(seq["difference"])),
                                           first=usd(seq["crash_first"]["ending"]),
                                           last=usd(seq["crash_last"]["ending"])))
    else:
        st.info(t["no_data"])

# Interest rates -----------------------------------------------------------
with tabs[3]:
    st.markdown(f"#### {t['rates_title']}")
    st.caption(t["rates_sub"])
    shocks = review["rate_shocks"]
    order = [-0.01, 0.01, 0.02]
    fig = go.Figure(go.Bar(
        x=[f"{c:+.0%}" for c in order], y=[shocks[c]["total_dollar_change"] for c in order],
        marker=dict(color=BLUE, cornerradius=4),
        text=[usd(shocks[c]["total_dollar_change"]) for c in order], textposition="outside",
        cliponaxis=False, hovertemplate="%{x}: %{text}<extra></extra>"))
    fig.update_xaxes(title=t["rate_change"], type="category")
    fig.update_yaxes(title=t["value_change"], tickformat="$,.0f", zeroline=True)
    st.plotly_chart(style(fig, 320), width="stretch", theme="streamlit")

# Client letter ------------------------------------------------------------
with tabs[4]:
    st.markdown(f"#### {t['letter_title']}")
    letter_key = (name, amount, tuple(sorted(answers.items())), lang, str(review.get("data_through")))
    letters = st.session_state.setdefault("letters", {})
    used = st.session_state.setdefault("ai_used", 0)
    letter, source_kind = letters.get(letter_key, (template_report(review, lang), "template"))

    key = api_key()
    if key:
        if st.button(t["write_ai"], disabled=used >= MAX_AI_LETTERS):
            with st.spinner("..."):
                letter, source_kind = ai_report(review, lang, api_key=key)
            st.session_state.ai_used = used + 1
            letters[letter_key] = (letter, source_kind)
            if source_kind != "ai":
                st.warning(t["ai_fallback"])
        if used >= MAX_AI_LETTERS:
            st.caption(t["ai_limit"])
    st.caption(t["ai_on"] if source_kind == "ai" else t["ai_off"] if not key else "")
    st.download_button(t["download"], letter, file_name=f"portfolio_review_{lang}.md",
                       mime="text/markdown")
    with st.container(border=True):
        shown = "\n".join(("#### " + line[3:]) if line.startswith("## ") else
                           ("### " + line[2:]) if line.startswith("# ") else line
                           for line in letter.splitlines())
        st.markdown(shown)

st.divider()
st.caption(t["footer"].format(source=source, url=REPO_URL))
