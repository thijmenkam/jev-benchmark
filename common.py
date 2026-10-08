import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(ROOT, ".env")

DEFAULT_QUESTIONS = {
    "is_urgent": {
        "type": "noul",
        "instructions": "Does this convey urgency or time-sensitivity?",
    },
    "team": {
        "type": "choice",
        "instructions": "Which team should handle this request?",
        "criteria": {
            "billing": "Payments, invoices, and refunds",
            "technical": "Outages, errors, and configuration",
            "sales": "Plans and upgrades",
        },
    },
    "frustration": {
        "type": "score",
        "instructions": "How frustrated is the customer?",
        "criteria": [
            "Calm, just stating facts",
            "Frustrated but civil",
            "Very angry, strong language",
        ],
    },
}


def load_env(path=ENV_PATH):
    if not os.path.exists(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            os.environ.setdefault(key, val)


def require_env(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing {name}. Add it to {ENV_PATH}.")
    return value


def http_post_json(url, payload, headers, timeout=60):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        req.add_header(key, value)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body, status = resp.read().decode(), resp.status
    except urllib.error.HTTPError as exc:
        body, status = exc.read().decode(), exc.code
    latency_ms = (time.perf_counter() - start) * 1000
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        parsed = body
    if status >= 400:
        raise RuntimeError(f"HTTP {status}: {body}")
    return parsed, latency_ms


def normalize_answers(answers):
    normalized = {}
    for qid, ans in answers.items():
        if not isinstance(ans, dict):
            normalized[qid] = ans
            continue
        kind = ans.get("type")
        if kind == "noul":
            prob = ans.get("noul")
            normalized[qid] = {"type": "noul", "value": prob, "probability": prob}
        elif kind == "choice":
            probs = {str(k): v for k, v in (ans.get("probabilities") or {}).items()}
            normalized[qid] = {
                "type": "choice",
                "value": ans.get("choice"),
                "probabilities": probs,
                "confidence": ans.get("confidence"),
            }
        elif kind == "score":
            legend = ans.get("legend") or {}
            probs = {str(k): v for k, v in (ans.get("probabilities") or {}).items()}
            label = None
            if probs:
                best = max(probs.items(), key=lambda kv: kv[1])[0]
                label = legend.get(best, best)
            normalized[qid] = {
                "type": "score",
                "value": ans.get("score"),
                "label": label,
                "legend": legend,
                "probabilities": probs,
                "confidence": ans.get("confidence"),
            }
        else:
            normalized[qid] = ans
    return normalized


def build_result(provider, model, answers, usage, latency_ms, raw):
    return {
        "provider": provider,
        "model": model,
        "latency_ms": round(latency_ms, 1),
        "answers": normalize_answers(answers),
        "usage": usage,
        "raw": raw,
    }


def run_cli(provider, decide):
    parser = argparse.ArgumentParser(
        description=f"Run a decision through {provider}. "
        "State can be a positional arg, --state, or stdin."
    )
    parser.add_argument("state", nargs="?", help="Input state/text.")
    parser.add_argument("--state", dest="state_opt", help="Input state/text.")
    parser.add_argument(
        "--questions",
        help="Path to a JSON file of normalized questions (defaults to a demo set).",
    )
    parser.add_argument(
        "--raw", action="store_true", help="Print only the provider's raw response."
    )
    args = parser.parse_args()

    state = args.state_opt or args.state
    if not state:
        state = sys.stdin.read().strip()
    if not state:
        parser.error("no state provided (pass an argument, --state, or pipe via stdin)")

    questions = DEFAULT_QUESTIONS
    if args.questions:
        with open(args.questions) as fh:
            questions = json.load(fh)

    result = decide(state, questions)
    print(json.dumps(result["raw"] if args.raw else result, indent=2))
