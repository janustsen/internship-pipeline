from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - exercised only on minimal installs
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False


class ConfigError(RuntimeError):
    pass


SOURCE_REQUIRED_ENV = {
    "adzuna": ("ADZUNA_APP_ID", "ADZUNA_APP_KEY"),
    "linkedin": ("APIFY_TOKEN", "LINKEDIN_APIFY_ACTOR_ID"),
    "serper": ("SERPER_API_KEY",),
}


@dataclass(frozen=True)
class Config:
    values: dict[str, str]

    @classmethod
    def from_env(
        cls,
        *,
        env_path: str | Path = ".env",
        required: tuple[str, ...] = (),
        require_existing_env_file: bool = False,
    ) -> "Config":
        path = Path(env_path)
        if require_existing_env_file and not path.exists():
            raise ConfigError(f"missing {path}; copy .env.example and fill required keys")
        load_dotenv(path)
        missing = [key for key in required if not os.getenv(key)]
        if missing:
            joined = ", ".join(missing)
            raise ConfigError(f"missing required environment variable(s): {joined}")
        return cls(values={key: value for key, value in os.environ.items()})

    def get(self, key: str, default: str = "") -> str:
        return self.values.get(key, default)

    def require(self, *keys: str) -> dict[str, str]:
        missing = [key for key in keys if not self.values.get(key)]
        if missing:
            joined = ", ".join(missing)
            raise ConfigError(f"missing required environment variable(s): {joined}")
        return {key: self.values[key] for key in keys}


def required_env_for_sources(sources: list[str]) -> tuple[str, ...]:
    required: list[str] = []
    for source in sources:
        required.extend(SOURCE_REQUIRED_ENV.get(source, ()))
    return tuple(dict.fromkeys(required))
