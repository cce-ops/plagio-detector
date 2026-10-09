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

---

## Guía de instalación paso a paso 

### Paso 1: Instalar Python

1. Ve a https://www.python.org/downloads/
2. Descarga la versión 3.11 o superior (el botón grande amarillo).
3. Ejecuta el instalador.
4. **IMPORTANTE:** En la primera pantalla del instalador, marca la casilla
   "Add python to PATH" antes de pulsar "Install Now".
5. Espera a que termine y cierra el instalador.

### Paso 2: Instalar Git (para clonar el repositorio)

1. Ve a https://git-scm.com/downloads
2. Descarga la versión para Windows.
3. Ejecuta el instalador con las opciones por defecto (pulsa "Next" en cada
   pantalla y "Install" al final).
4. Al terminar, abre el menú de inicio y busca "Git Bash". Ábrelo para verificar
   que funciona.

### Paso 3: Clonar el repositorio

En la terminal (Git Bash o PowerShell):

```bash
git clone https://github.com/cce-ops/plagio-detector.git
cd plagio-detector
```

### Paso 4: Crear el entorno virtual e instalar dependencias

En la misma terminal:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

La primera vez tarda varios minutos (descarga PyTorch y otros paquetes grandes).

### Paso 5: Crear el archivo de configuración

```bash
Copy-Item .env.example .env
```

### Paso 6: Obtener una API Key de Gemini

1. Ve a https://aistudio.google.com/apikey
2. Inicia sesión con tu cuenta de Google.
3. Pulsa "Create API Key".
4. Copia la clave que aparece (empieza por "AIza...").

### Paso 7: Instalar Tesseract OCR (opcional, solo para PDFs escaneados)

```bash
winget install UB-Mannheim.TesseractOCR
```

Si un PDF escaneado no tiene texto extraíble, la app usa OCR para leerlo.
Sin Tesseract, los PDFs escaneados mostrarán "[pytesseract no instalado]".

---

## Uso de la aplicación

### 1. Indexar los trabajos anteriores (opcional pero recomendado)

Si quieres comparar contra trabajos de años anteriores:

1. Crea la carpeta `data/repositorio/` en la raíz del proyecto.
2. Dentro, organiza los documentos así:
   ```
   data/repositorio/<curso>/<asignatura>/<año>/<archivo>.pdf
   ```
   Ejemplo:
   ```
   data/repositorio/2024-25/energia-solar/2024/proyecto-garcia.pdf
   ```
3. Ejecuta el indexador:
   ```bash
   python -m scripts.indexar_repositorio
   ```
4. Espera a que termine (la primera vez descarga el modelo de embeddings, ~1.1 GB).

**Nota:** El repositorio de GitHub NO incluye la carpeta `data/` porque contiene
datos personales de estudiantes. Debes crearla y llenarla en tu máquina.

### 2. Arrancar la aplicación

```bash
python -m streamlit run streamlit_app.py
```

Abre tu navegador en http://localhost:8501

### 3. Configurar la API Key

En la barra lateral izquierda:
1. Selecciona "Gemini (Google)" como proveedor.
2. Pega tu API Key en el campo "API Key".
3. Selecciona un modelo (recomendado: `gemini-3.8-flash`).
4. Pulsa "Probar" para verificar que la clave funciona.
5. Pulsa "Guardar".

### 4. Analizar un documento

1. Selecciona "Subir archivo" o "Pegar texto".
2. Sube un PDF, DOCX, TXT, MD o imagen (máximo 200MB).
3. Pulsa "Analizar".
4. Revisa los resultados: veredicto global, fragmentos con evidencia, y
   justificación del LLM.

---

## Proveedores de IA

Cada usuario introduce su propia clave en la barra lateral. Hay un botón
**Probar** que valida la clave y el modelo antes de analizar.

| Proveedor | Modelos                                                   |
|-----------|-----------------------------------------------------------|
| Gemini    | `gemini-3.8-flash`, `gemini-3.7-flash`, ...              |

Si el proveedor falla, se prueban los demás modelos del mismo proveedor antes
de rendirse.

---

## Búsqueda web

La búsqueda web (DuckDuckGo) funciona de forma independiente al índice local.
Puedes activarla o desactivarla con la casilla "Buscar en web (DuckDuckGo)" en
la barra lateral. Si no tienes el repositorio indexado, la búsqueda web sigue
permitiendo detectar coincidencias en internet.

---

## Despliegue

### Streamlit Community Cloud (gratis)

1. Sube el repositorio a GitHub
2. En [share.streamlit.io](https://share.streamlit.io) → *Deploy an app*
3. Archivo principal: `streamlit_app.py`
4. En *Advanced settings* → Secrets, añade las claves que necesites

El repositorio **no incluye `data/`**: los trabajos de los estudiantes
contienen datos personales y académicos, y no deben subirse.

**Limitación:** En Streamlit Community Cloud, el índice local no está disponible.
Solo funciona la búsqueda web. Para usar el repositorio completo, ejecuta la
aplicación en tu propio máquina o servidor.

### Hugging Face Spaces (gratis, con Docker)

Se puede desplegar el mismo código como Space. Los documentos de referencia
pueden montarse desde un dataset privado del Space.

---

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

---

## Notas

- El índice usa scikit-learn en vez de una base vectorial dedicada: evita
  dependencias que requieren compilador (hnswlib) y funciona en CPU.
- El primer análisis descarga el modelo de embeddings; a partir de ahí va en
  memoria.
- El veredicto es reproducible: mismas entradas, mismo resultado. El LLM solo
  cambia el texto de la explicación.
