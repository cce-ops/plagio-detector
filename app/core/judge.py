"""Redactor de justificaciones.

Este modulo NO decide si hay plagio: esa decision la toma app.core.decision a
partir de evidencia medible. Aqui solo se pide al modelo que redacte una
explicacion en lenguaje natural del veredicto ya calculado, para que un
profesor entienda por que se ha clasificado asi.
"""
import time
import json
import re
import httpx
from app.config import (
    settings,
    GEMINI_MODELS,
    GROQ_MODELS,
    OPENROUTER_MODELS,
    NVIDIA_NIM_MODELS,
    OLLAMA_MODELS,
)

PROMPT = """Eres un evaluador académico. Redacta una justificación BREVE en español.

Ya existe un veredicto calculado por el detector automático. Tu trabajo es
explicarlo con claridad, NO cambiarlo.

VEREDICTO DEL DETECTOR: {veredicto}
SEÑALES MEDIDAS:
{senales}

CONTEXTO:
{contexto}

FRAGMENTO A (entregado):
{a}

FRAGMENTO B (fuente):
{b}

Responde SOLO en JSON:
{{
  "justificacion": "2-3 frases que citen las señales concretas medidas",
  "detalle": "qué elementos concretos se comparten (datos, entidades, texto)"
}}

Si el veredicto es "si", señala qué evidencia lo sostiene sin suavizarlo.
Si es "dudoso", indica qué falta para confirmarlo.
Si es "no", explica por qué la evidencia es insuficiente.
No inventes datos que no estén en las señales ni en los fragmentos.
"""


