import json
from functools import lru_cache
from pathlib import Path

SEED_DIR = Path("data/seed")


@lru_cache(maxsize=None)
def _load(name: str) -> list[str]:
    path = SEED_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def names_male() -> list[str]:
    return _load("names_m")


def names_female() -> list[str]:
    return _load("names_f")


def surnames() -> list[str]:
    return _load("surnames")


def locations() -> list[str]:
    return _load("locations")


def objects() -> list[str]:
    return _load("objects")


def motives() -> list[str]:
    return _load("motives")


def personalities() -> list[str]:
    return _load("personalities")
