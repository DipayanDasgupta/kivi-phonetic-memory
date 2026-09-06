"""Reproducible end-to-end evaluation for Kivi word memory.

Product claim under test: "after ordinary teaching events, Kivi rewrites
the user's words in new transcripts, and deliberately does nothing when
its evidence is weak, wrong, or silenced."

Method
------
1. Fresh database in an isolated location (never touches the demo DB).
2. Apply the seed observations (same code path as `python3 -m app.seed`).
3. Run the case suite. Every case declares inputs, the exact expected
   memory-aware output, and the expected action for each notable span
   (rewrite / abstain / none).
4. Per case we record actual output, per-word decisions with reasons,
   the relevant memory state, latency, and db size. Failures stay in
   the report - the evaluation does not hide them.
5. Results are tallied (useful vs unnecessary interventions, correct
   abstentions, latency, storage) and written to evals/results.json
   and evals/results.md.

Run:  python3 -m evals.run_eval        (from repo root)
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from typing import Any

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(APP_DIR, "app"))
sys.path.insert(0, APP_DIR)

from engine import Engine  # noqa: E402
from store import Store  # noqa: E402
from seed import SEEDS  # noqa: E402

RESULTS_DIR = os.path.join(APP_DIR, "evals")


@dataclass
class Case:
    id: str
    group: str                          # positive | negative | boundary | lifecycle
    formatted: str                      # input: formatted transcript
    asr: str = ""                       # input: raw ASR (optional evidence)
    expect_text: str = ""               # exact expected memory-aware output
    expect_actions: dict[str, str] = field(default_factory=dict)  # token -> rewrite|abstain
    note: str = ""


CASES: list[Case] = [
    # ---- positive: memory should intervene ------------------------------
    Case(
        id="P1_brief_example",
        group="positive",
        formatted="Ask Aditya to review the Sarvam Kiwi service.",
        asr="ask aditya to review the sarvam kiwi service",
        expect_text="Ask Aaditya to review the Sarvam Kivi service.",
        expect_actions={"Aditya": "rewrite", "Kiwi": "rewrite"},
        note="The exact example from the brief, after teaching both words.",
    ),
    Case(
        id="P2_new_sentence_same_words",
        group="positive",
        formatted="Ping Aditya about the Sarvam Kiwi launch.",
        expect_text="Ping Aaditya about the Sarvam Kivi launch.",
        expect_actions={"Aditya": "rewrite", "Kiwi": "rewrite"},
        note="Memory must generalise beyond the sentence it was taught in.",
    ),
    Case(
        id="P3_lowercase_input",
        group="positive",
        formatted="can you ask aditya to join the kiwi call",
        expect_text="can you ask Aaditya to join the Kivi call",
        expect_actions={"aditya": "rewrite", "kiwi": "rewrite"},
        note="Proper nouns take their taught Title form regardless of "
             "input case; taught companion words supply context for kiwi.",
    ),
    Case(
        id="P4_paneer_variant",
        group="positive",
        formatted="Order more panner for the team lunch.",
        expect_text="Order more paneer for the team lunch.",
        expect_actions={"panner": "rewrite"},
        note="Food romanisation learned from a grocery correction.",
    ),
    Case(
        id="P5_caps_input",
        group="positive",
        formatted="Review the ADITYA migration before Friday.",
        expect_text="Review the Aaditya migration before Friday.",
        expect_actions={"ADITYA": "rewrite"},
        note="Proper nouns normalise to the taught Title form; the engine "
             "does not mirror SHOUTING because names are Title case in prose.",
    ),
    Case(
        id="P6_casing_preference",
        group="positive",
        formatted="Email the urzoo team about pricing.",
        expect_text="Email the UrZoo team about pricing.",
        expect_actions={"urzoo": "rewrite"},
        note="The user taught exact casing (UrZoo); even lowercase input "
             "is rewritten to the taught display form.",
    ),

    # ---- negative: memory must deliberately do nothing ------------------
    Case(
        id="N1_unrelated_text",
        group="negative",
        formatted="The quick brown fox jumps over the lazy dog.",
        expect_text="The quick brown fox jumps over the lazy dog.",
        expect_actions={},
        note="Ordinary English passes through untouched.",
    ),
    Case(
        id="N2_similar_but_not_taught",
        group="negative",
        formatted="Ask Aditi to review the service.",
        expect_text="Ask Aditi to review the service.",
        expect_actions={"Aditi": "abstain"},
        note="'Aditi' resembles 'Aaditya' (sim 0.70) but is a different "
             "name; below the strong threshold and no context support, so "
             "the engine records an abstention instead of guessing.",
    ),
    Case(
        id="N3_common_word_homophone_risk",
        group="negative",
        formatted="I like kiwi fruit in the morning.",
        asr="i like kiwi fruit in the morning",
        expect_text="I like kiwi fruit in the morning.",
        expect_actions={"kiwi": "abstain"},
        note="'kiwi' here IS the fruit. Rewriting a dictionary word "
             "requires supporting context; none appears, so it abstains.",
    ),
    Case(
        id="N4_candidate_not_yet_confirmed",
        group="negative",
        formatted="Ship the flurbo widget to production.",
        expect_text="Ship the flurbo widget to production.",
        expect_actions={},
        note="Runs against a candidate-only word; candidates never rewrite.",
    ),

    # ---- boundary: context rescues a sub-strong match --------------------
    Case(
        id="B1_kiwi_with_service_context",
        group="boundary",
        formatted="The kiwi service is down.",
        expect_text="The Kivi service is down.",
        expect_actions={"kiwi": "rewrite"},
        note="Product-sense context (stored template '<word> service') "
             "pushes the match over the intervention threshold.",
    ),
    Case(
        id="B2_already_canonical",
        group="boundary",
        formatted="Buy paneer at the market.",
        expect_text="Buy paneer at the market.",
        expect_actions={},
        note="Already-canonical spelling is left alone (no churn).",
    ),

    # ---- lifecycle: candidate -> confirmed -> conflict -> suppressed -----
    Case(
        id="L1_candidate_never_rewrites",
        group="lifecycle",
        formatted="Email Ananya about the Mehta invoice.",
        expect_text="Email Ananya about the Mehta invoice.",
        expect_actions={},
        note="First sighting of Mehta->Mayhta is only a candidate "
             "(weight 1): it must not rewrite yet.",
    ),
    Case(
        id="L2_confirmed_rewrites",
        group="lifecycle",
        formatted="Email Ananya about the Mehta invoice again.",
        expect_text="Email Ananya about the Mayhta invoice again.",
        expect_actions={"Mehta": "rewrite"},
        note="After a confirming second sighting, the word rewrites new "
             "sentences.",
    ),
    Case(
        id="L3_user_override_pauses",
        group="lifecycle",
        formatted="File the Mehta report under M.",
        expect_text="File the Mehta report under M.",
        expect_actions={"Mehta": "abstain"},
        note="The user re-edited our rewrite to a third spelling; the "
             "word is flagged needs_review and rewrites pause for it and "
             "all its forms.",
    ),
    Case(
        id="L4_suppressed_word_never_rewritten",
        group="lifecycle",
        formatted="The Kiwi launch went well.",
        expect_text="The Kiwi launch went well.",
        expect_actions={"Kiwi": "abstain"},
        note="After suppressing 'kivi' from the memory UI, the word (and "
             "its forms) is never rewritten again; the abstention is "
             "still logged for inspectability.",
    ),
]


@dataclass
class CaseResult:
    case_id: str
    group: str
    inputs: dict[str, str]
    expected_text: str
    actual_text: str
    passed: bool
    expected_actions: dict[str, str]
    actual_actions: dict[str, str]
    decisions: list[dict[str, Any]]
    memory_state_digest: dict[str, Any]
    latency_ms: float
    db_bytes: int
    failure_reason: str = ""


def _digest(store: Store, keywords: tuple[str, ...]) -> dict[str, Any]:
    snap = store.snapshot()
    kw = tuple(k.lower() for k in keywords)
    words = [
        {
            "word": w["word"], "display": w["display"], "status": w["status"],
            "occurrences": w["occurrences"], "interventions": w["interventions"],
            "forms": [f["form"] for f in w["forms"]],
            "contexts": [c["context"] for c in w["contexts"]],
        }
        for w in snap["words"] if any(k in w["word"] for k in kw)
    ]
    return {"relevant_words": words, "total_events": len(store.events(limit=10_000))}


def run() -> dict[str, Any]:
    eval_db = os.environ.get("KIVI_EVAL_DB", os.path.join(tempfile.gettempdir(), "kivi_eval.db"))
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(eval_db + suffix):
            os.remove(eval_db + suffix)
    store = Store(eval_db)
    store.reset()
    eng = Engine(store)

    for s in SEEDS:
        eng.observe(**s)

    # documented per-case setup (see Case.note)
    eng.observe(kind="confirm", asr="ship the flurbo widget",
                formatted="Ship the flurbo widget to production.", selection="flurbo")
    eng.observe(kind="correction", asr="email ananya about the mehta invoice",
                formatted="Email Ananya about the Mehta invoice.",
                selection="Mehta", replacement="Mayhta", weight=1)

    results: list[CaseResult] = []
    for case in CASES:
        if case.id == "L2_confirmed_rewrites":
            eng.observe(kind="confirm", asr="call mehta about the invoice",
                        formatted="Call Mehta about the invoice.", selection="Mehta")
        if case.id == "L3_user_override_pauses":
            eng.observe(kind="edit", asr="file the mehta report under m",
                        formatted="File the Mehta report under M.",
                        selection="Mayhta", replacement="Mehta")
        if case.id == "L4_suppressed_word_never_rewritten":
            eng.observe(kind="correction", asr="the kivi launch went well",
                        formatted="The Kiwi launch went well.",
                        selection="Kiwi", replacement="Kivi", weight=2)
            row = store.get_word("kivi")
            if row is not None:
                eng.suppress(row["id"])

        r = eng.rewrite(case.formatted, case.asr)
        actual_actions = {d.original: d.action for d in r.decisions}
        passed = r.text == case.expect_text and actual_actions == case.expect_actions
        failures = []
        if r.text != case.expect_text:
            failures.append(f"text {r.text!r} != {case.expect_text!r}")
        if actual_actions != case.expect_actions:
            failures.append(f"actions {actual_actions} != {case.expect_actions}")

        keywords = tuple(
            t.strip(".,!?;:") for t in case.formatted.split()
            if t.strip(".,!?;:").lower() not in ("the", "a", "an", "to", "of", "is")
        )
        results.append(CaseResult(
            case_id=case.id,
            group=case.group,
            inputs={"asr": case.asr, "formatted": case.formatted},
            expected_text=case.expect_text,
            actual_text=r.text,
            passed=passed,
            expected_actions=case.expect_actions,
            actual_actions=actual_actions,
            decisions=[asdict(d) for d in r.decisions],
            memory_state_digest=_digest(store, keywords),
            latency_ms=round(r.latency_ms, 3),
            db_bytes=r.db_bytes,
            failure_reason="; ".join(failures),
        ))

    total = len(results)
    passed_n = sum(r.passed for r in results)
    useful = sum(
        1 for r in results
        if r.passed and any(a == "rewrite" for a in r.actual_actions.values())
    )
    incorrect = sum(
        1 for r in results
        if not r.passed and any(a == "rewrite" for a in r.actual_actions.values())
    )
    abstains = sum(
        1 for r in results
        if r.passed and r.group in ("negative", "lifecycle", "boundary")
        and not any(a == "rewrite" for a in r.actual_actions.values())
    )
    latencies = [r.latency_ms for r in results]

    report = {
        "summary": {
            "total_cases": total,
            "passed": passed_n,
            "failed": total - passed_n,
            "pass_rate": round(passed_n / total, 4) if total else 0.0,
            "useful_interventions": useful,
            "unnecessary_or_incorrect_interventions": incorrect,
            "correct_deliberate_abstentions": abstains,
            "avg_latency_ms": round(sum(latencies) / max(len(latencies), 1), 3),
            "max_latency_ms": round(max(latencies), 3) if latencies else 0.0,
            "db_bytes_after_eval": results[-1].db_bytes if results else 0,
            "model_usage": "none - phonetic matching is fully local; the memory layer makes no LLM calls",
            "cost": "0 API calls, 0 tokens; local compute only",
            "note": "A failed case means the engine disagreed with the declared expectation; "
                    "every case's inputs, decisions and reasons are recorded below.",
        },
        "cases": [asdict(r) for r in results],
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "results.json"), "w") as f:
        json.dump(report, f, indent=2)
    with open(os.path.join(RESULTS_DIR, "results.md"), "w") as f:
        f.write(_markdown(report))

    s = report["summary"]
    print(
        f"Kivi word memory evaluation\n"
        f"  cases {s['total_cases']} | passed {s['passed']} | failed {s['failed']} | pass rate {s['pass_rate']:.1%}\n"
        f"  useful interventions {s['useful_interventions']} | incorrect/unnecessary {s['unnecessary_or_incorrect_interventions']}"
        f" | deliberate abstentions {s['correct_deliberate_abstentions']}\n"
        f"  avg latency {s['avg_latency_ms']} ms | db after eval {s['db_bytes_after_eval']} bytes\n"
        f"  written to evals/results.json and evals/results.md"
    )
    return report


def _markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Kivi Word Memory - Evaluation Results",
        "",
        "Reproducible run: `python3 -m evals.run_eval` (offline, deterministic).",
        "",
        "## Summary",
        "",
        "| metric | value |",
        "|---|---|",
        f"| cases | {s['total_cases']} |",
        f"| passed | {s['passed']} |",
        f"| failed | {s['failed']} |",
        f"| pass rate | {s['pass_rate']:.1%} |",
        f"| useful interventions | {s['useful_interventions']} |",
        f"| unnecessary/incorrect interventions | {s['unnecessary_or_incorrect_interventions']} |",
        f"| deliberate abstentions | {s['correct_deliberate_abstentions']} |",
        f"| avg latency | {s['avg_latency_ms']} ms |",
        f"| max latency | {s['max_latency_ms']} ms |",
        f"| db size after eval | {s['db_bytes_after_eval']} bytes |",
        f"| model usage | {s['model_usage']} |",
        f"| cost | {s['cost']} |",
        "",
        "## Cases",
        "",
    ]
    for c in report["cases"]:
        lines2 = [
            f"### [{'PASS' if c['passed'] else 'FAIL'}] {c['case_id']} ({c['group']})",
            "",
            f"- input (formatted): `{c['inputs']['formatted']}`",
            f"- input (asr): `{c['inputs']['asr']}`",
            f"- expected: `{c['expected_text']}`",
            f"- actual: `{c['actual_text']}`",
            f"- expected actions: `{c['expected_actions']}`",
            f"- actual actions: `{c['actual_actions']}`",
            "- decisions:",
        ]
        for d in c["decisions"]:
            lines2.append(
                f"  - `{d['action']}` on `{d['original']}` -> `{d['replacement']}` "
                f"(sim {d['similarity']}, ctx {d['context_support']}) - {d['reason']}"
            )
        lines2 += [
            f"- relevant memory state: `{json.dumps(c['memory_state_digest'])}`",
            f"- latency: {c['latency_ms']} ms",
            "",
        ]
        if not c["passed"]:
            lines2 += [f"- FAILURE: {c['failure_reason']}", ""]
        lines.extend(lines2)
    return "\n".join(lines)


if __name__ == "__main__":
    run()