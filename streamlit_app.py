"""Punto de entrada para Streamlit Community Cloud.

Community Cloud solo ejecuta UN proceso. Este archivo delega en la UI real
para que la aplicacion funcione sin la API FastAPI (uvicorn) en paralelo.

Ejecucion local:  python -m streamlit run streamlit_app.py
"""
from pathlib import Path

import sys

_RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(_RAIZ))

# Reutiliza ui/streamlit_app.py sin duplicar codigo
_EJECUTAR = _RAIZ / "ui" / "streamlit_app.py"

if _EJECUTAR.exists():
    exec(compile(_EJECUTAR.read_text(encoding="utf-8"), str(_EJECUTAR), "exec"))
else:
    import streamlit as st
    st.error(f"No se encuentra {_EJECUTAR}")