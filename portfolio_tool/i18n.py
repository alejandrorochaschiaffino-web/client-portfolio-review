"""
English / Spanish text for the questionnaire, profiles, funds and crises.
Numbers are formatted the US way in both languages ($12,345 and 12.3%),
which is how US-based Spanish-speaking clients see their statements.
"""

PROFILE_NAMES = {
    "en": {"Conservative": "Conservative",
           "Moderately Conservative": "Moderately Conservative",
           "Moderate": "Moderate", "Growth": "Growth"},
    "es": {"Conservative": "Conservador",
           "Moderately Conservative": "Moderadamente conservador",
           "Moderate": "Moderado", "Growth": "Crecimiento"},
}

PROFILE_DESCRIPTIONS = {
    "en": {
        "Conservative": "Mostly bonds and cash. Built to protect your money, with modest growth.",
        "Moderately Conservative": "More bonds than stocks. Some growth, with smaller swings.",
        "Moderate": "A balance of stocks and bonds. Solid long-term growth with moderate ups and downs.",
        "Growth": "Mostly stocks. Highest long-term growth potential, but expect big swings along the way.",
    },
    "es": {
        "Conservative": "Principalmente bonos y efectivo. Diseñado para proteger su dinero, con un crecimiento moderado.",
        "Moderately Conservative": "Más bonos que acciones. Algo de crecimiento, con altibajos más pequeños.",
        "Moderate": "Un equilibrio entre acciones y bonos. Buen crecimiento a largo plazo con altibajos moderados.",
        "Growth": "Principalmente acciones. El mayor potencial de crecimiento a largo plazo, pero con altibajos fuertes.",
    },
}

ASSET_CLASSES = {
    "en": {"US Stocks": "US Stocks", "International Stocks": "International Stocks",
           "Bonds": "Bonds", "Cash & T-Bills": "Cash & T-Bills"},
    "es": {"US Stocks": "Acciones de EE. UU.", "International Stocks": "Acciones internacionales",
           "Bonds": "Bonos", "Cash & T-Bills": "Efectivo y letras del Tesoro"},
}

CRISIS_NAMES = {
    "en": {"2008 Financial Crisis": "2008 Financial Crisis",
           "2020 COVID Crash": "2020 COVID Crash",
           "2022 Rate Shock": "2022 Rate Shock"},
    "es": {"2008 Financial Crisis": "Crisis financiera de 2008",
           "2020 COVID Crash": "Caída por COVID de 2020",
           "2022 Rate Shock": "Choque de tasas de 2022"},
}

CRISIS_NOTES = {
    "en": {"2008 Financial Crisis": "Banks failed and stocks fell by about half; high-quality bonds held up.",
           "2020 COVID Crash": "The fastest crash on record, followed by a quick recovery.",
           "2022 Rate Shock": "Rates rose fast to fight inflation, so stocks and bonds fell together."},
    "es": {"2008 Financial Crisis": "Quebraron bancos y las acciones cayeron casi a la mitad; los bonos de alta calidad resistieron.",
           "2020 COVID Crash": "La caída más rápida de la historia, seguida de una recuperación rápida.",
           "2022 Rate Shock": "Las tasas subieron rápido para combatir la inflación, y cayeron acciones y bonos a la vez."},
}

# Same order and ids as profiles.QUESTIONS; answers are worth 1-4 points.
QUESTIONS_ES = {
    "horizon": ("¿Cuándo necesitará empezar a usar la mayor parte de este dinero?",
                ["En menos de 3 años", "En 3 a 5 años", "En 6 a 10 años", "En más de 10 años"]),
    "goal": ("¿Cuál es su objetivo principal para este dinero?",
             ["Proteger lo que tengo", "Obtener ingresos estables",
              "Equilibrar crecimiento y seguridad", "Hacerlo crecer lo más posible"]),
    "drop_reaction": ("Su portafolio cae un 20% en un año. ¿Qué hace?",
                      ["Vendo todo", "Vendo una parte", "Mantengo y espero",
                       "Compro más mientras los precios están bajos"]),
    "experience": ("¿Cuánta experiencia tiene invirtiendo?",
                   ["Ninguna", "Solo cuentas de ahorro y certificados de depósito",
                    "Algunas acciones o fondos", "Invierto con regularidad"]),
    "income": ("¿Qué tan estable es su ingreso?",
               ["Inestable", "Algo estable", "Estable", "Muy estable"]),
    "emergency_fund": ("¿Cuántos meses de gastos tiene ahorrados para emergencias?",
                       ["Ninguno", "Menos de 3 meses", "De 3 a 6 meses", "Más de 6 meses"]),
    "tradeoff": ("¿Qué rango de resultados en un año preferiría?",
                 ["+2% a +4%", "-5% a +10%", "-15% a +20%", "-25% a +35%"]),
}


def question_text(q: dict, lang: str) -> tuple:
    """(question, [answers]) for a profiles.QUESTIONS entry in the chosen language."""
    if lang == "es":
        return QUESTIONS_ES[q["id"]]
    return q["text"], q["answers"]
