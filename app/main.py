from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
from pathlib import Path
import shutil, tempfile

from app.core.extractor import extract_text
from app.core.analyzer import analizar_documento
from app.core.judge import test_llm
from app.config import settings

app = FastAPI(title="Detector de Plagio IA", version="0.1.0")


class LLMConfig(BaseModel):
    provider: str
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    groq_api_key: str | None = None
    groq_model: str | None = None
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    nvidia_nim_api_key: str | None = None
    nvidia_nim_model: str | None = None
    ollama_host: str | None = None
    ollama_model: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/config/llm")
def config_llm(cfg: LLMConfig):
    settings.llm_provider = cfg.provider
    if cfg.gemini_api_key:
        settings.gemini_api_key = cfg.gemini_api_key
    if cfg.gemini_model:
        settings.gemini_model = cfg.gemini_model
    if cfg.groq_api_key:
        settings.groq_api_key = cfg.groq_api_key
    if cfg.groq_model:
        settings.groq_model = cfg.groq_model
    if cfg.openrouter_api_key:
        settings.openrouter_api_key = cfg.openrouter_api_key
    if cfg.openrouter_model:
        settings.openrouter_model = cfg.openrouter_model
    if cfg.nvidia_nim_api_key:
        settings.nvidia_nim_api_key = cfg.nvidia_nim_api_key
    if cfg.nvidia_nim_model:
        settings.nvidia_nim_model = cfg.nvidia_nim_model
    if cfg.ollama_host:
        settings.ollama_host = cfg.ollama_host
    if cfg.ollama_model:
        settings.ollama_model = cfg.ollama_model
    return {"status": "ok", "provider": settings.llm_provider}


@app.get("/config/llm")
def get_llm_config():
    return {
        "provider": settings.llm_provider,
        "gemini_model": settings.gemini_model,
        "groq_model": settings.groq_model,
        "ollama_model": settings.ollama_model,
        "ollama_host": settings.ollama_host,
    }


@app.post("/test/llm")
def test_llm_endpoint():
    return test_llm()


@app.post("/analizar/texto")
def analizar_texto(texto: str, usar_llm: bool = True, usar_web: bool = True):
    return analizar_documento(texto, usar_llm=usar_llm, usar_web=usar_web)


@app.post("/analizar/archivo")
async def analizar_archivo(
    file: UploadFile = File(...),
    usar_llm: bool = Form(True),
    usar_web: bool = Form(False),
):
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=Path(file.filename or "").suffix
        ) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = Path(tmp.name)
        try:
            texto = extract_text(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        if not texto.strip():
            return {"error": "El documento no contiene texto extraible.", "total_fragmentos": 0,
                    "fragmentos_con_coincidencia": 0, "porcentaje_similitud": 0.0,
                    "por_tipo": {}, "autores_detectados": [],
                    "resumen": {"veredicto_global": "sin_ia", "fragmentos_con_plagio": 0,
                                "fragmentos_dudosos": 0, "severidad_maxima": 0,
                                "analizados_por_ia": 0, "coincidencias_mismo_autor": 0,
                                "coincidencias_con_datos": 0, "autores_detectados": []},
                    "coincidencias": []}

        return analizar_documento(texto, usar_llm=usar_llm, usar_web=usar_web)

    except ValueError as e:
        return {"error": str(e), "total_fragmentos": 0, "fragmentos_con_coincidencia": 0,
                "porcentaje_similitud": 0.0, "por_tipo": {}, "autores_detectados": [],
                "resumen": {"veredicto_global": "sin_ia", "fragmentos_con_plagio": 0,
                            "fragmentos_dudosos": 0, "severidad_maxima": 0,
                            "analizados_por_ia": 0, "coincidencias_mismo_autor": 0,
                            "coincidencias_con_datos": 0, "autores_detectados": []},
                "coincidencias": []}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "total_fragmentos": 0,
                "fragmentos_con_coincidencia": 0, "porcentaje_similitud": 0.0,
                "por_tipo": {}, "autores_detectados": [],
                "resumen": {"veredicto_global": "sin_ia", "fragmentos_con_plagio": 0,
                            "fragmentos_dudosos": 0, "severidad_maxima": 0,
                            "analizados_por_ia": 0, "coincidencias_mismo_autor": 0,
                            "coincidencias_con_datos": 0, "autores_detectados": []},
                "coincidencias": []}