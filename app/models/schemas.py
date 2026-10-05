from pydantic import BaseModel


class AnalisisRequest(BaseModel):
    texto: str
    usar_llm: bool = True
    usar_web: bool = True


class AnalisisResponse(BaseModel):
    total_fragmentos: int
    fragmentos_con_coincidencia: int
    porcentaje_similitud: float
    coincidencias: list[dict]