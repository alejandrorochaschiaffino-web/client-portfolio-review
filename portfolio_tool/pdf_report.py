"""
The client review as a polished PDF (English or Spanish).

Page 1 summarizes the recommendation (profile, key figures, allocation and
the goal projection), page 2 shows how the portfolio behaved in real
crises and answers the two questions clients ask, and the following pages
hold the client letter itself (template or AI-assisted).

Every number comes from build_review(); the charts are drawn with
matplotlib and the layout with ReportLab. Fonts are the DejaVu family that
ships with matplotlib, so accents (á, ñ, ¿) and symbols (≈, −) print
correctly everywhere.
"""

from __future__ import annotations

import io
import re
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")                     # no screen needed (servers, tests)
import matplotlib.pyplot as plt           # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402
from reportlab.lib import colors          # noqa: E402
from reportlab.lib.enums import TA_LEFT   # noqa: E402
from reportlab.lib.pagesizes import LETTER  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import inch      # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,  # noqa: E402
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from .i18n import ASSET_CLASSES, CRISIS_NAMES, PROFILE_DESCRIPTIONS, PROFILE_NAMES  # noqa: E402
from .projection import chart_floor  # noqa: E402
from .report import MONTHS_ES, goal_paragraph, odds, usd  # noqa: E402

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, MUTED, RULE, PANEL = "#1d2433", "#5b6475", "#d9dee7", "#f3f5f9"
ASSET_COLORS = {"US Stocks": BLUE, "International Stocks": ORANGE,
                "Bonds": AQUA, "Cash & T-Bills": YELLOW}

LABELS = {
    "en": {
        "doc_title": "Portfolio Review", "prepared": "Prepared {today} · Market data through {through}",
        "for": "For", "profile": "Recommended profile", "score": "Risk score {score} of 28",
        "capped": "The answers alone point to {score_profile}, but the money is needed soon, so the profile is capped at {profile}.",
        "ann": "Annualized return", "vol": "Volatility", "worst": "Worst fall", "stocks": "In stocks",
        "allocation": "Recommended allocation", "fund": "Fund", "class": "Asset class",
        "weight": "Weight", "amount": "Amount", "total": "Total",
        "goal": "Goal projection", "goal_chance": "chance of reaching {target} in {years}",
        "goal_typ": "Typical outcome", "goal_bad": "Bad case (1 in 10)", "goal_in": "Total put in",
        "x_years": "Years from today", "typical": "Typical", "mid": "Middle half", "wide": "8 in 10 futures",
        "goal_line": "Goal",
        "history": "How it held up", "crises": "Three real crises (peak to bottom)",
        "crisis": "Crisis", "loss": "Loss", "loss_usd": "Loss ($)", "back": "Back to even",
        "months": "{m} months", "not_yet": "Not yet",
        "panic": "“Should I sell and wait it out?”", "stayed": "Stayed invested",
        "panicked": "Sold at bottom, back 1 year later",
        "panic_note": "Value today of the amount invested at each market peak.",
        "seq": "“Does it matter when a crash happens if I'm retired?”",
        "seq_first": "Crash at the start", "seq_last": "Same returns, crash at the end",
        "seq_note": "Withdrawing {wd} a year for 10 years. Same returns, different order.",
        "rates": "If interest rates change", "rate_change": "Change in rates", "value_change": "Change in value",
        "pt": "pt", "letter": "Client letter", "page": "Page {n}",
        "footer": "Educational example, not investment advice. Past results don't guarantee future returns.",
    },
    "es": {
        "doc_title": "Revisión de portafolio", "prepared": "Preparado el {today} · Datos de mercado hasta el {through}",
        "for": "Para", "profile": "Perfil recomendado", "score": "Puntaje de riesgo {score} de 28",
        "capped": "Las respuestas por sí solas indican {score_profile}, pero el dinero se necesitará pronto, así que el perfil se limita a {profile}.",
        "ann": "Rendimiento anualizado", "vol": "Volatilidad", "worst": "Peor caída", "stocks": "En acciones",
        "allocation": "Asignación recomendada", "fund": "Fondo", "class": "Clase de activo",
        "weight": "Porcentaje", "amount": "Monto", "total": "Total",
        "goal": "Proyección de la meta", "goal_chance": "de probabilidad de llegar a {target} en {years}",
        "goal_typ": "Resultado típico", "goal_bad": "Caso malo (1 de cada 10)", "goal_in": "Total aportado",
        "x_years": "Años a partir de hoy", "typical": "Típico", "mid": "Mitad central", "wide": "8 de cada 10 futuros",
        "goal_line": "Meta",
        "history": "Cómo resistió", "crises": "Tres crisis reales (del máximo al mínimo)",
        "crisis": "Crisis", "loss": "Pérdida", "loss_usd": "Pérdida ($)", "back": "Recuperación",
        "months": "{m} meses", "not_yet": "Todavía no",
        "panic": "“¿Debería vender y esperar?”", "stayed": "Se mantuvo invertido",
        "panicked": "Vendió en el mínimo, volvió 1 año después",
        "panic_note": "Valor actual del monto invertido en cada punto máximo del mercado.",
        "seq": "“¿Importa cuándo ocurre una caída si estoy jubilado?”",
        "seq_first": "Caída al inicio", "seq_last": "Mismos rendimientos, caída al final",
        "seq_note": "Retirando {wd} al año durante 10 años. Mismos rendimientos, distinto orden.",
        "rates": "Si cambian las tasas de interés", "rate_change": "Cambio en las tasas", "value_change": "Cambio de valor",
        "pt": "pt", "letter": "Carta al cliente", "page": "Página {n}",
        "footer": "Ejemplo educativo, no es asesoría de inversión. Los resultados pasados no garantizan rendimientos futuros.",
    },
}

