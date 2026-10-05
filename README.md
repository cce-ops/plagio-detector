# Detector de Plagio para Proyectos de Ingeniería

Herramienta de detección de plagio para trabajos de ingeniería. Compara una
entrega contra un repositorio de proyectos anteriores, busca coincidencias en
internet y clasifica cada fragmento según evidencia medible.

## Idea central

El LLM **no decide** si hay plagio. Un modelo siempre encuentra una explicación
benévola ("es la misma práctica", "solo coincide el tema") para descartar la
evidencia. El veredicto lo fija `app/core/decision.py` con medidas objetivas y
reproducibles; el modelo de lenguaje solo redacta la justificación en lenguaje
natural.

## Cómo clasifica un fragmento

| Señal                                        | Significado                                  |
|----------------------------------------------|----------------------------------------------|
| Solapamiento léxico (n-gramas de 5 palabras) | Copia literal de texto                       |
| Similitud semántica (embeddings)             | Mismo contenido con otra redacción           |
| Valores numéricos idénticos                 | Copia de datos/resultados                    |
| Entidades nombradas idénticas                | Mismo caso concreto (lugar, organismo)       |
| Autores coincidentes                         | Trabajo del mismo autor: no es plagio        |

Reglas (entre autores distintos):

- Texto copiado (léxico ≥ 50 % + un dato) → **plagio literal**
- ≥ 3 valores idénticos **o** ≥ 2 entidades → **plagio** (severidad 55-95 %)
- 1 dato o entidad compartida → **dudoso**
- Sin evidencia → **no plagio**

Si los autores coinciden (una memoria y su presentación, por ejemplo), la
coincidencia se excluye automáticamente: es material reutilizado del mismo
trabajo, no plagio.

## Requisitos

- Python 3.11 o superior
- Tesseract OCR (solo para PDFs escaneados):
  `winget install UB-Mannheim.TesseractOCR`
  Si no está en el PATH, ajusta `TESSERACT_CMD` en `app/core/extractor.py`.

## Instalación

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Uso

### 1. Indexar los trabajos anteriores

Coloca los documentos en `data/repositorio/<curso>/<asignatura>/<año>/` y ejecuta:

```powershell
python -m scripts.indexar_repositorio
```

El índice se guarda en `data/chroma_db/` y se puede reconstruir cuando quieras.
La primera vez descarga el modelo de embeddings (~1.1 GB).

### 2. Arrancar la aplicación

```powershell
python -m streamlit run streamlit_app.py
```

Abre http://localhost:8501

La aplicación corre en un solo proceso: no hace falta levantar la API.
Para usarla como servicio HTTP aparte:

```powershell
python -m uvicorn app.main:app --reload   # http://localhost:8000/docs
```

## Proveedores de IA

Cada usuario introduce su propia clave en la barra lateral. Hay un botón
**Probar** que valida la clave y el modelo antes de analizar.

| Proveedor   | Modelos                                             |
|-------------|-----------------------------------------------------|
| Gemini      | `gemini-3.8-flash`, `gemini-3.7-flash`, ...          |
| Groq        | `openai/gpt-oss-120b`, `openai/gpt-oss-20b`          |
| OpenRouter  | `nvidia/nemotron-3-ultra-550b-a55b:free`, ...        |
| NVIDIA NIM  | `nvidia/nemotron-3-ultra-550b-a55b`, ...             |
| Ollama      | local, sin límites                                  |

Si el proveedor falla, se prueban los demás modelos del mismo proveedor antes
de rendirse.

## Despliegue

### Streamlit Community Cloud (gratis)

1. Sube el repositorio a GitHub
2. En [share.streamlit.io](https://share.streamlit.io) → *Deploy an app*
3. Archivo principal: `streamlit_app.py`
4. En *Advanced settings* → Secrets, añade las claves que necesites

El repositorio **no incluye `data/`**: los trabajos de los estudiantes
contienen datos personales y académicos, y no deben subirse.

### Hugging Face Spaces (gratis, con Docker)

Se puede desplegar el mismo código como Space. Los documentos de referencia
pueden montarse desde un dataset privado del Space.

## Estructura

```
app/
  config.py              configuración por entorno
  runner.py              permite ejecutar en un proceso o vía API
  main.py                API FastAPI (opcional)
  core/
    extractor.py         texto de PDF/DOCX/TXT + OCR con límites
    chunker.py           divide en fragmentos de ~400 palabras
    embeddings.py        modelo multilingüe
    vector_store.py      NearestNeighbors de scikit-learn (persistente)
    lexical.py           n-gramas, MinHash, huella numérica, entidades
    authors.py           detección de autores en la cabecera
    decision.py          motor de reglas: decide plagio/dudoso/no
    judge.py             el LLM solo redacta la justificación
    web_search.py        coincidencias en internet
    analyzer.py          orquesta el análisis completo
scripts/
  indexar_repositorio.py construye el índice
```

## Notas

- El índice usa scikit-learn en vez de una base vectorial dedicada: evita
  dependencias que requieren compilador (hnswlib) y funciona en CPU.
- El primer análisis descarga el modelo de embeddings; a partir de ahí va en
  memoria.
- El veredicto es reproducible: mismas entradas, mismo resultado. El LLM solo
  cambia el texto de la explicación.