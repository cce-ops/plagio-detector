from app.core.chunker import chunk_text
from app.core.vector_store import buscar_similares
from app.core.lexical import (
    solapamiento_ngramas,
    minhash_similitud,
    solapamiento_numeros,
    solapamiento_entidades,
)
from app.core.web_search import extraer_frases_clave, buscar_en_web
from app.core.judge import justificar
from app.core.decision import evaluar
from app.core.authors import extraer_autores, autores_coinciden
from app.config import settings

TIPOS = {
    "literal": "Copia literal",
    "parafrasis": "Parafrasis",
    "ideas": "Similitud conceptual",
    "potencial": "Posible coincidencia web",
}

# El LLM solo redacta la justificacion: limitar a los fragmentos mas severos.
# Sin tope, un documento con N coincidencias genera N llamadas HTTP
# secuenciales (cada una con reintentos y fallback entre modelos).
MAX_JUSTIFICACIONES_LLM = 5


def _titulo(tipo: str, sim, meta: dict, mismo_autor: bool,
            nums: dict | None = None, ents: dict | None = None) -> str:
    etiqueta = TIPOS.get(tipo, tipo)
    if sim is None:
        return f"{etiqueta} · web"
    fuente = meta.get("proyecto_id") or meta.get("titulo") or "desconocido"
    if mismo_autor:
        sufijo = " · mismo autor"
    else:
        marcas = []
        if nums and nums.get("comunes", 0) >= 3:
            marcas.append(f"{nums['comunes']} datos")
        if ents and ents.get("comunes", 0) >= 2:
            marcas.append(f"{ents['comunes']} entidades")
        sufijo = f" · ⚠ {' + '.join(marcas)}" if marcas else ""
    return f"{etiqueta} · {round(sim * 100)}% · {fuente}{sufijo}"


