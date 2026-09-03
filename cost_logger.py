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


def log_api_cost(run_id, lead_id, call_type, model, input_tokens, output_tokens, web_searches=0):
    pricing = PRICING.get(model, {"input": 0, "output": 0})
    cost_usd = (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]
    cost_usd += web_searches * 0.01  # $10 per 1,000 searches = $0.01 per search
    cost_jpy = cost_usd * USD_TO_JPY

    file_exists = os.path.isfile(COST_LOG_FILE)

    with open(COST_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["run_id", "timestamp", "lead_id", "call_type", "model", "input_tokens", "output_tokens", "web_searches", "cost_usd", "cost_jpy"])
        writer.writerow([
            run_id,
            datetime.now().isoformat(timespec="seconds"),
            lead_id, call_type, model, input_tokens, output_tokens, web_searches,
            round(cost_usd, 6), round(cost_jpy, 2)
        ])