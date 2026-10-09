import json

import streamlit as st

from app.runner import (
    analizar,
    guardar_config,
    indice_existe,
    probar_config,
    resumen_config,
)
from app.core.drive_public import indexar_carpeta_publica

st.set_page_config(page_title="Detector de Plagio IA", layout="wide")
st.title("🔍 Detector de Plagio para Proyectos de Ingeniería")

PROVIDERS = {
    "gemini": "🟢 Gemini (Google)",
}

MODELS = {
    "gemini": [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ],
}

HELP = {
    "gemini": "https://aistudio.google.com/apikey",
}

with st.sidebar:
    st.header("⚙️ Configuración LLM")
    st.caption("Cada visitante usa su propia clave. No se guarda ni se comparte.")

    provider = st.selectbox(
        "Proveedor",
        list(PROVIDERS.keys()),
        format_func=lambda p: PROVIDERS[p],
    )

    api_key = ""
    ollama_host = ""
    if provider != "ollama":
        # La clave vive en session_state: sobrevive al rerun de Streamlit y
        # nunca se comparte entre visitantes.
        clave_guardada = st.session_state.get("api_key", "")
        tipo_key = "password" if clave_guardada else "default"
        api_key = st.text_input(
            "API Key",
            type=tipo_key,
            value=clave_guardada,
            help=f"Obtén tu key en {HELP[provider]}" if HELP[provider] else "",
        )
        if api_key and api_key != clave_guardada:
            st.session_state["api_key"] = api_key
        if not api_key and tipo_key == "password":
            st.session_state.pop("api_key", None)

        origen = resumen_config().get(provider, "sin clave")
        if origen == "clave del despliegue":
            st.caption("ℹ️ Este despliegue ya tiene una clave configurada; "
                       "puedes usarla o escribir la tuya para reemplazarla.")
    else:
        ollama_host = st.text_input("Ollama Host", value="http://localhost:11434")

    model = st.selectbox("Modelo", MODELS[provider])

    def _guardar():
        guardar_config(provider, model, api_key, ollama_host)

    c1, c2 = st.columns(2)
    guardar = c1.button("Guardar", type="primary", use_container_width=True)
    probar = c2.button("Probar", use_container_width=True)

    if guardar:
        _guardar()
        st.success(f"Guardado: {provider} / {model}")

    if probar:
        # Guarda primero: Probar siempre valida lo que hay en pantalla
        _guardar()
        with st.spinner(f"Probando {provider} / {model}..."):
            rj = probar_config()
        if rj.get("ok"):
            st.success(f"✅ {rj.get('model')}: {rj.get('respuesta')}")
        else:
            st.error(f"❌ {rj.get('error')}")
            for d in rj.get("detalles", [])[:4]:
                st.caption(d)

    st.divider()
    st.header("📁 Google Drive")

    drive_url = st.text_input(
        "Dirección carpeta Drive",
        placeholder="https://drive.google.com/drive/folders/...",
        help="Pega el enlace de una carpeta COMPARTIDA PÚBLICAMENTE (cualquiera con el enlace puede ver)",
    )
    if drive_url and st.button("Indexar carpeta"):
        with st.spinner("Indexando documentos de Drive..."):
            try:
                resultado = indexar_carpeta_publica(drive_url)
                count = resultado["count"]
                errores = resultado["errores"]
                st.success(f"{count} documentos leídos/considerados")
                if errores:
                    st.warning(f"{len(errores)} archivos no se pudieron indexar:")
                    for err in errores[:5]:
                        st.caption(err)
            except Exception as e:
                st.error(f"Error al indexar: {e}")

    st.caption("ℹ️ La carpeta debe ser compartida como 'Cualquiera con el enlace'.")

    st.divider()
    st.header("🔧 Opciones")
    if not indice_existe():
        st.warning(
            "⚠ No hay índice de trabajos previos. Coloca los PDF en "
            "`data/repositorio/<curso>/<asignatura>/<año>/` y ejecuta "
            "`python -m scripts.indexar_repositorio`. Sin índice solo se "
            "detectará plagio en la búsqueda web."
        )
    usar_llm = st.checkbox("Usar LLM juez", value=True)
    usar_web = st.checkbox("Buscar en web (DuckDuckGo)", value=False)

modo = st.radio("Entrada:", ["Subir archivo", "Pegar texto"], horizontal=True)

if modo == "Subir archivo":
    file = st.file_uploader(
        "Sube PDF, DOCX, TXT, MD o imagen",
        type=["pdf", "docx", "txt", "md", "png", "jpg", "jpeg"],
        help="Tamaño máximo: 200MB por archivo. Formatos: PDF, DOCX, TXT, MD, PNG, JPG, JPEG",
    )
    if file and st.button("Analizar", type="primary"):
        with st.spinner("Analizando (el OCR de PDFs escaneados puede tardar)..."):
            st.session_state["resultado"] = analizar(
                contenido=file.getvalue(),
                ruta=file,
                usar_llm=usar_llm,
                usar_web=usar_web,
            )
else:
    texto = st.text_area("Pega el texto", height=300)
    if texto and st.button("Analizar", type="primary"):
        with st.spinner("Analizando..."):
            st.session_state["resultado"] = analizar(
                texto=texto, usar_llm=usar_llm, usar_web=usar_web
            )

