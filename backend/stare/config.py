"""Runtime configuration. Every setting can be overridden with an environment variable prefixed STARE_."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    # backend/.env.local (never committed) holds private keys and overrides backend/.env
    model_config = SettingsConfigDict(env_prefix="STARE_", env_file=(BACKEND_DIR / ".env", BACKEND_DIR / ".env.local"),
                                      extra="ignore")

    # --- storage -------------------------------------------------------------------------------
    data_dir: Path = REPO_DIR / "data"
    # SQLite is the laptop default; set to postgresql+psycopg://user:pw@host/stare for pgvector.
    database_url: str = ""
    upload_dir_name: str = "uploads"
    keep_raw_uploads: bool = False  # NFR-03: raw client files are deleted after extraction by default

    # --- security ------------------------------------------------------------------------------
    jwt_secret: str = "change-me-in-production"
    jwt_ttl_minutes: int = 12 * 60
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- LLM -----------------------------------------------------------------------------------
    # "offline" is a deterministic, rule-based provider: no network, no cost. It is the default.
    llm_provider: Literal["offline", "anthropic", "openai_compat"] = "offline"
    llm_model: str = "claude-opus-5-5"  # main model (drafting, opposing counsel)
    llm_fast_model: str = "claude-haiku-5-5"  # routine steps (query writing, extraction)
    llm_base_url: str = ""  # for openai_compat (e.g. a local Ollama server)
    llm_api_key: str = ""
    llm_max_tokens: int = 8000
    llm_cache: bool = True  # cache identical prompts on disk to control cost

    # --- retrieval -----------------------------------------------------------------------------
    embedder: Literal["lsa", "fastembed", "sentence_transformers"] = "lsa"
    embedding_dim: int = 256  # LSA dimension; neural embedders override with their own size
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker: Literal["lexical", "cross_encoder", "none"] = "lexical"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rrf_k: int = 60
    chunk_tokens: int = 350
    chunk_overlap: int = 60
    candidates_per_query: int = 30
    max_candidates: int = 100
    shortlist_size: int = 12

    # --- citation firewall ---------------------------------------------------------------------
    courtlistener_token: str = ""  # free account token; anonymous mode is used when empty
    courtlistener_base_url: str = "https://www.courtlistener.com/api/rest/v4"
    courtlistener_rate_per_minute: int = 30
    courtlistener_max_wait_s: float = 5.0  # interactive runs never wait long; batch evaluation can raise it
    courtlistener_enabled: bool = True  # Gate 2 fallback; NFR-06: system continues when unavailable
    cap_lookup_enabled: bool = True  # Gate 2 also checks static.case.law reporter listings (free, cached)
    quote_exact_threshold: float = 0.995
    quote_warn_threshold: float = 0.90
    case_name_threshold: float = 0.60
    min_verified_authorities: int = 3  # CRAG-style loop: research again when fewer pass
    max_research_loops: int = 3

    # --- performance ---------------------------------------------------------------------------
    latency_target_s: float = 90.0

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'stare.db'}"

    @property
    def is_postgres(self) -> bool:
        return self.db_url.startswith("postgresql")

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / self.upload_dir_name

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def checkpoint_path(self) -> Path:
        return self.data_dir / "checkpoints.sqlite"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.upload_dir, self.index_dir, self.cache_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s
