# Kivi Word Memory - Evaluation Results

Reproducible run: `python3 -m evals.run_eval` (offline, deterministic).

## Summary

| metric | value |
|---|---|
| cases | 16 |
| passed | 16 |
| failed | 0 |
| pass rate | 100.0% |
| useful interventions | 8 |
| unnecessary/incorrect interventions | 0 |
| deliberate abstentions | 8 |
| avg latency | 12.864 ms |
| max latency | 32.807 ms |
| db size after eval | 271280 bytes |
| model usage | none - phonetic matching is fully local; the memory layer makes no LLM calls |
| cost | 0 API calls, 0 tokens; local compute only |

## Cases

### [PASS] P1_brief_example (positive)

- input (formatted): `Ask Aditya to review the Sarvam Kiwi service.`
- input (asr): `ask aditya to review the sarvam kiwi service`
- expected: `Ask Aaditya to review the Sarvam Kivi service.`
- actual: `Ask Aaditya to review the Sarvam Kivi service.`
- expected actions: `{'Aditya': 'rewrite', 'Kiwi': 'rewrite'}`
- actual actions: `{'Kiwi': 'rewrite', 'Aditya': 'rewrite'}`
- decisions:
  - `rewrite` on `Kiwi` -> `Kivi` (sim 0.825, ctx 0.15) - phonetic match to confirmed word 'kivi' (sim 0.82, context +0.15)
  - `rewrite` on `Aditya` -> `Aaditya` (sim 0.8999999999999999, ctx 0.05) - phonetic match to confirmed word 'aaditya' (sim 0.90, context +0.05)
- relevant memory state: `{"relevant_words": [{"word": "aaditya", "display": "Aaditya", "status": "confirmed", "occurrences": 2, "interventions": 1, "forms": ["aaditya", "aditya"], "contexts": ["deploy", "ping <word>", "sarvam", "slack"]}], "total_events": 8}`
- latency: 13.73 ms

### [PASS] P2_new_sentence_same_words (positive)

- input (formatted): `Ping Aditya about the Sarvam Kiwi launch.`
- input (asr): ``
- expected: `Ping Aaditya about the Sarvam Kivi launch.`
- actual: `Ping Aaditya about the Sarvam Kivi launch.`
- expected actions: `{'Aditya': 'rewrite', 'Kiwi': 'rewrite'}`
- actual actions: `{'Kiwi': 'rewrite', 'Aditya': 'rewrite'}`
- decisions:
  - `rewrite` on `Kiwi` -> `Kivi` (sim 0.825, ctx 0.1) - phonetic match to confirmed word 'kivi' (sim 0.82, context +0.10)
  - `rewrite` on `Aditya` -> `Aaditya` (sim 0.8999999999999999, ctx 0.05) - phonetic match to confirmed word 'aaditya' (sim 0.90, context +0.05)
- relevant memory state: `{"relevant_words": [{"word": "aaditya", "display": "Aaditya", "status": "confirmed", "occurrences": 2, "interventions": 2, "forms": ["aaditya", "aditya"], "contexts": ["deploy", "ping <word>", "sarvam", "slack"]}], "total_events": 8}`
- latency: 27.769 ms

### [PASS] P3_lowercase_input (positive)

- input (formatted): `can you ask aditya to join the kiwi call`
- input (asr): ``
- expected: `can you ask Aaditya to join the Kivi call`
- actual: `can you ask Aaditya to join the Kivi call`
- expected actions: `{'aditya': 'rewrite', 'kiwi': 'rewrite'}`
- actual actions: `{'kiwi': 'rewrite', 'aditya': 'rewrite'}`
- decisions:
  - `rewrite` on `kiwi` -> `Kivi` (sim 0.825, ctx 0.05) - phonetic match to confirmed word 'kivi' (sim 0.82, context +0.05)
  - `rewrite` on `aditya` -> `Aaditya` (sim 0.8999999999999999, ctx 0.0) - phonetic match to confirmed word 'aaditya' (sim 0.90, context +0.00)
- relevant memory state: `{"relevant_words": [{"word": "aaditya", "display": "Aaditya", "status": "confirmed", "occurrences": 2, "interventions": 3, "forms": ["aaditya", "aditya"], "contexts": ["deploy", "ping <word>", "sarvam", "slack"]}], "total_events": 8}`
- latency: 32.807 ms

### [PASS] P4_paneer_variant (positive)

