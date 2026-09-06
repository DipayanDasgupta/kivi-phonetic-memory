"""Reproducible seed data for Kivi word memory.

Applies a small set of realistic observations through the same
Engine.observe API the UI uses, so seeded state is identical to what a
user clicking through the demo would produce.

Usage:  python3 -m app.seed   (from repo root)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import Engine  # noqa: E402
from store import Store  # noqa: E402

SEEDS = [
    # The canonical example from the brief: two spellings learned as
    # corrections. 'Aditya' is corrected twice (weight 1 each): the second
    # sighting confirms it. 'Kiwi' is corrected once with weight 2 because
    # the correction itself is unambiguous (a brand name).
    {
        "kind": "correction",
        "asr": "ask aditya to review the sarvam kiwi service",
        "formatted": "Ask Aditya to review the Sarvam Kiwi service.",
        "selection": "Aditya",
        "replacement": "Aaditya",
        "weight": 1,
    },
    {
        "kind": "correction",
        "asr": "ping aditya on slack about the deploy",
        "formatted": "Ping Aditya on Slack about the deploy.",
        "selection": "Aditya",
        "replacement": "Aaditya",
        "weight": 1,
    },
    {
        "kind": "correction",
        "asr": "ask aditya to review the sarvam kiwi service",
        "formatted": "Ask Aditya to review the Sarvam Kiwi service.",
        "selection": "Kiwi",
        "replacement": "Kivi",
        "weight": 2,
    },
    # A food word the ASR habitually romanises wrong.
    {
        "kind": "correction",
        "asr": "add milk and panner to the grocery list",
        "formatted": "Add milk and panner to the grocery list.",
        "selection": "panner",
        "replacement": "paneer",
        "weight": 2,
    },
    # A company name with unusual casing the user cares about.
    {
        "kind": "correction",
        "asr": "email veena at urzoo dot com",
        "formatted": "Email Veena at urzoo dot com.",
        "selection": "urzoo",
        "replacement": "UrZoo",
        "weight": 2,
    },
]


def seed(engine: Engine) -> list[dict]:
    return [engine.observe(**s) for s in SEEDS]


if __name__ == "__main__":
    store = Store()
    store.create()
    eng = Engine(store)
    for s, r in zip(SEEDS, seed(eng)):
        print(f"{s['selection']} -> {r.word or '(none)'} [{r.status}] {r.reason}")
    print(f"Seeded {len(SEEDS)} observations into {store.path}")