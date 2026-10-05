"""Motor de decision basado en evidencia medible.

El LLM NO decide si hay plagio: solo redacta la justificacion. El veredicto
lo fija este modulo a partir de medidas objetivas, de forma reproducible y
auditable. Esto evita que un modelo invente excusas ("es la misma practica")
para descartar evidencia objetiva.
"""
from app.config import settings

# decision: "si" | "dudoso" | "no"
# tipo:    "literal" | "parafrasis" | "ideas" | "ninguno"

UMBRAL_PLAGIO_NUMEROS = 3      # valores identicos distintos
UMBRAL_PLAGIO_ENTIDADES = 2    # nombres propios coincidentes (lugar, organismo)
UMBRAL_LITERAL_LEXICO = 0.50
UMBRAL_LITERAL_SEMANTICA = 0.92
UMBRAL_PARAFRASIS_LEXICO = 0.25


def evaluar(ev: dict) -> dict:
    """ev contiene: mismo_autor, semantica, lexico, minhash, numeros, entidades.

    Devuelve el veredicto y las señales que lo justifican.
    """
    if ev.get("mismo_autor"):
        comunes = ev.get("autores_comunes") or []
        return {
            "plagio": "no",
            "tipo": "ninguno",
            "severidad": 0,
            "senales": [f"mismo autor ({', '.join(comunes)})"],
        }

    sem = ev.get("similitud_semantica") or 0.0
    lex = ev.get("similitud_lexica") or 0.0
    nums = ev.get("numeros") or {}
    ents = ev.get("entidades") or {}

    n_comunes = nums.get("comunes", 0)
    n_ratio = nums.get("ratio", 0.0)
    n_ejemplos = nums.get("ejemplos", [])
    e_comunes = ents.get("comunes", 0)
    e_ejemplos = ents.get("ejemplos", [])

    senales: list[str] = []
    if n_comunes:
        senales.append(f"{n_comunes} valores numéricos idénticos ({', '.join(n_ejemplos[:6])})")
    if e_comunes:
        senales.append(f"{e_comunes} entidades idénticas ({', '.join(e_ejemplos[:6])})")
    if lex >= 0.3:
        senales.append(f"solapamiento léxico {round(lex * 100)}%")
    if sem >= 0.9:
        senales.append(f"similitud semántica {round(sem * 100)}%")

    # --- Ninguna señal: no hay motivo para acusar ---
    if n_comunes == 0 and e_comunes == 0 and lex < UMBRAL_PARAFRASIS_LEXICO and sem < 0.85:
        return {
            "plagio": "no",
            "tipo": "ninguno",
            "severidad": 0,
            "senales": senales or ["sin evidencia de copia"],
        }

    # --- Copia literal de texto ---
    if lex >= UMBRAL_LITERAL_LEXICO and (n_comunes >= 1 or e_comunes >= 1):
        sev = 90 if lex >= 0.7 else 75
        return {
            "plagio": "si",
            "tipo": "literal",
            "severidad": sev,
            "senales": senales,
        }

    # --- Datos del caso copiados: la evidencia más fuerte entre autores distintos ---
    if n_comunes >= UMBRAL_PLAGIO_NUMEROS or e_comunes >= UMBRAL_PLAGIO_ENTIDADES:
        # Cuantos más valores y entidades compartidos, más grave
        sev = min(95, 55 + n_comunes * 2 + e_comunes * 5)
        if n_ratio >= 0.5:
            sev = min(95, sev + 10)
        return {
            "plagio": "si",
            "tipo": "parafrasis" if lex < UMBRAL_LITERAL_LEXICO else "literal",
            "severidad": sev,
            "senales": senales,
        }

    # --- Caso borderline: un solo dato o entidad compartida ---
    if n_comunes >= 1 or e_comunes >= 1:
        return {
            "plagio": "dudoso",
            "tipo": "ideas",
            "severidad": 40,
            "senales": senales,
        }

    # --- Sin datos, pero texto muy parecido ---
    if sem >= UMBRAL_LITERAL_SEMANTICA:
        sev = int(min(75, 45 + lex * 30))
        return {
            "plagio": "dudoso" if lex < 0.4 else "si",
            "tipo": "parafrasis",
            "severidad": sev,
            "senales": senales,
        }

    # --- Solo tema compartido ---
    return {
        "plagio": "no",
        "tipo": "ninguno",
        "severidad": 0,
        "senales": senales or ["similitud solo temática"],
    }