import re
from app.config import settings


def chunk_text(text: str, size: int = None, overlap: int = None) -> list[dict]:
    """Divide el texto en fragmentos por párrafos, agrupando hasta ~size palabras."""
    size = size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap

    # Normaliza espacios
    text = re.sub(r"\s+", " ", text).strip()
    palabras = text.split()
    chunks = []
    i = 0
    idx = 0
    while i < len(palabras):
        fragmento = " ".join(palabras[i:i + size])
        chunks.append({
            "id": f"chunk_{idx}",
            "texto": fragmento,
            "inicio": i,
        })
        i += size - overlap
        idx += 1
    return chunks