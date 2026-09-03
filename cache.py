# caching flow
# Format — JSON file (research_cache.json), one shared file for now.
# Key — "{company}::{lead_name}" combined string, so two different leads at the same company never collide.
# Entry shape — {"cached_at": timestamp, "findings": {...ResearchFindings as a plain dict...}}.
# TTL — 30 days; entries older than this are treated as a miss (ignored), not deleted from the file.
# Read — get_cached_research(company, lead_name): load the file, look up the key, check freshness, return a validated ResearchFindings or None.
# Write — save_research_to_cache(company, lead_name, findings): load the file (or start fresh if it doesn't exist yet), add/update the entry, save it back.
# Failure case — a missing, corrupted, or unreadable cache file is treated as an empty cache (a miss), never allowed to crash run_research.
# Wire-in — inside run_research: check the cache first; if it's a fresh hit, return it immediately (skip the API call entirely); otherwise call the API as before, then save the new result to cache before returning.
# History log — a separate, append-only file (research_history.jsonl); every completed research run — cache hit or fresh — gets one new line added, never overwritten, so past research stays reviewable even after the cache itself gets refreshed.
# Test — run against Kinoshita/Panasonic twice in a row; the second run should be near-instant and should not trigger a real API call.


import json
from datetime import datetime, timedelta
from models import ResearchFindings

CACHE_FILE = "research_cache.json"
CACHE_TTL_DAYS = 30

def get_cached_research(company, lead_name):
    try:
        with open(CACHE_FILE) as f:
            cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    key = f"{company}::{lead_name}"
    entry = cache.get(key)
    if entry is None:
        return None

    cached_at = datetime.fromisoformat(entry["cached_at"])
    if datetime.now() - cached_at > timedelta(days=CACHE_TTL_DAYS):
        return None

    return ResearchFindings(**entry["findings"])


def save_research_to_cache(company, lead_names, findings):
    try:
        with open(CACHE_FILE) as f:
            cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}

    entry = {
        "cached_at": datetime.now().isoformat(),
        "findings": findings.model_dump()
    }

    for name in lead_names:
        key = f"{company}::{name}"
        cache[key] = entry

    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)