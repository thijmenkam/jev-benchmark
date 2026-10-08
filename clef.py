"""Cloudflare Clef decision call (Workers AI, model: clef).

Clef follows the System One API, so it uses the same state + typed questions
shape as Jev. The response is wrapped in Cloudflare's {result, success} envelope.

Usage:
    python clef.py "Help! My payouts have failed for 3 days."
    echo "ticket text" | python clef.py
    python clef.py --state "..." --questions questions.json --raw
"""

import os

from common import build_result, http_post_json, load_env, require_env, run_cli

load_env()

MODEL = os.environ.get("CLEF_MODEL", "clef")


def decide(state, questions, model=None):
    model = model or MODEL
    token = require_env("CLOUDFLARE_AUTH_TOKEN")
    account_id = require_env("CLOUDFLARE_ACCOUNT_ID")
    endpoint = "clef-flash" if "flash" in model else "clef"
    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/run/@cf/cloudflare/{endpoint}"
    )
    payload = {"model": model, "state": state, "questions": questions}
    data, latency_ms = http_post_json(url, payload, {"Authorization": f"Bearer {token}"})
    result = data.get("result", data)
    return build_result(
        "clef",
        result.get("model", model),
        result.get("answers", {}),
        result.get("usage"),
        latency_ms,
        data,
    )


if __name__ == "__main__":
    run_cli("clef", decide)
