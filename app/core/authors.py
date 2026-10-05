"""Detección heurística de autores en la cabecera de un documento."""
import re
from collections import Counter

_CONECTORES = {
    "de", "del", "la", "las", "los", "el", "y", "e", "o", "u",
    "da", "das", "dos", "van", "von", "der", "den", "di", "al",
    "bin", "ibn", "mc", "mac",
}

# Palabras que aparecen capitalizadas por ser titulo o arranque de frase,
# no por ser nombre propio.
_NO_NOMBRE = {
    "comunidad", "energética", "energetica", "renovable", "proyecto", "índice",
    "indice", "introducción", "introduccion", "conclusiones", "conclusion",
    "bibliografía", "bibliografia", "resumen", "abstract", "grupo", "curso",
    "universidad", "grado", "ingeniería", "ingenieria", "titulo", "título",
    "autor", "autores", "autoría", "autoria", "memoria", "informe",
    "presentación", "presentacion", "departamento", "asignatura", "módulo",
    "modulo", "sistema", "sistemas", "diseño", "diseno", "estudio",
    "análisis", "analisis", "datos", "escenarios", "escenario", "indicadores",
    "costes", "resultados", "discusión", "discusion", "métodos", "metodos",
    "producción", "produccion", "almacenamiento", "alumno", "alumna",
    "alumnos", "docente", "tutor", "coordinador", "modelo", "model",
    "caso", "study", "energía", "energia", "descripción", "descripcion",
    "codi", "cognoms", "nom", "noms", "disseny", "gr", "departament",
    "enginyeria", "pla", "tipus", "descripció", "descripcio", "import",
    "total", "media", "medios", "bajo", "alto", "medio", "casos",
    "figura", "tabla", "gráfico", "grafico", "anexo", "capítulo", "capitulo",
    "sección", "seccion", "autosuficiencia", "consumo", "coste", "costes",
    "and", "the", "for", "with", "from", "this", "that", "table", "figure",
    "chapter", "section",
}

_TITULOS_ACADEMICOS = {
    "sr", "sra", "srta", "dr", "dra", "prof", "profesor", "profesora",
    "ing", "ingeniero", "ingeniera", "licenciado", "licenciada", "master",
    "máster", "mster", "grad", "graduado",
}

# Token capitalizado: primera letra mayúscula, resto minúsculas, >=2 chars
_TOKEN = re.compile(r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{1,}")


def _normalizar(nombre: str) -> str:
    return re.sub(r"\s+", " ", nombre.strip().lower())


_PARTICULAS = {
    "de", "del", "la", "las", "los", "el", "y", "da", "das", "dos", "van",
    "von", "der", "den", "di", "al", "bin", "ibn", "mc", "mac", "san", "santa",
}

# Etiquetas tipicas de formulario administrativo o tabla: no son nombres
_ETIQUETA_FORMULARIO = re.compile(
    r"\b(data|taula|taula|codi|codi|camp|camps|columna|columnes|fila|files|"
    r"descripcio|descripción|nom|noms|cognom|cognoms|apellido|apellidos|"
    r"tipus|marge|seccio|secció|pagina|pàgina|total|import|export|"
    r"departament|departamento|assignatura|asignatura| curs|curs)\b"
)


def _parece_etiqueta(tokens: list[str]) -> bool:
    """Detecta 'data fi', 'codi descripció': etiquetas, no nombres."""
    for t in tokens:
        if _ETIQUETA_FORMULARIO.search(t.lower()):
            return True
    return False


def _es_valido(tokens: list[str]) -> bool:
    if not (2 <= len(tokens) <= 3):
        return False
    lows = [t.lower() for t in tokens]
    if any(t in _CONECTORES for t in lows[1:]):
        return False
    if any(t in _NO_NOMBRE or t in _TITULOS_ACADEMICOS for t in lows):
        return False
    # Las tres primeras letras deben ser distintas (nombres, no repeticiones)
    if len(lows) >= 2 and lows[0][:3] == lows[1][:3]:
        return False
    if _parece_etiqueta(tokens):
        return False
    # Un nombre no empieza por articulo ni preposicion
    if lows[0] in _PARTICULAS:
        return False
    return True


def _segmentar(run: list[str]) -> list[list[str]]:
    """Divide una secuencia de tokens capitalizados en nombres no solapados.

    Usa segmentacion de coste minimo: los segmentos son de 2 o 3 tokens, se
    minimise el numero de segmentos y en empate se prefieren los de 3.
    Asi 'Christian Couto Egea Pol Rubio Valero' (5 tokens) se parte en
    ['Christian Couto Egea', 'Pol Rubio Valero'] y no en ventanas solapadas.
    """
    n = len(run)
    # dp[i] = (num_segmentos, lista_de_segmentos) para run[i:]
    dp: list[tuple[int, list[list[str]]] | None] = [None] * (n + 1)
    dp[n] = (0, [])
    for i in range(n - 1, -1, -1):
        mejor = None
        # Tamaño 3 antes que 2: a igualdad de coste, cubre mas palabras
        for tam in (3, 2):
            if i + tam > n:
                continue
            seg = run[i:i + tam]
            if not _es_valido(seg):
                continue
            resto = dp[i + tam]
            if resto is None:
                continue
            cand = (resto[0] + 1, [seg] + resto[1])
            if mejor is None or cand[0] < mejor[0]:
                mejor = cand
        dp[i] = mejor

    if dp[0] is None:
        return []
    return dp[0][1]


def extraer_autores(texto: str, max_caracteres: int = 800) -> list[str]:
    """Extrae candidatos a autor del inicio del documento.

    Segmenta las secuencias de palabras capitalizadas del encabezado en
    nombres de 2-3 palabras, y conserva los mas repetidos en el documento.
    """
    cabecera = texto[:max_caracteres]
    if not cabecera.strip():
        return []

    runs: list[list[str]] = []
    for run in re.finditer(
        r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{1,}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{1,})*", cabecera
    ):
        runs.append(run.group(0).split())

    conteo: Counter[str] = Counter()
    for run in runs:
        for seg in _segmentar(run):
            conteo[_normalizar(" ".join(seg))] += 1

    if not conteo:
        return []

    mas_frecuentes = conteo.most_common(4)
    top = mas_frecuentes[0][1]

    if top >= 2:
        return sorted(n for n, c in mas_frecuentes if c >= 2)

    candidatos = [n for n, _ in mas_frecuentes]
    return sorted(c for c in candidatos if not any(c != o and c in o for o in candidatos))


def autores_coinciden(autores_a: list[str], autores_b: list[str]) -> tuple[bool, list[str]]:
    """Devuelve (hay_autores_comunes, lista_de_comunes)."""
    if not autores_a or not autores_b:
        return False, []
    set_b = set(autores_b)
    comunes = sorted({a for a in autores_a if a in set_b})
    return bool(comunes), comunes