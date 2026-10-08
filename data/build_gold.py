"""Build frozen gold dataset: data/gold.v1.jsonl + data/questions.v1.json
Deterministic (seed 42). Gold labels known by construction; tiers assigned by cue conflict.
300 rows total: 215 unique + 45 paraphrases + 30 json variants + 10 long.
"""
import json, os, random

ROOT = os.path.dirname(os.path.abspath(__file__))
random.seed(42)

QUESTIONS = {
    "support": {
        "is_urgent": {"type": "noul", "instructions": "Does this convey urgency or time-sensitivity?"},
        "team": {"type": "choice", "instructions": "Which team should handle this request?",
                 "criteria": {"billing": "Payments, invoices, and refunds",
                              "technical": "Outages, errors, and configuration",
                              "sales": "Plans and upgrades"}},
        "frustration": {"type": "score", "instructions": "How frustrated is the customer?",
                        "criteria": ["Calm, just stating facts", "Frustrated but civil", "Very angry, strong language"]},
    },
    "invoice": {
        "needs_human": {"type": "noul", "instructions": "Does this invoice need human review before approval?"},
        "route": {"type": "choice", "instructions": "What should happen to this invoice?",
                  "criteria": {"approve": "All fields present, PO matches, approve for payment",
                               "request_info": "Missing fields, ask vendor for more info",
                               "escalate": "Suspicious amount or duplicate, escalate to finance lead",
                               "reject": "Invalid or fraudulent, reject outright"}},
        "completeness": {"type": "score", "instructions": "How complete is this invoice record?",
                         "criteria": ["Missing critical fields", "Partial, needs follow-up",
                                      "Complete but unverified", "Complete and verified"]},
    },
    "security": {
        "is_critical": {"type": "noul", "instructions": "Is this a critical security incident needing immediate response?"},
        "team": {"type": "choice", "instructions": "Which team should handle this incident?",
                 "criteria": {"secops": "Active threats, breaches, malware",
                              "platform": "Infra errors, config, uptime",
                              "support": "General questions, how-to, account help"}},
        "severity": {"type": "score", "instructions": "How severe is the impact?",
                     "criteria": ["No impact", "Minor", "Major", "Critical"]},
    },
    "toolcall": {
        "should_call_tool": {"type": "noul", "instructions": "Should the agent call a tool now rather than ask a clarifying question or answer directly?"},
        "action": {"type": "choice", "instructions": "What should the agent do next?",
                   "criteria": {"call_tool": "Enough detail to act via API or tool",
                                "ask_clarify": "Too vague, must ask a follow-up question",
                                "answer_directly": "General knowledge question, answer without tools"}},
    },
    "guardrail": {  # reuses support shape; OOS rows expect low confidence, gold = best-fit + abstain flag
        "is_urgent": {"type": "noul", "instructions": "Does this convey urgency or time-sensitivity?"},
        "team": {"type": "choice", "instructions": "Which team should handle this request?",
                 "criteria": {"billing": "Payments, invoices, and refunds",
                              "technical": "Outages, errors, and configuration",
                              "sales": "Plans and upgrades"}},
        "frustration": {"type": "score", "instructions": "How frustrated is the customer?",
                        "criteria": ["Calm, just stating facts", "Frustrated but civil", "Very angry, strong language"]},
    },
}

rows = []
def add(domain, state, gold, tier, variant=None, paraphrase_of=None):
    qkey = domain
    rows.append({"id": f"{domain}-{len([r for r in rows if r['domain']==domain])+1:03d}{('-'+variant) if variant else ''}",
                 "domain": domain, "tier": tier, "state": state,
                 "questions_template": qkey, "questions": QUESTIONS[qkey],
                 "gold": gold, "paraphrase_of": paraphrase_of, "format_variant": variant or "text"})

# --- 1. support (55 unique) ---
urgent_bits = ["URGENT: checkout down for all customers for the last hour, losing sales every minute!",
               "Whenever you get a chance, could you look at my receipt from last week?",
               "Help! My payouts have failed for 3 days and rent is due tomorrow.",
               "Just a quick question about my invoice layout, no rush."]
team_bits = {"billing": "charged twice for September, need a refund of $84.20.",
             "technical": "Stripe connection errors on every checkout, API returns 500.",
             "sales": "we want to upgrade from Starter to Scale, need plan pricing."}
frust_bits = {0: "Thanks for your help, just stating the facts.",
              1: "This is getting frustrating, please fix it soon.",
              2: "I AM FURIOUS, this is UNACCEPTABLE!!! Fix NOW!!!"}
combos = [(1,"technical",2),(1,"billing",1),(0,"sales",0),(0,"billing",0),(1,"technical",1),
          (0,"technical",0),(1,"sales",1),(0,"sales",1),(1,"billing",2)]
