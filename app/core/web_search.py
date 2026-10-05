from ddgs import DDGS
from app.config import settings
from app.core.lexical import ngramas


def extraer_frases_clave(texto: str, max_frases: int = None, n: int = 10) -> list[str]:
    """Extrae frases largas (n-gramas) representativas para buscar en web."""
    max_frases = max_frases or settings.web_search_max_queries
    frases = list(ngramas(texto, n=n))
    frases = sorted(set(frases), key=len, reverse=True)
    return frases[:max_frases]


def buscar_en_web(frase: str, max_results: int = 5) -> list[dict]:
    if not settings.web_search_enabled:
        return []
    try:
        with DDGS() as ddgs:
            resultados = list(ddgs.text(f'"{frase}"', max_results=max_results))
        return [{
            "titulo": r.get("title"),
            "url": r.get("href"),
            "snippet": r.get("body"),
            "frase_buscada": frase,
        } for r in resultados]
    except Exception as e:
        return [{"error": str(e), "frase_buscada": frase}]