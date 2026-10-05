"""Vector store usando scikit-learn NearestNeighbors (puro Python)"""
import pickle
import numpy as np
from pathlib import Path
from sklearn.neighbors import NearestNeighbors
from app.config import settings
from app.core.embeddings import embed_texts

_INDEX_FILE = settings.chroma_dir / "sklearn_index.pkl"
_DATA_FILE = settings.chroma_dir / "sklearn_data.pkl"

_index = None
_data = None


def _ensure_dir():
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)


def _load():
    global _index, _data
    if _index is not None:
        return
    if _INDEX_FILE.exists() and _DATA_FILE.exists():
        with open(_INDEX_FILE, "rb") as f:
            _index = pickle.load(f)
        with open(_DATA_FILE, "rb") as f:
            _data = pickle.load(f)
    else:
        _index = None
        _data = {"textos": [], "metadatas": [], "ids": []}


def _save():
    _ensure_dir()
    with open(_INDEX_FILE, "wb") as f:
        pickle.dump(_index, f)
    with open(_DATA_FILE, "wb") as f:
        pickle.dump(_data, f)


def _rebuild_index():
    global _index
    if not _data["textos"]:
        _index = None
        return
    all_embeddings = np.array(embed_texts(_data["textos"]))
    _index = NearestNeighbors(
        n_neighbors=min(10, len(all_embeddings)),
        metric="cosine",
        algorithm="brute",
    ).fit(all_embeddings)


def indexar_proyecto(
    proyecto_id: str,
    autor: str,
    curso: str,
    asignatura: str,
    anio: str,
    chunks: list[dict],
    autores: list[str] | None = None,
):
    _load()
    textos = [c["texto"] for c in chunks]
    ids = [f"{proyecto_id}::{c['id']}" for c in chunks]
    lista_autores = ", ".join(autores) if autores else ""
    metadatas = [
        {
            "proyecto_id": proyecto_id,
            "autor": autor,
            "curso": curso,
            "asignatura": asignatura,
            "anio": anio,
            "chunk_id": c["id"],
            "autores": lista_autores,
        }
        for c in chunks
    ]
    
    _data["textos"].extend(textos)
    _data["metadatas"].extend(metadatas)
    _data["ids"].extend(ids)
    
    _rebuild_index()
    _save()


def buscar_similares(texto: str, n_results: int = 5) -> list[dict]:
    _load()
    if _index is None or len(_data["textos"]) == 0:
        return []
    
    emb = np.array(embed_texts([texto])[0]).reshape(1, -1)
    n_results = min(n_results, len(_data["textos"]))
    distances, indices = _index.kneighbors(emb, n_neighbors=n_results)
    
    resultados = []
    for dist, idx in zip(distances[0], indices[0]):
        resultados.append({
            "texto": _data["textos"][idx],
            "metadata": _data["metadatas"][idx],
            "distancia": float(dist),
            "similitud": 1 - float(dist),
        })
    return resultados