def _call_ollama(prompt: str, model: str) -> str:
    r = httpx.post(
        f"{settings.ollama_host}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["response"]


def _call_gemini(prompt: str, model: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0},
    }
    r = httpx.post(url, headers=headers, json=payload, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def _call_openai_compatible(prompt: str, model: str, url: str, key: str) -> str:
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }
    r = httpx.post(url, headers=headers, json=payload, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def _call_groq(prompt: str, model: str) -> str:
    return _call_openai_compatible(
        prompt, model, "https://api.groq.com/openai/v1/chat/completions",
        settings.groq_api_key,
    )


def _call_openrouter(prompt: str, model: str) -> str:
    return _call_openai_compatible(
        prompt, model, "https://openrouter.ai/api/v1/chat/completions",
        settings.openrouter_api_key,
    )


def _call_nim(prompt: str, model: str) -> str:
    return _call_openai_compatible(
        prompt, model, "https://integrate.api.nvidia.com/v1/chat/completions",
        settings.nvidia_nim_api_key,
    )


def _extract_json(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    return json.loads(m.group(0)) if m else {"error": "respuesta no JSON"}


def _proveedor() -> tuple[str, list[str], callable]:
    p = settings.llm_provider
    tabla = {
        "gemini": (GEMINI_MODELS, _call_gemini),
        "groq": (GROQ_MODELS, _call_groq),
        "openrouter": (OPENROUTER_MODELS, _call_openrouter),
        "nim": (NVIDIA_NIM_MODELS, _call_nim),
        "ollama": (OLLAMA_MODELS, _call_ollama),
    }
    modelos, caller = tabla.get(p, ([], None))
    return p, modelos, caller


def _clave_ok(p: str) -> bool:
    return {
        "gemini": bool(settings.gemini_api_key),
        "groq": bool(settings.groq_api_key),
        "openrouter": bool(settings.openrouter_api_key),
        "nim": bool(settings.nvidia_nim_api_key),
        "ollama": True,
    }.get(p, False)


def _modelo_seleccionado(p: str) -> str:
    return {
        "gemini": settings.gemini_model,
        "groq": settings.groq_model,
        "openrouter": settings.openrouter_model,
        "nim": settings.nvidia_nim_model,
        "ollama": settings.ollama_model,
    }.get(p, "?")


def _construir_contexto(autores_a, autores_b, meta_b) -> str:
    lineas = []
    if autores_a:
        lineas.append(f"- Autores del documento entregado: {', '.join(autores_a)}")
    if autores_b:
        lineas.append(f"- Autores de la fuente: {', '.join(autores_b)}")
    if meta_b:
        proyecto = meta_b.get("proyecto_id", "")
        datos = " / ".join(
            x for x in (meta_b.get("curso", ""), meta_b.get("asignatura", ""),
                        meta_b.get("anio", "")) if x
        )
        if proyecto:
            lineas.append(f"- Documento fuente: {proyecto} ({datos})" if datos
                          else f"- Documento fuente: {proyecto}")
    if autores_a and autores_b:
        comunes = sorted(set(autores_a) & set(autores_b))
        if comunes:
            lineas.append(f"- {', '.join(comunes)} figura en ambos documentos.")
    return "\n".join(lineas) or "- Sin metadatos de autor."


def _formatear_senales(senales: list[str], evidencia: dict) -> str:
    lineas = []
    sem = evidencia.get("similitud_semantica")
    lex = evidencia.get("similitud_lexica")
    if sem is not None:
        lineas.append(f"- Similitud semántica: {sem}")
    if lex is not None:
        lineas.append(f"- Solapamiento léxico (n-gramas): {lex}")

    nums = evidencia.get("numeros_compartidos") or {}
    if nums.get("comunes"):
        lineas.append(
            f"- Valores numéricos idénticos: {nums['comunes']} "
            f"({', '.join(nums.get('ejemplos', [])[:8])})"
        )
    ents = evidencia.get("entidades_compartidas") or {}
    if ents.get("comunes"):
        lineas.append(
            f"- Entidades nombradas idénticas: {ents['comunes']} "
            f"({', '.join(ents.get('ejemplos', [])[:8])})"
        )
    if senales:
        lineas.append("- Señales del detector: " + "; ".join(senales))
    return "\n".join(lineas) or "- Sin señales."


def justificar(a: str, b: str, autores_a=None, autores_b=None, meta_b=None,
               evidencia: dict | None = None, veredicto: str = "dudoso") -> dict:
    """Genera la justificacion en lenguaje natural. No altera el veredicto."""
    evidencia = evidencia or {}
    senales = evidencia.get("senales", [])

    prompt = PROMPT.format(
        a=a[:2000],
        b=b[:2000],
        veredicto={"si": "PLAGIO", "dudoso": "DUDOSO", "no": "NO PLAGIO"}.get(veredicto, veredicto),
        senales=_formatear_senales(senales, evidencia),
        contexto=_construir_contexto(autores_a or [], autores_b or [], meta_b),
    )

    provider, modelos, caller = _proveedor()
    if not caller:
        return {}
    if not _clave_ok(provider):
        return {}

    elegido = _modelo_seleccionado(provider)
    orden = [elegido] + [m for m in modelos if m != elegido]

    for model in orden:
        for intento in range(2):
            try:
                raw = caller(prompt, model)
                salida = _extract_json(raw)
                if "error" in salida:
                    break
                return {
                    "justificacion": salida.get("justificacion", "").strip(),
                    "detalle": salida.get("detalle", "").strip(),
                    "model": model,
                }
            except Exception:
                if intento == 0:
                    time.sleep(2)
    return {}


def test_llm() -> dict:
    """Comprueba que el proveedor configurado responde."""
    provider, modelos, caller = _proveedor()
    if not caller:
        return {"ok": False, "error": f"Proveedor desconocido: {provider}"}
    if not _clave_ok(provider):
        return {"ok": False, "error": f"Falta API Key para {provider}"}

    orden = [_modelo_seleccionado(provider)] + list(modelos)
    errores = []
    for model in orden:
        try:
            raw = caller("Responde SOLO: OK", model)
            return {"ok": True, "model": model, "respuesta": raw.strip()[:80]}
        except Exception as e:
            errores.append(f"{model}: {str(e)[:150]}")
    return {"ok": False, "error": "Todos fallaron", "detalles": errores}