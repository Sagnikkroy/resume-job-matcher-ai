"""Loads configuration and prompt files once and caches them."""
from functools import lru_cache
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def load_config(path: str = "config.yaml") -> dict:
    with open(BASE_DIR / path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def load_prompts(path: str | None = None) -> dict:
    path = path or load_config()["paths"]["prompts"]
    with open(BASE_DIR / path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def render(template: str, **values: str) -> str:
    """Fill {placeholders}. Uses plain replace so JSON braces in prompts stay intact."""
    for key, value in values.items():
        template = template.replace("{" + key + "}", str(value))
    return template