def analizar_documento(texto: str, usar_llm: bool = True, usar_web: bool = True) -> dict:
    chunks = chunk_text(texto)
    coincidencias = []

    autores_entrega = extraer_autores(texto)

    # --- 1. Comparación con repositorio interno ---
    for ch in chunks:
        similares = buscar_similares(ch["texto"], n_results=3)
        for s in similares:
            if s["similitud"] < settings.threshold_ideas:
                continue
            lex = solapamiento_ngramas(ch["texto"], s["texto"])
            mh = minhash_similitud(ch["texto"], s["texto"])
            nums = solapamiento_numeros(ch["texto"], s["texto"])
            ents = solapamiento_entidades(ch["texto"], s["texto"])

            if s["similitud"] >= settings.threshold_literal or lex > 0.6:
                tipo = "literal"
            elif s["similitud"] >= settings.threshold_paraphrase:
                tipo = "parafrasis"
            else:
                tipo = "ideas"

            meta = s["metadata"]
            autores_fuente = [
                a.strip() for a in (meta.get("autores") or "").split(",") if a.strip()
            ]
            hay_comunes, comunes = autores_coinciden(autores_entrega, autores_fuente)

            coincidencias.append({
                "titulo": _titulo(tipo, s["similitud"], meta, hay_comunes, nums, ents),
                "origen": "repositorio",
                "tipo": tipo,
                "mismo_autor": hay_comunes,
                "autores_comunes": comunes,
                "autores_entrega": autores_entrega,
                "autores_fuente": autores_fuente,
                "similitud_semantica": round(s["similitud"], 3),
                "similitud_lexica": round(lex, 3),
                "minhash": round(mh, 3),
                "numeros": nums,
                "entidades": ents,
                "fragmento_entregado": ch["texto"],
                "fragmento_fuente": s["texto"],
                "metadata_fuente": meta,
            })

    # --- 2. Búsqueda web ---
    if usar_web and settings.web_search_enabled:
        frases = extraer_frases_clave(texto)
        for frase in frases:
            for r in buscar_en_web(frase):
                if "error" in r:
                    continue
                meta = {"url": r["url"], "titulo": r["titulo"]}
                coincidencias.append({
                    "titulo": _titulo("potencial", None, meta, False, None, None),
                    "origen": "web",
                    "tipo": "potencial",
                    "mismo_autor": False,
                    "autores_comunes": [],
                    "autores_entrega": autores_entrega,
                    "autores_fuente": [],
                    "similitud_semantica": None,
                    "similitud_lexica": None,
                    "minhash": None,
                    "numeros": None,
                    "entidades": None,
                    "fragmento_entregado": frase,
                    "fragmento_fuente": r["snippet"],
                    "metadata_fuente": meta,
                })

    # --- 3. Veredicto ---
    # El motor de decision fija el veredicto con evidencia medible. El LLM solo
    # redacta la justificacion; no puede rebajar un veredicto de plagio.
    for c in coincidencias:
        if c["origen"] != "repositorio":
            continue

        decision = evaluar({
            "mismo_autor": c["mismo_autor"],
            "autores_comunes": c["autores_comunes"],
            "similitud_semantica": c["similitud_semantica"],
            "similitud_lexica": c["similitud_lexica"],
            "minhash": c["minhash"],
            "numeros": c["numeros"],
            "entidades": c["entidades"],
        })

        c["veredicto_llm"] = {
            "plagio": decision["plagio"],
            "tipo": decision["tipo"],
            "severidad": decision["severidad"],
            "senales": decision["senales"],
            "justificacion": "",
            "model": "motor-reglas",
        }

    if usar_llm:
        pendientes = [
            c for c in coincidencias
            if c["origen"] == "repositorio" and not c["mismo_autor"]
        ]
        pendientes.sort(
            key=lambda c: c["veredicto_llm"].get("severidad", 0),
            reverse=True,
        )
        for c in pendientes[:MAX_JUSTIFICACIONES_LLM]:
            texto_just = justificar(
                c["fragmento_entregado"],
                c["fragmento_fuente"],
                autores_a=autores_entrega,
                autores_b=autores_fuente,
                meta_b=c["metadata_fuente"],
                evidencia={
                    "similitud_semantica": c["similitud_semantica"],
                    "similitud_lexica": c["similitud_lexica"],
                    "minhash": c["minhash"],
                    "numeros_compartidos": c["numeros"],
                    "entidades_compartidas": c["entidades"],
                },
                veredicto=c["veredicto_llm"]["plagio"],
            )
            if texto_just:
                c["veredicto_llm"]["justificacion"] = texto_just
                c["veredicto_llm"]["model"] = texto_just.get("model", "")

    # --- 4. Métricas globales ---
    total = len(chunks)
    afectados = len({c["fragmento_entregado"] for c in coincidencias
                     if c["origen"] == "repositorio"})
    porcentaje = round(100 * afectados / total, 2) if total else 0.0

    por_tipo = {}
    for c in coincidencias:
        por_tipo[c["tipo"]] = por_tipo.get(c["tipo"], 0) + 1

    veredictos = [c["veredicto_llm"] for c in coincidencias
                  if c.get("veredicto_llm") and "error" not in c["veredicto_llm"]]
    con_plagio = sum(1 for v in veredictos if v.get("plagio") == "si")
    dudosos = sum(1 for v in veredictos if v.get("plagio") == "dudoso")
    severidad_max = max((v.get("severidad", 0) for v in veredictos), default=0)

    del_mismo_autor = sum(1 for c in coincidencias if c.get("mismo_autor"))
    con_datos = sum(
        1 for c in coincidencias
        if (c.get("numeros") or {}).get("comunes", 0) >= 3
        or (c.get("entidades") or {}).get("comunes", 0) >= 2
    )
    autores_entrega_lista = sorted(set(autores_entrega))

    if not veredictos:
        global_verdict = "sin_ia"
    elif con_plagio:
        global_verdict = "plagio"
    elif dudosos:
        global_verdict = "revisar"
    else:
        global_verdict = "no_plagio"

    return {
        "total_fragmentos": total,
        "fragmentos_con_coincidencia": afectados,
        "porcentaje_similitud": porcentaje,
        "por_tipo": por_tipo,
        "autores_detectados": autores_entrega_lista,
        "resumen": {
            "veredicto_global": global_verdict,
            "fragmentos_con_plagio": con_plagio,
            "fragmentos_dudosos": dudosos,
"severidad_maxima": severidad_max,
                    "analizados_por_ia": sum(
                        1 for v in veredictos if v.get("justificacion")
                    ),
            "coincidencias_mismo_autor": del_mismo_autor,
            "coincidencias_con_datos": con_datos,
            "autores_detectados": autores_entrega_lista,
        },
        "coincidencias": coincidencias,
    }