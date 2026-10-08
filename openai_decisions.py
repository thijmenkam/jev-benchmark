"""OpenAI Decisions API call (model: gpt-6-luna).

Normalized question types are translated to OpenAI's predicate/choice/score
schema, and the array response is mapped back to a dict keyed by question name.

Usage:
    python openai_decisions.py "Help! My payouts have failed for 3 days."
    echo "ticket text" | python openai_decisions.py
    python openai_decisions.py --state "..." --questions questions.json --raw
"""

from common import build_result, http_post_json, load_env, require_env, run_cli

load_env()

API_URL = "https://api.openai.com/v1/decisions"
MODEL = "gpt-6-luna"


def to_openai_questions(questions):
    converted = []
    for qid, question in questions.items():
        kind = question["type"]
        item = {"name": qid, "instructions": question["instructions"]}
        if kind == "noul":
            item["type"] = "predicate"
        elif kind == "choice":
            item["type"] = "choice"
            item["choices"] = [
                {"value": value, "description": desc}
                for value, desc in question["criteria"].items()
            ]
        elif kind == "score":
            item["type"] = "score"
            item["levels"] = [
                {"label": desc, "description": desc}
                for desc in question["criteria"]
            ]
        else:
            raise ValueError(f"Unknown question type: {kind}")
        converted.append(item)
    return converted


def from_openai_answer(answer):
    kind = answer.get("type")
    if kind == "predicate":
        prob = answer.get("probability")
        return {"type": "noul", "noul": prob}
    if kind == "choice":
        return {
            "type": "choice",
            "choice": answer.get("choice"),
            "probabilities": {
                p["value"]: p["probability"] for p in answer.get("probabilities", [])
            },
            "confidence": answer.get("confidence"),
        }
    if kind == "score":
        levels = answer.get("probabilities", [])
        return {
            "type": "score",
            "score": answer.get("score"),
            "legend": {str(p["value"]): p.get("label") for p in levels},
            "probabilities": {str(p["value"]): p["probability"] for p in levels},
            "confidence": answer.get("confidence"),
        }
    return answer


def decide(state, questions):
    api_key = require_env("OPENAI_API_KEY")
    # Decisions API takes string/array input; System One accepts objects.
    # Same semantic content, stringified (documented adapter, cf. EXPERIMENT §3.3).
    if not isinstance(state, str):
        import json as _json
        state = _json.dumps(state)
    payload = {
        "model": MODEL,
        "input": state,
        "questions": to_openai_questions(questions),
    }
    data, latency_ms = http_post_json(
        API_URL, payload, {"Authorization": f"Bearer {api_key}"}
    )
    answers = {}
    for index, answer in enumerate(data.get("answers", [])):
        name = answer.get("name") or (
            list(questions)[index] if index < len(questions) else str(index)
        )
        answers[name] = from_openai_answer(answer)
    return build_result(
        "openai",
        data.get("model", MODEL),
        answers,
        data.get("usage"),
        latency_ms,
        data,
    )


if __name__ == "__main__":
    run_cli("openai", decide)
