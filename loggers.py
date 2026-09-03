import csv
import os
from datetime import datetime

# Price per 1 million tokens, in USD, by model. Update if pricing changes.
PRICING = {
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00}
}

USD_TO_JPY = 155  # update this occasionally to track the real exchange rate

COST_LOG_FILE = "api_costs.csv"


def log_api_cost(run_id, lead_id, call_type, model, input_tokens, output_tokens, web_searches=0, cache_creation_input_tokens=0, cache_read_input_tokens=0):
    pricing = PRICING.get(model, {"input": 0, "output": 0})

    regular_input_cost = (input_tokens / 1_000_000) * pricing["input"]
    cache_write_cost = (cache_creation_input_tokens / 1_000_000) * pricing["input"] * 1.25
    cache_read_cost = (cache_read_input_tokens / 1_000_000) * pricing["input"] * 0.1
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    cost_usd = regular_input_cost + cache_write_cost + cache_read_cost + output_cost
    cost_usd += web_searches * 0.01
    cost_jpy = cost_usd * USD_TO_JPY

    file_exists = os.path.isfile(COST_LOG_FILE)

    with open(COST_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["run_id", "timestamp", "lead_id", "call_type", "model", "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens", "web_searches", "cost_usd", "cost_jpy"])
        writer.writerow([
            run_id,
            datetime.now().isoformat(timespec="seconds"),
            lead_id, call_type, model, input_tokens, cache_creation_input_tokens, cache_read_input_tokens, output_tokens, web_searches,
            round(cost_usd, 6), round(cost_jpy, 2)
        ])

SEARCH_LOG_FILE = "search_trace.csv"


def log_search_query(run_id, lead_id, query):
    file_exists = os.path.isfile(SEARCH_LOG_FILE)

    with open(SEARCH_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["run_id", "lead_id", "content"])
        writer.writerow([run_id, lead_id, query])