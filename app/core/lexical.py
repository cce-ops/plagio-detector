from datasketch import MinHash
import re


def _normalizar(texto: str) -> str:
    texto = texto.lower()
    texto = re.sub(r"[^\wáéíóúüñ\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def minhash_similitud(a: str, b: str, num_perm: int = 128) -> float:
    def _mh(texto):
        m = MinHash(num_perm=num_perm)
        for token in _normalizar(texto).split():
            m.update(token.encode("utf8"))
        return m
    return _mh(a).jaccard(_mh(b))


def ngramas(texto: str, n: int = 5) -> set[str]:
    palabras = _normalizar(texto).split()
    return {" ".join(palabras[i:i + n]) for i in range(len(palabras) - n + 1)}


def solapamiento_ngramas(a: str, b: str, n: int = 5) -> float:
    ga, gb = ngramas(a, n), ngramas(b, n)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / min(len(ga), len(gb))


# --- Huella numerica -------------------------------------------------------
# Numeros con 3+ cifras significativas que no son anos ni valores redondos.
# Dos documentos de autores distintos que comparten estos valores comparten
# los datos originales, no una terminologia comun.

_NUMERO_RE = re.compile(r"\d+(?:[.,]\d+)*")
_MILES_RE = re.compile(r"^\d{1,3}(?:\.\d{3})+$")


def _a_float(token: str) -> float | None:
    """Interpreta un numero en formato español o ingles.

    '99.000' -> 99000.0   (punto de millar)
    '0,48'   -> 0.48      (coma decimal)
    '43388,4'-> 43388.4
    '120.00086611,5' -> descarta: numero pegado por el extractor de PDF
    """
    if "," in token and "." in token:
        # Formato mixto: 1.234.567,89
        if not _MILES_RE.match(token.split(",")[0]):
            return None
        return float(token.replace(".", "").replace(",", "."))

    if _MILES_RE.match(token):
        return float(token.replace(".", ""))

    if "," in token:
        # '4864,2' -> decimal ; '120,000' -> millar
        entero, _, decimal = token.partition(",")
        if len(decimal) == 3 and len(entero) <= 3:
            return float(entero + decimal)
        return float(f"{entero}.{decimal}")

    return float(token)


def _es_significativo(valor: float, token: str) -> bool:
    """Filtra anos, indices y numeros sin valor informativo."""
    # Anos y numeros de seccion/tabla
    if "." not in token and "," not in token and 1900 <= valor <= 2100:
        return False
    if valor < 100:
        return False
    # Valores redondos sin precision (100, 500, 1000)
    if valor in (100, 200, 250, 300, 400, 500, 600, 700, 800, 900, 1000):
        return False
    return len(re.sub(r"[^\d]", "", token)) >= 3


def numeros_significativos(texto: str) -> set[str]:
    """Extrae valores numericos distintivos, normalizados sin separadores."""
    salida: set[str] = set()
    for token in _NUMERO_RE.findall(texto):
        valor = _a_float(token)
        if valor is None or not _es_significativo(valor, token):
            continue
        clave = str(int(valor)) if float(valor).is_integer() else f"{valor:.1f}"
        salida.add(clave)
    return salida


def solapamiento_numeros(a: str, b: str) -> dict:
    """Mide cuantos valores numericos distintivos comparten dos textos.

    Es la evidencia mas fuerte de copia: valores como '70000.4864' o
    '43388.4' no se repiten por casualidad entre autores distintos.
    """
    na, nb = numeros_significativos(a), numeros_significativos(b)
    if not na or not nb:
        return {"comunes": 0, "total_a": len(na), "total_b": len(nb), "ratio": 0.0, "ejemplos": []}

    comunes = sorted(na & nb, key=lambda x: (-len(x), x))
    ratio = len(comunes) / min(len(na), len(nb))
    return {
        "comunes": len(comunes),
        "total_a": len(na),
        "total_b": len(nb),
        "ratio": round(ratio, 3),
        "ejemplos": comunes[:8],
    }


# --- Entidades nombradas ----------------------------------------------------
# Nombres propios (lugares, organismos, empresas) que identifican el caso
# concreto. Dos autores distintos que nombran la misma localidad y el mismo
# caso de estudio han copiado el enunciado, no coincidence academic casual.

_ENTIDAD_RE = re.compile(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})?\b")

_NO_ENTIDAD = {
    # Terminos tecnicos y titulos de apartado
    "comunidad", "energética", "energetica", "renovable", "sistema", "sistemas",
    "proyecto", "índice", "indice", "introducción", "introduccion", "conclusiones",
    "conclusion", "bibliografía", "bibliografia", "resumen", "abstract", "grupo",
    "curso", "universidad", "grado", "ingeniería", "ingenieria", "energía", "energia",
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "y", "o",
    "este", "esta", "estos", "estas", "como", "para", "con", "por", "que", "se",
    "diseño", "diseno", "estudio", "análisis", "analisis", "datos", "escenarios",
    "escenario", "indicadores", "costes", "resultados", "discusión", "discusion",
    "métodos", "metodos", "producción", "produccion", "almacenamiento",
    "alumno", "alumna", "alumnos", "docente", "tutor", "modelo", "caso",
    "figura", "tabla", "gráfico", "grafico", "anexo", "capítulo", "capitulo",
    "sección", "seccion", "informe", "memoria", "presentación", "presentacion",
    "autores", "autor", "titulo", "título", "departamento", "asignatura",
    "módulo", "modulo", "autosuficiencia", "consumo", "escenarios", "casos",
    "total", "media", "medios", "bajo", "alto", "medio", "siguiente", "figura",
    "this", "the", "and", "for", "with", "from", "that",
}


def entidades(texto: str) -> set[str]:
    """Extrae nombres propios de 1-2 palabras, sin terminos tecnicos."""
    salida: set[str] = set()
    for match in _ENTIDAD_RE.finditer(texto):
        cand = match.group(0).strip()
        palabras = cand.split()
        if len(palabras) == 1:
            if cand.lower() in _NO_ENTIDAD or len(cand) < 4:
                continue
            salida.add(cand.lower())
        else:
            if any(p.lower() in _NO_ENTIDAD for p in palabras):
                continue
            salida.add(cand.lower())
    return salida


def solapamiento_entidades(a: str, b: str) -> dict:
    """Mide cuantos nombres propios comparten dos textos."""
    ea, eb = entidades(a), entidades(b)
    if not ea or not eb:
        return {"comunes": 0, "total_a": len(ea), "total_b": len(eb), "ejemplos": []}

    comunes = sorted(ea & eb, key=lambda x: (-len(x), x))
    return {
        "comunes": len(comunes),
        "total_a": len(ea),
        "total_b": len(eb),
        "ejemplos": comunes[:8],
    }