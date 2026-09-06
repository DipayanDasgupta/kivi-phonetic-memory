# RUN — Kivi Word Memory

**Primary review method: completely local application** (Python standard
library only — no pip installs, no databases to install, no API keys).

A coding agent should be able to clone this commit, run the commands below
unchanged, and reach every part of the system.

## 1. Required runtimes and versions

- **Python 3.10 or newer** (`python3 --version`). No other runtimes.
- No third-party packages are required at runtime.

## 2. Required environment variables

None. Optional overrides:

| variable | default | purpose |
|---|---|---|
| `KIVI_PORT` | `8000` | port for the demo server |
| `KIVI_DB` | `./db/kivi.db` | demo database location |
| `KIVI_EVAL_DB` | system temp dir | evaluation database location |

There is an `.env.example` documenting this (no LLM keys are needed — the
memory layer is fully local).

## 3. Install dependencies

Nothing to install. Verify Python:

```bash
python3 --version
```

## 4. Create, migrate, and seed the database

Migrations run automatically and idempotently on first server start
(`db/schema.sql` + `db/migrations/*.sql`). To seed the demo journey
explicitly:

```bash
python3 -m app.seed
```

## 5. Start every required process

```bash
python3 app/server.py
```

(equivalent: `KIVI_PORT=8000 python3 app/server.py`). The process prints its
address and database path and stays in the foreground.

## 6. URL / interface to open

Open **http://127.0.0.1:8000** in a browser — the demonstration UI.

## 7. Primary interactions to try

1. **Load the demo journey** — click *Load seed data* (memory panel) or
   `Load demo journey` (reset panel). Teaches: `Aditya→Aaditya`,
   `Kiwi→Kivi`, `panner→paneer`, `urzoo→UrZoo`.
2. **Rewrite the brief's example** — panel 3 already contains
   `Ask Aditya to review the Sarvam Kiwi service.`; click
   *Make it memory-aware*. Expect
   `Ask Aaditya to review the Sarvam Kivi service.` with two rewrite
   decisions and reasons.
3. **Watch it abstain** — rewrite `I like kiwi fruit in the morning.` and
   expect an abstention (real-word veto); rewrite `Ask Aditi to review the
   service.` and expect an abstention (different person, sub-strong match).
4. **Context rescues a match** — rewrite `The kiwi service is down.`
   and expect `The Kivi service is down.` (learned context support).
5. **Inspect memory** — statuses, provenance, learned forms and contexts,
   per-word counters.
6. **Control it** — *Suppress* `kivi`, then rewrite
   `The kiwi service is down.` → untouched. *Forget* a word entirely.
7. **Reset and repeat** — click *Reset memory*, replay the journey.

## 8. Exact command to run the evaluation

```bash
python3 -m evals.run_eval
```

(Offline, deterministic, isolated database; exits 0. Unit tests:
`python3 -m unittest discover -s tests`.)

## 9. Where the evaluation results are written

- `evals/results.json` — full machine-readable report (per-case inputs,
  expected/actual, decisions with reasons, memory digests, latency, db size)
- `evals/results.md` — the same, human-readable
- the console prints the summary table

## 10. Exact procedure for resetting the system

Either:

- **UI**: `Reset memory` button (confirms, then wipes), or
- **CLI**: stop the server and delete the demo database:

```bash
rm -f db/kivi.db db/kivi.db-wal db/kivi.db-shm
python3 app/server.py          # re-creates + migrates schema on start
python3 -m app.seed            # optional: re-apply the seed journey
```

---

## Submission facts

- **Repository layout**

  ```
  app/          engine, phonetics, store, seed, server (stdlib only)
  db/           schema.sql + migrations/
  static/       demonstration UI (single file, no build step)
  evals/        run_eval.py + committed results.json / results.md
  seeds/        seed observations (mirror of app/seed.py SEEDS, JSONL)
  tests/        unittest suite (19 tests)
  ```

- **Port**: 8000 (override with `KIVI_PORT`).
- **Reset safety**: the evaluation always runs on an isolated database; the
  demo database is never touched by the evaluation.