res = st.session_state.get("resultado")
if res and res.get("error"):
    st.error(res["error"])
    st.caption("El documento puede estar escaneado sin texto. Prueba con OCR activado o exporta el PDF con texto.")
elif res:
    resumen = res.get("resumen", {})
    veredicto = resumen.get("veredicto_global", "sin_ia")

    etiquetas = {
        "plagio": ("🔴 PLAGIO DETECTADO",
                   "El motor de reglas ha clasificado uno o más fragmentos como plagio."),
        "revisar": ("🟡 REVISAR",
                    "Hay fragmentos con evidencia parcial que requieren revisión manual."),
        "no_plagio": ("🟢 SIN PLAGIO",
                      "Las coincidencias no llegan al umbral de evidencia: mismo autor, "
                      "citas o terminología técnica."),
        "sin_ia": ("⚪ SIN ANÁLISIS DE IA",
                   "Activa el juez LLM para redactar la justificación de las coincidencias."),
    }
    titulo, detalle = etiquetas.get(veredicto, etiquetas["sin_ia"])

    st.markdown("---")
    if veredicto == "plagio":
        st.error(f"## {titulo}")
    elif veredicto == "revisar":
        st.warning(f"## {titulo}")
    elif veredicto == "no_plagio":
        st.success(f"## {titulo}")
    else:
        st.info(f"## {titulo}")
    st.caption(detalle)

    autores = res.get("autores_detectados") or []
    mismos = resumen.get("coincidencias_mismo_autor", 0)
    if autores:
        st.caption(f"Autores detectados en el documento: **{', '.join(autores)}**")
    if mismos:
        st.info(
            f"ℹ️ **{mismos} de {len(res['coincidencias'])} coincidencias son del mismo autor.** "
            "Una entrega (memoria, presentación, anexos) reutiliza su propio material, "
            "así que no se puntúa como plagio. Se excluye del veredicto."
        )

    con_datos = resumen.get("coincidencias_con_datos", 0)
    if con_datos:
        st.error(
            f"🚨 **{con_datos} fragmentos comparten datos concretos** con documentos "
            "de otros autores. El veredicto lo fija el motor de reglas sobre medidas "
            "objetivas (datos numéricos, entidades nombradas, solapamiento textual); "
            "la IA solo redacta la justificación."
        )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Similitud global", f"{res['porcentaje_similitud']}%")
    m2.metric("Fragmentos con plagio", resumen.get("fragmentos_con_plagio", 0))
    m3.metric("Severidad máxima", f"{resumen.get('severidad_maxima', 0)}%")
    m4.metric("Dudosos", resumen.get("fragmentos_dudosos", 0))

    por_tipo = res.get("por_tipo", {})
    if por_tipo:
        st.caption(" · ".join(
            f"{k}: {v}" for k, v in sorted(por_tipo.items(), key=lambda x: -x[1])
        ))

    st.markdown("---")

    for c in res["coincidencias"]:
        v = c.get("veredicto_llm")
        badge = ""
        if v and "error" not in v:
            badge = {"si": " 🔴", "dudoso": " 🟡", "no": " 🟢"}.get(v.get("plagio", ""), "")
        with st.expander(f"**{c.get('titulo', c['tipo'])}**{badge}"):
            ents = c.get("entidades") or {}
            nums = c.get("numeros") or {}
            if c.get("mismo_autor"):
                st.success(
                    f"✔ Coincidencia interna del mismo autor "
                    f"({', '.join(c.get('autores_comunes') or [])}). "
                    "No cuenta como plagio."
                )
            else:
                partes = []
                if nums.get("comunes", 0):
                    partes.append(
                        f"{nums['comunes']} valores idénticos "
                        f"({', '.join(nums.get('ejemplos', [])[:6])})"
                    )
                if ents.get("comunes", 0):
                    partes.append(
                        f"{ents['comunes']} entidades idénticas "
                        f"({', '.join(ents.get('ejemplos', [])[:6])})"
                    )
                if partes:
                    st.warning("⚠ Datos concretos compartidos: " + "; ".join(partes))
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Fragmento entregado**")
                st.write(c["fragmento_entregado"][:900])
            with col2:
                st.markdown("**Fragmento fuente**")
                st.write(c["fragmento_fuente"][:900])
                st.caption(c["metadata_fuente"])
            st.markdown("---")
            if v:
                if "error" in v:
                    st.error(f"Error del redactor: {v['error']}")
                else:
                    a, b, d = st.columns([1, 2, 2])
                    a.metric("Plagio", v.get("plagio", "?"))
                    b.metric("Tipo", v.get("tipo", "?"))
                    d.metric("Severidad", f"{v.get('severidad', 0)}%")
                    if v.get("senales"):
                        with st.expander("Evidencia que motivó el veredicto"):
                            for s in v["senales"]:
                                st.markdown(f"- {s}")
                    if v.get("justificacion"):
                        st.caption(v["justificacion"])
                    if v.get("detalle"):
                        st.caption(f"Detalle: {v['detalle']}")
                    if v.get("model"):
                        st.caption(f"Redacción IA: `{v['model']}`")
                    else:
                        st.caption("Veredicto del motor de reglas (sin redacción IA).")
            else:
                st.caption("Sin veredicto (fragmento web).")

    st.download_button(
        "Descargar informe JSON",
        data=json.dumps(res, ensure_ascii=False, indent=2),
        file_name="informe_plagio.json",
    )