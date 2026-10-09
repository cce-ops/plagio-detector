"""Indexar documentos de una carpeta pública de Google Drive.

Usa gdown para descargar la carpeta completa sin autenticacion.
La carpeta debe estar compartida como "Cualquiera con el enlace puede ver".
"""
import tempfile
from pathlib import Path

from app.core.chunker import chunk_text
from app.core.extractor import extract_text
from app.core.vector_store import indexar_proyecto
from app.core.authors import extraer_autores

SUFIJOS = (".pdf", ".docx", ".txt", ".md")


def indexar_carpeta_publica(folder_url: str, sesion: str = "") -> dict:
    """Indexa todos los documentos de una carpeta pública de Drive.

    Usa gdown.download_folder() que maneja la descarga de carpetas públicas
    sin necesidad de API key ni OAuth.
    """
    try:
        import gdown
    except ImportError as e:
        raise RuntimeError(
            "Falta la dependencia 'gdown'. Instala con: pip install -r requirements.txt"
        ) from e

    output_dir = tempfile.mkdtemp(prefix="drive_")

    # gdown descarga todos los archivos de la carpeta pública
    gdown.download_folder(
        folder_url,
        output=output_dir,
        quiet=False,
        remaining_ok=True,
        use_cookies=False,
    )

    # Indexar todos los archivos descargados
    archivos = [
        p for p in Path(output_dir).rglob("*")
        if p.suffix.lower() in SUFIJOS and p.is_file()
    ]

    count = 0
    errores = []

    for path in archivos:
        try:
            texto = extract_text(path)
            if not texto.strip():
                continue

            chunks = chunk_text(texto)
            autores = extraer_autores(texto)
            indexar_proyecto(
                proyecto_id=path.stem,
                chunks=chunks,
                autor="",
                curso="",
                asignatura="",
                anio="",
                autores=autores,
                origen="drive",
                sesion=sesion,
            )
            count += 1
        except Exception as e:
            errores.append(f"{path.name}: {e}")

    return {"count": count, "errores": errores}