for i in range(55):
    u,t,f = combos[i % len(combos)]
    ub = urgent_bits[0 if u else 1] if i % 7 else urgent_bits[2 if u else 3]
    state = f"{ub} Additional detail: customer says {team_bits[t]} {frust_bits[f]} Ticket ref T-{7000+i}."
    tier = "clear" if (u==1 and f>=1) or (u==0 and f==0) else "borderline"
    if i % 11 == 10: tier = "ambiguous"  # mixed-signal exemplar
    add("support", state, {"is_urgent": float(u), "team": t, "frustration": f}, tier)

# --- 2. invoice (45 unique) ---
for i in range(45):
    kind = i % 4
    if kind == 0:
        state = f"Invoice INV-{1000+i} for ${1200+i*37}.50 due 2026-10-15. PO-88{i} matches, vendor tax ID present, line items verified."
        gold = {"needs_human": 0.0, "route": "approve", "completeness": 3}
        tier = "clear"
    elif kind == 1:
        state = f"Invoice INV-{1000+i} for ${300+i*11}. No PO number, missing tax ID. Please advise."
        gold = {"needs_human": 1.0, "route": "request_info", "completeness": 1}
        tier = "clear"
    elif kind == 2:
        state = f"Possible duplicate: INV-{1000+i} for ${9800+i*100} appears twice, amounts round, vendor new. Review urgently."
        gold = {"needs_human": 1.0, "route": "escalate", "completeness": 2}
        tier = "borderline"
    else:
        state = f"Bill INV-{1000+i}: handwritten total $45, no vendor name, dated 2019. Looks invalid."
        gold = {"needs_human": 1.0, "route": "reject", "completeness": 0}
        tier = "clear"
    add("invoice", state, gold, tier)

# --- 3. security (45 unique; varied hosts/services/users so states are distinct) ---
sec0 = ["ransomware detected on {n} prod hosts", "credential-stuffing wave against SSO ({n}k failed logins)",
        "wormable RCE exploit published for our VPN version, {n} edge nodes exposed",
        "exfiltration alert: {n}GB outbound to unknown host from db-{n}"]
sec1 = ["Elevated 500s on {svc} ({p}% error budget burn), suspect bad config push {m} min ago",
        "p99 latency on {svc} up {p}x after deploy #{d}, no data loss yet",
        "{svc} CPU saturation {p}% for {m} min, autoscaler flapping"]
sec2 = ["How do I enable 2FA for my team? No incident, just a how-to question (ticket {i}).",
        "Where do I rotate an API key for {svc}? Docs unclear (ticket {i}).",
        "What's the SLA for {svc} on the {plan} plan? (ticket {i})"]
sec3 = ["Single phishing report from {user}, did not click. Defender quarantined attachment. Monitoring.",
        "{user} forwarded a suspicious invoice macro doc; sandbox says benign. Watching.",
        "One malware alert on {user}'s laptop, isolated, reimaging."]