- input (formatted): `Order more panner for the team lunch.`
- input (asr): ``
- expected: `Order more paneer for the team lunch.`
- actual: `Order more paneer for the team lunch.`
- expected actions: `{'panner': 'rewrite'}`
- actual actions: `{'panner': 'rewrite'}`
- decisions:
  - `rewrite` on `panner` -> `paneer` (sim 0.8833333333333333, ctx 0.0) - phonetic match to confirmed word 'paneer' (sim 0.88, context +0.00)
- relevant memory state: `{"relevant_words": [], "total_events": 8}`
- latency: 20.799 ms

### [PASS] P5_caps_input (positive)

- input (formatted): `Review the ADITYA migration before Friday.`
- input (asr): ``
- expected: `Review the Aaditya migration before Friday.`
- actual: `Review the Aaditya migration before Friday.`
- expected actions: `{'ADITYA': 'rewrite'}`
- actual actions: `{'ADITYA': 'rewrite'}`
- decisions:
  - `rewrite` on `ADITYA` -> `Aaditya` (sim 0.8999999999999999, ctx 0.0) - phonetic match to confirmed word 'aaditya' (sim 0.90, context +0.00)
- relevant memory state: `{"relevant_words": [{"word": "aaditya", "display": "Aaditya", "status": "confirmed", "occurrences": 2, "interventions": 4, "forms": ["aaditya", "aditya"], "contexts": ["deploy", "ping <word>", "sarvam", "slack"]}], "total_events": 8}`
- latency: 21.363 ms

### [PASS] P6_casing_preference (positive)

- input (formatted): `Email the urzoo team about pricing.`
- input (asr): ``
- expected: `Email the UrZoo team about pricing.`
- actual: `Email the UrZoo team about pricing.`
- expected actions: `{'urzoo': 'rewrite'}`
- actual actions: `{'urzoo': 'rewrite'}`
- decisions:
  - `rewrite` on `urzoo` -> `UrZoo` (sim 1.0, ctx 0.0) - phonetic match to confirmed word 'urzoo' (sim 1.00, context +0.00)
- relevant memory state: `{"relevant_words": [{"word": "urzoo", "display": "UrZoo", "status": "confirmed", "occurrences": 1, "interventions": 1, "forms": ["urzoo"], "contexts": ["com", "dot", "veena"]}], "total_events": 8}`
- latency: 23.343 ms

### [PASS] N1_unrelated_text (negative)

- input (formatted): `The quick brown fox jumps over the lazy dog.`
- input (asr): ``
- expected: `The quick brown fox jumps over the lazy dog.`
- actual: `The quick brown fox jumps over the lazy dog.`
- expected actions: `{}`
- actual actions: `{}`
- decisions:
- relevant memory state: `{"relevant_words": [], "total_events": 8}`
- latency: 4.741 ms

### [PASS] N2_similar_but_not_taught (negative)

- input (formatted): `Ask Aditi to review the service.`
- input (asr): ``
- expected: `Ask Aditi to review the service.`
- actual: `Ask Aditi to review the service.`
- expected actions: `{'Aditi': 'abstain'}`
- actual actions: `{'Aditi': 'abstain'}`
- decisions:
  - `abstain` on `Aditi` -> `aaditya` (sim 0.7, ctx 0.0) - similarity 0.70 below strong threshold 0.72 and context support 0.00 insufficient
- relevant memory state: `{"relevant_words": [], "total_events": 8}`
- latency: 4.567 ms

### [PASS] N3_common_word_homophone_risk (negative)

- input (formatted): `I like kiwi fruit in the morning.`
- input (asr): `i like kiwi fruit in the morning`
- expected: `I like kiwi fruit in the morning.`
- actual: `I like kiwi fruit in the morning.`
- expected actions: `{'kiwi': 'abstain'}`
- actual actions: `{'kiwi': 'abstain'}`
- decisions:
  - `abstain` on `kiwi` -> `kivi` (sim 0.825, ctx 0.0) - real-word risk: 'kiwi' is a common word; rewriting to 'kivi' requires supporting context, which is absent
- relevant memory state: `{"relevant_words": [{"word": "aaditya", "display": "Aaditya", "status": "confirmed", "occurrences": 2, "interventions": 4, "forms": ["aaditya", "aditya"], "contexts": ["deploy", "ping <word>", "sarvam", "slack"]}, {"word": "kivi", "display": "Kivi", "status": "confirmed", "occurrences": 1, "interventions": 3, "forms": ["kivi", "kiwi"], "contexts": ["<word> service", "aditya", "sarvam"]}], "total_events": 8}`
- latency: 4.515 ms

