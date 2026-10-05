from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    llm_provider: str = "ollama"
    ollama_model: str = "llama3.1:8b"
    ollama_host: str = "http://localhost:11434"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    openrouter_api_key: str = ""
    openrouter_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    nvidia_nim_api_key: str = ""
    nvidia_nim_model: str = "nvidia/nemotron-3-ultra-550b-a55b"

    threshold_literal: float = 0.90
    threshold_paraphrase: float = 0.82
    threshold_ideas: float = 0.75

    chunk_size: int = 400
    chunk_overlap: int = 50

    web_search_enabled: bool = True
    web_search_max_queries: int = 10

    base_dir: Path = Path(__file__).resolve().parent.parent
    repo_dir: Path = base_dir / "data" / "repositorio"
    chroma_dir: Path = base_dir / "data" / "chroma_db"

    class Config:
        env_file = ".env"


settings = Settings()


# Modelos gratis con API Key (lista real)
GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.8-live",
    "gemini-3.8-live-extended-thinking",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]

GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]

OPENROUTER_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "stealth/space-bunny-alpha",
]

NVIDIA_NIM_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-4-340b-instruct",
]

OLLAMA_MODELS = [
    "llama3.1:8b",
    "llama3.1:70b",
    "qwen2.5:7b",
    "qwen2.5:14b",
    "mistral:7b",
    "mistral-nemo:12b",
]