for i in range(45):
    kind = i % 4
    if kind == 0:
        t = sec0[(i // 4) % len(sec0)]
        state = "ALERT: " + t.format(n=3+i, m=5+i, p=1+i, d=100+i, svc=f"api-{'east' if i%2 else 'west'}", user=f"user{i}@acme.co", plan="Scale") + ". Customer data at risk. Contain NOW."
        gold = {"is_critical": 1.0, "team": "secops", "severity": 3}; tier="clear"
    elif kind == 1:
        t = sec1[(i // 4) % len(sec1)]
        state = t.format(svc=f"api-{'east' if i%2 else 'west'}", p=round(0.5+i*0.1,1), m=5+i, d=100+i) + "."
        gold = {"is_critical": 0.0, "team": "platform", "severity": 2}; tier="borderline"
    elif kind == 2:
        t = sec2[(i // 4) % len(sec2)]
        state = t.format(i=i, svc="dashboard", plan="Starter")
        gold = {"is_critical": 0.0, "team": "support", "severity": 0}; tier="clear"
    else:
        t = sec3[(i // 4) % len(sec3)]
        state = t.format(user=f"user{i}@acme.co")
        gold = {"is_critical": 0.0, "team": "secops", "severity": 1}; tier="borderline"
    add("security", state, gold, tier)

# --- 4. toolcall (40 unique; varied wording so states are distinct) ---
call_t = ["Please refund my last charge of ${amt} on card ending {cc}, order #A-{oid}.",
          "Cancel order #A-{oid} and refund ${amt} to card ending {cc}.",
          "Rebook my flight {fl} to Friday and charge the {cc} card (${amt} fare diff).",
          "Rotate the API key for service {svc} (id {oid}) — it leaked at {amt} UTC."]
clar_t = ["Help with my account, it's broken or something ({thing}), not sure what I need.",
          "Something's wrong with {thing} since yesterday, can you look? Not sure what to ask.",
          "My {thing} isn't working — I think? What do you need from me?"]
direct_t = ["What is your refund policy for {plan} plans?",
            "How long do refunds take to card ending {cc}?",
            "Do you offer {plan} discounts for nonprofits?",
            "Where is the {svc} status page?"]
for i in range(40):
    kind = i % 3
    if kind == 0:
        t = call_t[(i // 3) % len(call_t)]
        state = t.format(amt=20+i, cc=4242+i, oid=5000+i, fl=f"LH-{400+i}", svc=f"svc-{i}")
        gold = {"should_call_tool": 1.0, "action": "call_tool"}; tier="clear"
    elif kind == 1:
        t = clar_t[(i // 3) % len(clar_t)]
        state = t.format(thing=["billing page", "SSO login", "API key", "dashboard"][i % 4]) + f" (ref C-{i})"
        gold = {"should_call_tool": 0.0, "action": "ask_clarify"}; tier="borderline"
    else:
        t = direct_t[(i // 3) % len(direct_t)]
        state = t.format(plan=["annual", "monthly", "team"][(i // 3) % 3], cc=1000+i, svc="API") + f" (ref Q-{i})"
        gold = {"should_call_tool": 0.0, "action": "answer_directly"}; tier="clear"
    add("toolcall", state, gold, tier)

# --- 5. guardrail: 20 ambiguous + 10 OOS (unique) ---
amb = ["My bill looks off and also the dashboard won't load — charged $90 and seeing 500 errors.",
       "We might upgrade but first why was I charged twice? Also SSO is broken.",
       "Refund requested Friday, still waiting, and docs page 404s."]
for i in range(20):
    state = amb[i % len(amb)] + f" (case {i})"
    add("guardrail", state, {"is_urgent": 1.0, "team": "billing", "frustration": 1}, "ambiguous")
oos_states = ["What's a good lasagna recipe for six people?",
              "Explain photosynthesis for my homework.",
              "Who won the 2024 chess championship and what opening did they play?",
              "Write a haiku about rain.",
              "What's the weather in Lisbon next Tuesday?",
              "Summarize the plot of Dune part 2.",
              "How do I bake sourdough?",
              "Translate 'good morning' to Japanese.",
              "What is the capital of Peru?",
              "Tell me a joke about databases."]
for i, s in enumerate(oos_states):
    add("guardrail", s, {"is_urgent": 0.0, "team": "technical", "frustration": 0, "_abstain_expected": True}, "oos")

assert len(rows) == 215, len(rows)

# --- variants to reach 300: 45 paraphrases + 30 json + 10 long ---
def paraphrase(s):
    return s.replace("URGENT:", "Time-sensitive:").replace("Help!", "Please help —").replace("Thanks for your help,", "Appreciate it;").replace("I AM FURIOUS,", "I'm really upset,") + " (Reworded for stability check.)"

base_ids = list(range(len(rows)))
random.shuffle(base_ids)
for k in base_ids[:45]:
    src = dict(rows[k])
    new = dict(src); new["state"] = paraphrase(src["state"]) if isinstance(src["state"], str) else src["state"]
    new["id"] = src["id"] + "-para"; new["paraphrase_of"] = src["id"]; new["format_variant"] = "paraphrase"
    rows.append(new)

for k in base_ids[45:75]:
    src = rows[k]
    if not isinstance(src["state"], str): continue
    new = dict(src); new["state"] = {"transcript": src["state"], "metadata": {"channel": "support-ticket", "locale": "en"}}
    new["id"] = src["id"] + "-json"; new["paraphrase_of"] = src["id"]; new["format_variant"] = "json"
    rows.append(new)

filler = "\n".join(f"[log {i}] 2026-10-01T12:{i:02d}:00Z INFO api latency_ms={100+i} status=200" for i in range(400))
for k in base_ids[75:85]:
    src = rows[k]
    if not isinstance(src["state"], str): continue
    new = dict(src); new["state"] = src["state"] + "\n\n--- attached debug logs ---\n" + filler
    new["id"] = src["id"] + "-long"; new["paraphrase_of"] = src["id"]; new["format_variant"] = "long"
    rows.append(new)

assert len(rows) == 300, len(rows)
random.shuffle(rows)

os.makedirs(ROOT, exist_ok=True)
with open(os.path.join(ROOT, "questions.v1.json"), "w") as fh:
    json.dump(QUESTIONS, fh, indent=2)
with open(os.path.join(ROOT, "gold.v1.jsonl"), "w") as fh:
    for r in rows:
        fh.write(json.dumps(r) + "\n")
from collections import Counter
print("total", len(rows), Counter((r["domain"], r["tier"]) for r in rows), Counter(r["format_variant"] for r in rows))
