"""Capa de ejecucion: permite trabajar en un solo proceso o contra la API.

- Modo IN-PROCESO (por defecto): importa el nucleo y lo llama directamente.
  Es lo que permite desplegar en Streamlit Community Cloud, que solo admite
  un proceso. Tambien evita depender de la terminal de la API.
- Modo API: delega en el servidor FastAPI (uvicorn) si se indica
  PLAGIO_USE_API=1. Util cuando el nucleo se ejecuta en otra maquina.
"""
import os
from pathlib import Path

# Permite ejecutar desde la raiz del repo (Streamlit Community Cloud) o desde ui/
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in os.sys.path:
    os.sys.path.insert(0, str(_RAIZ))

from app.config import settings            # noqa: E402
from app.core.analyzer import analizar_documento   # noqa: E402
from app.core.extractor import extract_text        # noqa: E402
from app.core.judge import test_llm                # noqa: E402

API = os.environ.get("PLAGIO_API_URL", "http://localhost:8000")
USAR_API = os.environ.get("PLAGIO_USE_API", "0") == "1"


# --- Estado ---------------------------------------------------------------

def _indice_existe() -> bool:
    return settings.chroma_dir.exists() and any(settings.chroma_dir.glob("*.pkl"))


# --- Configuracion del LLM ------------------------------------------------

def guardar_config(provider: str, model: str, api_key: str, ollama_host: str) -> None:
    """Guarda la configuracion del proveedor seleccionado."""
    if USAR_API:
        import requests
        payload = {"provider": provider, f"{provider}_model": model}
        if provider == "ollama":
            payload["ollama_host"] = ollama_host
        elif provider == "nim":
            payload["nvidia_nim_api_key"] = api_key
            payload["nvidia_nim_model"] = model
        else:
            payload[f"{provider}_api_key"] = api_key
        requests.post(f"{API}/config/llm", json=payload, timeout=30)
        return

    settings.llm_provider = provider
    if provider == "ollama":
        settings.ollama_host = ollama_host or settings.ollama_host
        settings.ollama_model = model
    elif provider == "nim":
        settings.nvidia_nim_api_key = api_key
        settings.nvidia_nim_model = model
    elif provider == "gemini":
        settings.gemini_api_key = api_key
        settings.gemini_model = model
    elif provider == "groq":
        settings.groq_api_key = api_key
        settings.groq_model = model
    elif provider == "openrouter":
        settings.openrouter_api_key = api_key
        settings.openrouter_model = model


def probar_config() -> dict:
    """Comprueba que el proveedor configurado responde."""
    if USAR_API:
        import requests
        try:
            return requests.post(f"{API}/test/llm", timeout=120).json()
        except Exception as e:
            return {"ok": False, "error": f"No se pudo contactar con la API: {e}"}
    return test_llm()


# --- Analisis -------------------------------------------------------------

def analizar(contenido: bytes | None = None, ruta=None, texto: str | None = None,
             usar_llm: bool = True, usar_web: bool = False) -> dict:
    """Analiza un documento. Devuelve siempre un dict con 'error' si falla."""
    try:
        if USAR_API:
            import requests
            if contenido is not None:
                nombre = getattr(ruta, "name", "documento.pdf")
                r = requests.post(
                    f"{API}/analizar/archivo",
                    files={"file": (nombre, contenido)},
                    data={"usar_llm": usar_llm, "usar_web": usar_web},
                    timeout=900,
                )
            else:
                r = requests.post(
                    f"{API}/analizar/texto",
                    params={"texto": texto, "usar_llm": usar_llm, "usar_web": usar_web},
                    timeout=900,
                )
            if r.headers.get("content-type", "").startswith("application/json"):
                return r.json()
            return {"error": f"Error {r.status_code} de la API: {r.text[:300]}"}

        # In-proceso
        if contenido is not None:
            import tempfile
            suf = Path(getattr(ruta, "name", "documento.pdf")).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suf) as tmp:
                tmp.write(contenido)
                tmp_path = Path(tmp.name)
            try:
                cuerpo = extract_text(tmp_path)
            finally:
                tmp_path.unlink(missing_ok=True)
        else:
            cuerpo = texto or ""

        if not cuerpo.strip():
            return {"error": "El documento no contiene texto extraible."}

        return analizar_documento(cuerpo, usar_llm=usar_llm, usar_web=usar_web)

    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}