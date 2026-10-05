"""Indexa los proyectos de data/repositorio/ en el vector store.

Estructura de carpetas reconocida (de más específica a más general):
    <autor>/<asignatura>/<año>/<proyecto>.pdf
    <curso>/<asignatura>/<año>/<proyecto>.pdf
    <anything>/<proyecto>.pdf

Se detecta por patrón: si un segmento parece un año (4 dígitos), los
segmentos anteriores son autor/curso y el siguiente es asignatura.
"""
import re
import shutil
from pathlib import Path
from tqdm import tqdm

from app.config import settings
from app.core.extractor import extract_text
from app.core.chunker import chunk_text
from app.core.vector_store import indexar_proyecto
from app.core.authors import extraer_autores

SUFIJOS = (".pdf", ".docx", ".txt", ".md")


def _clasificar(partes: tuple[str, ...]) -> dict:
    """Deduce autor/curso/asignatura/año de los segmentos de la ruta."""
    dirs = list(partes[:-1])
    anio = ""
    for i, seg in enumerate(dirs):
        if re.fullmatch(r"(19|20)\d{2}", seg):
            anio = seg
            dirs = dirs[:i]
            dirs.insert(i, seg)
            break

    # Lo que queda antes del año: el último es asignatura, el primero autor/curso
    antes = [d for d in dirs if d != anio]
    asignatura = antes[-1] if len(antes) >= 2 else ""
    autor = antes[0] if len(antes) >= 2 else ""
    curso = ""

    return {
        "autor": autor or "desconocido",
        "curso": curso,
        "asignatura": asignatura,
        "anio": anio,
    }


def main():
    repo = settings.repo_dir
    archivos = [p for p in repo.rglob("*") if p.suffix.lower() in SUFIJOS]
    print(f"Encontrados {len(archivos)} archivos en {repo}")

    for path in tqdm(archivos):
        try:
            texto = extract_text(path)
            if not texto.strip():
                print(f"  (sin texto, se omite) {path.name}")
                continue
            chunks = chunk_text(texto)
            meta = _clasificar(path.relative_to(repo).parts)
            autores = extraer_autores(texto)
            indexar_proyecto(
                proyecto_id=path.stem,
                chunks=chunks,
                autor=meta["autor"],
                curso=meta["curso"],
                asignatura=meta["asignatura"],
                anio=meta["anio"],
                autores=autores,
            )
            print(f"  OK {path.name} -> autores={autores}, {meta}")
        except Exception as e:
            print(f"  ERROR {path}: {e}")

    print("Indexación completada.")


if __name__ == "__main__":
    main()