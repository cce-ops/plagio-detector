"""Indexar documentos de una carpeta pública de Google Drive.

No requiere autenticacion ni Google Cloud Console. La carpeta debe estar
compartida como "Cualquiera con el enlace puede ver".
"""
import io
import re
import httpx

from app.core.chunker import chunk_text
from app.core.extractor import extract_text
from app.core.vector_store import indexar_proyecto
from app.core.authors import extraer_autores

SUFIJOS = (".pdf", ".docx", ".txt", ".md")


def _extraer_folder_id(url: str) -> str:
    """Extrae el ID de carpeta de una URL de Google Drive."""
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError(
            "No se pudo extraer el ID de la carpeta. "
            "Asegúrate de que el enlace sea de una carpeta compartida."
        )
    return match.group(1)


def _listar_archivos_publicos(folder_id: str) -> list[dict]:
    """Lista los archivos de una carpeta pública usando la API REST pública."""
    # La API pública de Drive permite listar carpetas compartidas sin auth
    url = f"https://www.googleapis.com/drive/v3/files"
    params = {
        "q": f"'{folder_id}' in parents and trashed = false",
        "fields": "files(id,name,mimeType)",
        "pageSize": 1000,
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
        "key": "anonymous",
    }
    try:
        r = httpx.get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("files", [])
    except httpx.HTTPStatusError:
        # Si la API pública no funciona, intentamos con el HTML de la carpeta
        return _listar_desde_html(folder_id)


def _listar_desde_html(folder_id: str) -> list[dict]:
    """Fallback: extrae IDs del HTML de la carpeta pública."""
    url = f"https://drive.google.com/drive/folders/{folder_id}"
    r = httpx.get(url, timeout=30, follow_redirects=True)
    r.raise_for_status()

    # Buscar patrones de ID en el HTML
    ids = re.findall(r'"([a-zA-Z0-9_-]{25,})"', r.text)
    nombres = re.findall(r'"name":"([^"]+)"', r.text)

    archivos = []
    for i, file_id in enumerate(ids):
        nombre = nombres[i] if i < len(nombres) else f"documento_{i}.pdf"
        archivos.append({
            "id": file_id,
            "name": nombre,
            "mimeType": "application/pdf",
        })
    return archivos


def _descargar_publico(file_id: str) -> bytes:
    """Descarga un archivo público de Drive."""
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    r = httpx.get(url, timeout=120, follow_redirects=True)
    r.raise_for_status()
    return r.content


def indexar_carpeta_publica(folder_url: str) -> dict:
    """Indexa todos los documentos de una carpeta pública de Drive."""
    import tempfile
    from pathlib import Path

    folder_id = _extraer_folder_id(folder_url)
    archivos = _listar_archivos_publicos(folder_id)

    # Filtrar solo formatos soportados
    documentos = [
        f for f in archivos
        if any(f.get("name", "").lower().endswith(ext) for ext in SUFIJOS)
    ]

    count = 0
    errores = []

    for doc in documentos:
        try:
            contenido = _descargar_publico(doc["id"])
            suf = Path(doc["name"]).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suf) as tmp:
                tmp.write(contenido)
                tmp_path = Path(tmp.name)
            try:
                texto = extract_text(tmp_path)
            finally:
                tmp_path.unlink(missing_ok=True)

            if not texto.strip():
                continue

            chunks = chunk_text(texto)
            autores = extraer_autores(texto)
            indexar_proyecto(
                proyecto_id=doc["name"],
                chunks=chunks,
                autor="",
                curso="",
                asignatura="",
                anio="",
                autores=autores,
                origen="drive",
            )
            count += 1
        except Exception as e:
            errores.append(f"{doc.get('name', '?')}: {e}")

    return {"count": count, "errores": errores}
