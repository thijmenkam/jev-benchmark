"""Jev (TypeSafe System One) decision call.

Usage:
    python jev.py "Help! My payouts have failed for 3 days."
    echo "ticket text" | python jev.py
    python jev.py --state "..." --questions questions.json --raw
"""

from common import build_result, http_post_json, load_env, require_env, run_cli

load_env()

API_URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"


def decide(state, questions):
    api_key = require_env("JEV_API_KEY")
    payload = {"model": MODEL, "state": state, "questions": questions}
    data, latency_ms = http_post_json(
        API_URL, payload, {"Authorization": f"Bearer {api_key}"}
    )
    return build_result(
        "jev",
        data.get("model", MODEL),
        data.get("answers", {}),
        data.get("usage"),
        latency_ms,
        data,
    )


if __name__ == "__main__":
    run_cli("jev", decide)
