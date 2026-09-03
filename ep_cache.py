import json
import os
import hashlib
from models import EngagementPlan

CACHE_FILE = "ep_cache.json"


def make_cache_key(lea_input) -> str:
    input_json = lea_input.model_dump_json()
    return hashlib.sha256(input_json.encode("utf-8")).hexdigest()


def load_cache() -> dict:
    if not os.path.isfile(CACHE_FILE):
        return {}
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache: dict) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def get_cached_plan(lea_input):
    cache = load_cache()
    key = make_cache_key(lea_input)
    if key in cache:
        return EngagementPlan.model_validate(cache[key])
    return None


def store_plan(lea_input, engagement_plan) -> None:
    cache = load_cache()
    key = make_cache_key(lea_input)
    cache[key] = engagement_plan.model_dump(mode="json")
    save_cache(cache)