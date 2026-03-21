from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """
    All configuration lives here.

    pydantic-settings automatically reads from your .env file.
    If a required field is missing it crashes immediately with a
    clear error — much better than a confusing crash 10 layers deep.
    """

    # --- LLM ---
    groq_api_key: str                        # required, no default — must be in .env
    openrouter_api_key: str = ""             # optional, if set uses OpenRouter instead of Groq
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct:free"
    model: str = "llama-3.3-70b-versatile"
    max_turns: int = 10                        # how many tool calls before agent stops

    # --- Security ---
    max_csv_size_mb: int = 10                 # max allowed CSV file size in MB
    disable_persistent_storage: bool = False   # if True, stores credentials only in memory

    # --- Paths (all relative to project root) ---
    db_path: str = "db/sessions.db"
    chroma_path: str = "db/chroma"
    data_dir: str = "data"

    class Config:
        env_file = ".env"                      # tells pydantic to read from .env
        env_file_encoding = "utf-8"

    # --- Path helpers ---
    # These convert the string paths into Path objects so we can do
    # things like:  settings.db_dir.mkdir(parents=True, exist_ok=True)

    @property
    def db_dir(self) -> Path:
        return Path(self.db_path).parent       # returns  db/

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)             # returns  data/


# Single shared instance — every other file imports this one object.
# .env is read exactly once, right here at startup.
settings = Settings()