### [PASS] N4_candidate_not_yet_confirmed (negative)

- input (formatted): `Ship the flurbo widget to production.`
- input (asr): ``
- expected: `Ship the flurbo widget to production.`
- actual: `Ship the flurbo widget to production.`
- expected actions: `{}`
- actual actions: `{}`
- decisions:
- relevant memory state: `{"relevant_words": [{"word": "flurbo", "display": "flurbo", "status": "candidate", "occurrences": 1, "interventions": 0, "forms": ["flurbo"], "contexts": []}], "total_events": 8}`
- latency: 7.956 ms

### [PASS] B1_kiwi_with_service_context (boundary)

- input (formatted): `The kiwi service is down.`
- input (asr): ``
- expected: `The Kivi service is down.`
- actual: `The Kivi service is down.`
- expected actions: `{'kiwi': 'rewrite'}`
- actual actions: `{'kiwi': 'rewrite'}`
- decisions:
  - `rewrite` on `kiwi` -> `Kivi` (sim 0.825, ctx 0.1) - phonetic match to confirmed word 'kivi' (sim 0.82, context +0.10)
- relevant memory state: `{"relevant_words": [], "total_events": 8}`
- latency: 17.954 ms

### [PASS] B2_already_canonical (boundary)

- input (formatted): `Buy paneer at the market.`
- input (asr): ``
- expected: `Buy paneer at the market.`
- actual: `Buy paneer at the market.`
- expected actions: `{}`
- actual actions: `{}`
- decisions:
- relevant memory state: `{"relevant_words": [{"word": "paneer", "display": "paneer", "status": "confirmed", "occurrences": 1, "interventions": 1, "forms": ["paneer", "panner"], "contexts": ["add", "grocery", "list"]}], "total_events": 8}`
- latency: 3.965 ms

### [PASS] L1_candidate_never_rewrites (lifecycle)

- input (formatted): `Email Ananya about the Mehta invoice.`
- input (asr): ``
- expected: `Email Ananya about the Mehta invoice.`
- actual: `Email Ananya about the Mehta invoice.`
- expected actions: `{}`
- actual actions: `{}`
- decisions:
- relevant memory state: `{"relevant_words": [], "total_events": 8}`
- latency: 4.753 ms

### [PASS] L2_confirmed_rewrites (lifecycle)

- input (formatted): `Email Ananya about the Mehta invoice again.`
- input (asr): ``
- expected: `Email Ananya about the Mayhta invoice again.`
- actual: `Email Ananya about the Mayhta invoice again.`
- expected actions: `{'Mehta': 'rewrite'}`
- actual actions: `{'Mehta': 'rewrite'}`
- decisions:
  - `rewrite` on `Mehta` -> `Mayhta` (sim 0.7666666666666666, ctx 0.1) - phonetic match to confirmed word 'mayhta' (sim 0.77, context +0.10)
- relevant memory state: `{"relevant_words": [], "total_events": 10}`
- latency: 11.305 ms

### [PASS] L3_user_override_pauses (lifecycle)

- input (formatted): `File the Mehta report under M.`
- input (asr): ``
- expected: `File the Mehta report under M.`
- actual: `File the Mehta report under M.`
- expected actions: `{'Mehta': 'abstain'}`
- actual actions: `{'Mehta': 'abstain'}`
- decisions:
  - `abstain` on `Mehta` -> `None` (sim None, ctx None) - word is flagged needs_review after user override; rewriting paused
- relevant memory state: `{"relevant_words": [{"word": "mayhta", "display": "Mayhta", "status": "needs_review", "occurrences": 2, "interventions": 1, "forms": ["mayhta", "mehta"], "contexts": ["ananya", "call <word>", "invoice"]}], "total_events": 11}`
- latency: 3.549 ms

### [PASS] L4_suppressed_word_never_rewritten (lifecycle)

- input (formatted): `The Kiwi launch went well.`
- input (asr): ``
- expected: `The Kiwi launch went well.`
- actual: `The Kiwi launch went well.`
- expected actions: `{'Kiwi': 'abstain'}`
- actual actions: `{'Kiwi': 'abstain'}`
- decisions:
  - `abstain` on `Kiwi` -> `None` (sim None, ctx None) - word is suppressed by user; never rewritten
- relevant memory state: `{"relevant_words": [], "total_events": 13}`
- latency: 2.701 ms
