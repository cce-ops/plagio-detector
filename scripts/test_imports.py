"""Comprueba que todo lo que la UI importa existe de verdad.

py_compile solo valida sintaxis: no detecta imports rotos. Este test si.
"""
import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
fallos = []

# 1) Todo lo que importa la UI debe existir en app/runner.py
ui = RAIZ / "ui" / "streamlit_app.py"
arbol = ast.parse(ui.read_text(encoding="utf-8"))
for nodo in ast.walk(arbol):
    if isinstance(nodo, ast.ImportFrom) and nodo.module == "app.runner":
        runner = RAIZ / "app" / "runner.py"
        arbol_runner = ast.parse(runner.read_text(encoding="utf-8"))
        definidos = {
            x.name for x in arbol_runner.body
            if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        definidos |= {
            t.id for x in arbol_runner.body if isinstance(x, ast.Assign)
            for t in x.targets if isinstance(t, ast.Name)
        }
        for alias in nodo.names:
            if alias.name not in definidos:
                fallos.append(f"app/runner.py no define {alias.name} (usado en ui/streamlit_app.py)")

# 2) Todos los modulos de app.core deben importar sin error
sys.path.insert(0, str(RAIZ))
for mod in sorted(p.stem for p in (RAIZ / "app" / "core").glob("*.py")
                  if p.stem != "__init__"):
    try:
        __import__(f"app.core.{mod}")
    except Exception as e:
        fallos.append(f"app/core/{mod}.py no importa: {type(e).__name__}: {e}")

# 3) runner y main
for mod in ("app.runner", "app.main", "app.config"):
    try:
        __import__(mod)
    except Exception as e:
        fallos.append(f"{mod} no importa: {type(e).__name__}: {e}")

if fallos:
    print("FALLOS:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)

print("Todos los imports correctos")