# ----------------------------------------------------------------- fonts

_FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
_FONTS_READY = False


def _register_fonts():
    global _FONTS_READY
    if _FONTS_READY:
        return
    for name, file in (("DejaVu", "DejaVuSans.ttf"), ("DejaVu-Bold", "DejaVuSans-Bold.ttf"),
                       ("DejaVu-Oblique", "DejaVuSans-Oblique.ttf"),
                       ("DejaVu-BoldOblique", "DejaVuSans-BoldOblique.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(_FONT_DIR / file)))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                                  italic="DejaVu-Oblique", boldItalic="DejaVu-BoldOblique")
    _FONTS_READY = True


def _styles():
    base = dict(fontName="DejaVu", textColor=colors.HexColor(INK), alignment=TA_LEFT)
    return {
        "title": ParagraphStyle("title", fontSize=22, leading=27, fontName="DejaVu-Bold", **{
            k: v for k, v in base.items() if k != "fontName"}),
        "sub": ParagraphStyle("sub", fontSize=9, leading=12, **{**base, "textColor": colors.HexColor(MUTED)}),
        "h2": ParagraphStyle("h2", fontSize=13, leading=17, spaceBefore=10, spaceAfter=4,
                             **{**base, "fontName": "DejaVu-Bold"}),
        "h3": ParagraphStyle("h3", fontSize=10.5, leading=14, spaceBefore=6, spaceAfter=2,
                             **{**base, "fontName": "DejaVu-Bold"}),
        "body": ParagraphStyle("body", fontSize=9.5, leading=13.5, spaceAfter=6, **base),
        "small": ParagraphStyle("small", fontSize=8, leading=10.5, **{**base, "textColor": colors.HexColor(MUTED)}),
        "big": ParagraphStyle("big", fontSize=26, leading=30, **{**base, "fontName": "DejaVu-Bold",
                                                                  "textColor": colors.HexColor(BLUE)}),
        "cell": ParagraphStyle("cell", fontSize=8.5, leading=11, **base),
        "cellb": ParagraphStyle("cellb", fontSize=8.5, leading=11, **{**base, "fontName": "DejaVu-Bold"}),
        "tile_label": ParagraphStyle("tl", fontSize=7.5, leading=9.5, **{**base, "textColor": colors.HexColor(MUTED)}),
        "tile_value": ParagraphStyle("tv", fontSize=15, leading=18, **{**base, "fontName": "DejaVu-Bold"}),
    }


# ----------------------------------------------------------------- helpers

def _x(text) -> str:
    """Escape text for ReportLab's mini-markup."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def md_inline(text: str) -> str:
    """Markdown bold/italic and backslash escapes -> ReportLab markup."""
    keep = []

    def stash(m):
        keep.append(m.group(1))
        return f"\x00{len(keep) - 1}\x00"

    text = re.sub(r"\\(.)", stash, text)                 # \* \$ \[ ... stay literal
    text = _x(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: _x(keep[int(m.group(1))]), text)


def _date(d, lang) -> str:
    return f"{d.day} de {MONTHS_ES[d.month - 1]} de {d.year}" if lang == "es" else f"{d:%b} {d.day}, {d.year}"


def _years(n, lang) -> str:
    if lang == "es":
        return f"{n} año" if n == 1 else f"{n} años"
    return f"{n} year" if n == 1 else f"{n} years"


def _money_axis(ax, axis="y"):
    fmt = FuncFormatter(lambda v, _: usd(v))
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def _fig_to_image(fig, width_in: float) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = width_in * inch, width_in * inch * ratio
    return img


def _short_usd(v: float) -> str:
    """$837,520 -> $838k (chart labels only; tables keep exact dollars)."""
    return f"${v / 1e6:,.1f}M" if abs(v) >= 1e6 else f"${v / 1e3:,.0f}k" if abs(v) >= 1e4 else usd(v)


def _clean_axes(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(RULE)
    ax.tick_params(colors=MUTED, labelsize=7.5, length=0)
    ax.grid(axis="y", color=RULE, linewidth=0.6)
    ax.set_axisbelow(True)


def _wrap(label: str) -> str:
    if " " not in label:
        return label
    mid = len(label) / 2
    cut = min((i for i, ch in enumerate(label) if ch == " "), key=lambda i: abs(i - mid))
    return label[:cut] + "\n" + label[cut + 1:]


def _table(rows, widths, st, header=True, align_right=()):
    data = [[Paragraph(c if isinstance(c, str) else _x(c), st["cellb" if header and i == 0 else "cell"])
             for c in row] for i, row in enumerate(rows)]
    t = Table(data, colWidths=[w * inch for w in widths], hAlign="LEFT")
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor(RULE)),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PANEL)))
    for col in align_right:
        style.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t


# ----------------------------------------------------------------- charts

def _donut(review, lang):
    classes = {}
    for h in review["holdings"]:
        classes[h["asset_class"]] = classes.get(h["asset_class"], 0) + h["weight"]
    fig, ax = plt.subplots(figsize=(2.0, 2.0))
    ax.pie(list(classes.values()), colors=[ASSET_COLORS[k] for k in classes], startangle=90,
           counterclock=False, wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
           autopct=lambda p: f"{p:.0f}%" if p >= 6 else "", pctdistance=0.79,
           textprops=dict(color="white", fontsize=6.5, fontweight="bold"))
    ax.set_aspect("equal")
    return fig


def _fan(g, lang):
    L = LABELS[lang]
    x = [m / 12 for m in range(g["months"] + 1)]
    b = g["bands"]
    fig, ax = plt.subplots(figsize=(6.6, 2.05))
    ax.fill_between(x, b[10], b[90], color=BLUE, alpha=0.15, linewidth=0, label=L["wide"])
    ax.fill_between(x, b[25], b[75], color=BLUE, alpha=0.32, linewidth=0, label=L["mid"])
    ax.plot(x, b[50], color=BLUE, linewidth=2, label=L["typical"])
    ax.axhline(g["goal"], color=ORANGE, linewidth=1.6, linestyle="--")
    ax.text(0, g["goal"], f" {L['goal_line']}: {usd(g['goal'])}", color=ORANGE, fontsize=7.5,
            va="bottom", ha="left", bbox=dict(facecolor="white", edgecolor="none", pad=1, alpha=0.85))
    _clean_axes(ax)
    _money_axis(ax)
    ax.set_xlabel(L["x_years"], fontsize=7.5, color=MUTED)
    ax.set_xlim(0, x[-1])
    ax.set_ylim(bottom=chart_floor(g))
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(loc="upper left", frameon=False, fontsize=7, ncol=3, bbox_to_anchor=(0, 1.16))
    return fig


def _crisis_bars(review, lang):
    crises = review["crises"]
    names = [_wrap(CRISIS_NAMES[lang][c["name"]]) for c in crises][::-1]
    vals = [c["dollar_change"] for c in crises][::-1]
    fig, ax = plt.subplots(figsize=(3.3, 1.9))
    bars = ax.barh(names, vals, color=BLUE, height=0.6)
    for bar, c in zip(bars, crises[::-1]):
        inside_left = bar.get_width() < 0                     # losses grow leftwards from 0
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f"  {c['return']:.1%}  ",
                va="center", ha="left" if inside_left else "right", color="white",
                fontsize=7.5, fontweight="bold")
    _clean_axes(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=RULE, linewidth=0.6)
    _money_axis(ax, "x")
    ax.xaxis.set_major_locator(MaxNLocator(3))
    ax.axvline(0, color=MUTED, linewidth=0.8)
    return fig


def _panic_bars(review, lang):
    L = LABELS[lang]
    crises = review["crises"]
    names = [_wrap(CRISIS_NAMES[lang][c["name"]]) for c in crises]
    xs = range(len(crises))
    fig, ax = plt.subplots(figsize=(3.3, 2.2))
    w = 0.38
    stayed = ax.bar([i - w / 2 for i in xs], [c["stayed"] for c in crises], w, color=BLUE, label=L["stayed"])
    pan = ax.bar([i + w / 2 for i in xs], [c["panicked"] for c in crises], w, color=ORANGE, label=L["panicked"])
    for bars in (stayed, pan):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), _short_usd(bar.get_height()),
                    ha="center", va="bottom", fontsize=6, color=MUTED)
    ax.set_xticks(list(xs), names)
    _clean_axes(ax)
    _money_axis(ax)
    top = max(max(c["stayed"], c["panicked"]) for c in crises)
    ax.set_ylim(0, top * 1.18)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=1, frameon=False, fontsize=6.5)
    return fig


def _sequence(review, lang):
    L = LABELS[lang]
    seq = review["sequence"]
    fig, ax = plt.subplots(figsize=(3.3, 2.2))
    for key, label, color in (("crash_last", L["seq_last"], BLUE), ("crash_first", L["seq_first"], ORANGE)):
        path = seq[key]["path"]
        ax.plot([m / 12 for m in range(len(path))], path, color=color, linewidth=1.8, label=label)
    _clean_axes(ax)
    _money_axis(ax)
    ax.set_xlabel(L["x_years"].split()[0] if lang == "en" else "Años", fontsize=7, color=MUTED)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=1, frameon=False, fontsize=6.5)
    return fig


# ----------------------------------------------------------------- letter

def letter_flowables(letter_md: str, st) -> list:
    """The Markdown client letter as ReportLab paragraphs and tables."""
    out, table = [], []

    def flush_table():
        if table:
            rows = [[md_inline(c.strip()) for c in r.strip().strip("|").split("|")] for r in table]
            ncol = len(rows[0])
            widths = [0.8, 2.6, 1.0, 1.3][:ncol] if ncol == 4 else [6.5 / ncol] * ncol
            out.append(_table(rows, widths, st, align_right=(2, 3) if ncol == 4 else ()))
            out.append(Spacer(1, 6))
            table.clear()

    for line in letter_md.splitlines():
        s = line.strip()
        if s.startswith("|"):
            if not re.fullmatch(r"\|?[\s:|-]+\|?", s):          # skip the |---| separator row
                table.append(s)
            continue
        flush_table()
        if not s or s == "---":
            continue
        if s.startswith("# "):
            out.append(Paragraph(md_inline(s[2:]), st["h2"]))
        elif s.startswith("## "):
            out.append(Paragraph(md_inline(s[3:]), st["h3"]))
        elif s.startswith("- "):
            out.append(Paragraph(md_inline(s[2:]), st["body"], bulletText="•"))
        elif s.startswith("*") and s.endswith("*") and not s.startswith("**"):
            out.append(Paragraph(md_inline(s), st["small"]))
        else:
            out.append(Paragraph(md_inline(s), st["body"]))
    flush_table()
    return out


# ----------------------------------------------------------------- document

def build_pdf(review: dict, letter_md: str, lang: str = "en", today: date | None = None) -> bytes:
    """The full client review as PDF bytes."""
    _register_fonts()
    st = _styles()
    L = LABELS[lang]
    today = today or date.today()
    name = review["name"] or ("Cliente" if lang == "es" else "Client")
    profile = PROFILE_NAMES[lang][review["profile"]]
    story = []

    # --- page 1: recommendation -------------------------------------------
    through = review.get("data_through")
    story += [Paragraph(_x(L["doc_title"]), st["title"]),
              Paragraph(f"{_x(L['for'])} <b>{_x(name)}</b> · " + _x(L["prepared"].format(
                  today=_date(today, lang), through=_date(through, lang) if through is not None else "—")),
                  st["sub"]),
              Spacer(1, 10),
              Paragraph(f"{_x(L['profile'])}: <font color='{BLUE}'>{_x(profile)}</font>", st["h2"]),
              Paragraph(_x(L["score"].format(score=review["score"])) + " · " +
                        _x(PROFILE_DESCRIPTIONS[lang][review["profile"]]), st["body"])]
    if review["capped"]:
        story.append(Paragraph(_x(L["capped"].format(
            score_profile=PROFILE_NAMES[lang][review["score_profile"]], profile=profile)), st["small"]))

    if review["has_history"]:
        s = review["stats"]
        tiles = [(L["ann"], f"{s['annual_return']:.1%}"), (L["vol"], f"{s['volatility']:.1%}"),
                 (L["worst"], f"{s['max_drawdown']:.1%}"), (L["stocks"], f"{review['stock_share']:.0%}")]
        t = Table([[Paragraph(_x(a), st["tile_label"]) for a, _ in tiles],
                   [Paragraph(_x(b), st["tile_value"]) for _, b in tiles]],
                  colWidths=[1.625 * inch] * 4, hAlign="LEFT")
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PANEL)),
                               ("LINEAFTER", (0, 0), (-2, -1), 2, colors.white),
                               ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
        story += [Spacer(1, 6), t]

    rows = [[L["fund"], L["class"], L["weight"], L["amount"]]]
    rows += [[h["ticker"], f"<font color='{ASSET_COLORS[h['asset_class']]}'>\u25a0</font> "
              + _x(ASSET_CLASSES[lang][h["asset_class"]]), f"{h['weight']:.0%}", usd(h["dollars"])]
             for h in review["holdings"]]
    rows.append([f"<b>{_x(L['total'])}</b>", "", "<b>100%</b>", f"<b>{_x(usd(review['amount']))}</b>"])
    holdings = _table(rows, [0.65, 2.05, 1.0, 0.95], st, align_right=(2, 3))
    side = Table([[_fig_to_image(_donut(review, lang), 1.55), holdings]],
                 colWidths=[1.8 * inch, 4.75 * inch], hAlign="LEFT")
    side.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [Paragraph(_x(L["allocation"]), st["h2"]), side]

    g = review.get("goal")
    if g:
        head = Table([[Paragraph(odds(g["probability"]), st["big"]),
                       Paragraph(_x(L["goal_chance"].format(target=usd(g["goal"]), years=_years(g["years"], lang))),
                                 st["body"])]],
                     colWidths=[1.2 * inch, 5.3 * inch], hAlign="LEFT")
        head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        figs = [(L["goal_typ"], usd(g["ending"][50])), (L["goal_bad"], usd(g["ending"][10])),
                (L["goal_in"], usd(g["contributed"]))]
        nums = Table([[Paragraph(_x(a), st["tile_label"]) for a, _ in figs],
                      [Paragraph(_x(b), st["cellb"]) for _, b in figs]],
                     colWidths=[2.17 * inch] * 3, hAlign="LEFT")
        nums.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1)]))
        story.append(KeepTogether([Paragraph(_x(L["goal"]), st["h2"]), head, nums, Spacer(1, 4),
                                   _fig_to_image(_fan(g, lang), 6.5),
                                   Paragraph(md_inline(goal_paragraph(g, review["stats"]["start"], lang)),
                                             st["small"])]))

    # --- page 2: history and client questions ------------------------------
    if review["has_history"]:
        story += [PageBreak(), Paragraph(_x(L["history"]), st["title"]), Spacer(1, 4),
                  Paragraph(_x(L["crises"]), st["h2"])]
        crisis_rows = [[L["crisis"], L["loss"], L["loss_usd"], L["back"]]]
        for c in review["crises"]:
            back = L["months"].format(m=round(c["months_total"])) if c["recovered"] else L["not_yet"]
            crisis_rows.append([CRISIS_NAMES[lang][c["name"]], f"{c['return']:.1%}", usd(c["dollar_change"]), back])
        pair = Table([[_fig_to_image(_crisis_bars(review, lang), 2.8),
                       _table(crisis_rows, [1.3, 0.68, 0.8, 1.0], st, align_right=(1, 2))]],
                     colWidths=[2.82 * inch, 3.78 * inch], hAlign="LEFT")
        pair.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(pair)

        seq = review["sequence"]
        qs = Table([[Paragraph(_x(L["panic"]), st["h3"]), Paragraph(_x(L["seq"]), st["h3"])],
                    [_fig_to_image(_panic_bars(review, lang), 3.15), _fig_to_image(_sequence(review, lang), 3.15)],
                    [Paragraph(_x(L["panic_note"]), st["small"]),
                     Paragraph(_x(L["seq_note"].format(wd=usd(seq["yearly_withdrawal"]))), st["small"])]],
                   colWidths=[3.3 * inch, 3.3 * inch], hAlign="LEFT")
        qs.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        story += [Spacer(1, 6), qs]

    shocks = review["rate_shocks"]
    rate_rows = [[L["rate_change"], L["value_change"]]]
    for ch in (-0.01, 0.01, 0.02):
        v = shocks[ch]["total_dollar_change"]
        rate_rows.append([f"{ch * 100:+.0f} {L['pt']}", ("+" if round(v) > 0 else "") + usd(v)])
    story += [Paragraph(_x(L["rates"]), st["h2"]), _table(rate_rows, [1.6, 1.6], st, align_right=(1,))]

    # --- the letter --------------------------------------------------------
    story += [PageBreak()] + letter_flowables(letter_md, st)

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont("DejaVu", 7)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(0.75 * inch, 0.5 * inch, L["footer"])
        canvas.drawRightString(LETTER[0] - 0.75 * inch, 0.5 * inch, L["page"].format(n=doc.page))
        canvas.setStrokeColor(colors.HexColor(BLUE))
        canvas.setLineWidth(3)
        canvas.line(0.75 * inch, LETTER[1] - 0.45 * inch, LETTER[0] - 0.75 * inch, LETTER[1] - 0.45 * inch)
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.75 * inch,
                            title=f"{L['doc_title']} — {name}", author="Client Portfolio Review",
                            subject=L["doc_title"])
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buf.getvalue()
