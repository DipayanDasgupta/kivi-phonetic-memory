# Kivi — The Words Kivi Keeps

A word-level **phonetic memory** for Kivi. After ordinary use, Kivi rewrites the
words that belong to *its* user — names, brands, foods, places — in new
transcripts, and **deliberately does nothing** when its evidence is weak, wrong,
or silenced.

This repository is the complete submission for the **Backend-Focused Full
Stack** assignment: the runnable demonstration, the durable store, the
learning policy, and a reproducible evaluation that tests the product claim —
not just the happy path.

---

## The product decision

The brief asks: *what would it mean for Kivi to know this person?* Our answer
at this thin, useful edge:

> Kivi keeps the words the user had to teach it once. Every time the user had
> to correct the transcript, memory failed. A word learned today should never
> need correcting again — and a word Kivi is unsure about should stay
> untouched rather than be guessed at.

Three properties follow, and everything in this system serves them:

1. **Corrections are the curriculum.** The user already fixed the transcript;
   that act of fixing is the strongest possible evidence of what Kivi got
   wrong. No separate "training mode" exists.
2. **Silence beats a wrong guess.** Rewriting is *subtractive trust*: Kivi
   intervenes only when evidence is strong, and records a reasoned abstention
   otherwise. A wrong "fix" destroys trust in every transcript.
3. **Memory is inspectable and reversible.** The user can see every word,
   every piece of provenance, every intervention, and can suppress or forget
   any word. Memory the user cannot inspect is memory they cannot trust.

### The three transcripts

| stage | example | produced by |
|---|---|---|
| ASR output | `ask aditya to review the sarvam kiwi service` | speech recognition |
| formatted output | `Ask Aditya to review the Sarvam Kiwi service.` | Kivi's formatting LLM |
| **memory-aware output** | `Ask Aaditya to review the Sarvam Kivi service.` | **this system** |

The brief does not tell us where the memory-aware output comes from in the
real product. Our demo treats it as a **post-formatting pass** that Kivi can
also inject into the formatting prompt (the memory store and retrieval are
the same; only the consumer differs). This keeps the demonstration honest:
we replay real inputs (ASR + formatted) rather than pretending to run ASR.

---

## What it learns, and what it refuses to learn

An **observation** is one act of user feedback on a transcript, supplied as
`(kind, asr, formatted, selection, replacement)`:

- `correction` — the user replaced span `selection` with `replacement`
  (the brief's example: `Aditya` → `Aaditya`).
- `confirm` — the user highlighted a span and approved it as-is.
- `edit` — the user edited a span we did *not* touch.
- `delete` — the user removes a word from memory.

The engine **refuses** to memorise:

- common English words as canonical forms (`the`, `send`, `kiwi` as a
  *replacement* — formatting is the LLM's job, not memory's), and
- stopword-level corrections (`of` → `have`), which belong to grammar.

Selecting a dictionary word as the *wrong* form is allowed (`kiwi` → `Kivi`
is exactly the user teaching a brand spelling); storing a dictionary word as
the *right* form is not.

### Learning policy (the numbers that govern it)

| policy | value | rationale |
|---|---|---|
| first correction | `candidate` | one correction may be noise; it never rewrites |
| second independent sighting | `confirmed` | corroboration across contexts is memory |
| formatted-output agreement | +1 weight | the formatting LLM *also* spelling it right is evidence of the user's habit |
| rewrites allowed from | `confirmed` only | a lone observation is a hypothesis, not knowledge |
| similarity floor | 0.60 | below this, not even a candidate match |
| strong threshold | 0.72 | at/above this, rewrite without context support |
| real-word veto | required context | rewriting a dictionary word (`kiwi`→`Kivi`) requires supporting context in the sentence |
| user override | `needs_review` | when the user re-edits a rewrite, memory was wrong; rewrites pause for that word and all its forms |
| user suppress | `suppressed` | the word (and every learned form of it) is never rewritten again |

Status lifecycle: `candidate → confirmed → (needs_review | suppressed)`; every
transition is a `word_event` row, so the full history is replayable.

### Casing policy

The user's taught form is stored verbatim as the canonical **display**
(`Aaditya`, `UrZoo`). If the taught form is capitalised, it is used verbatim —
names and brands are Title case in prose regardless of input case
(`ADITYA` → `Aaditya`, `urzoo` → `UrZoo`). Dictionary-word taught forms and
all-lowercase forms preserve the span's own capitalisation pattern
(`panner` → `paneer` in lowercase context stays lowercase).

---

## How rewriting decides

For every word span in the formatted transcript, the engine:

1. **skips** stopwords and spans already canonical (no churn);
2. finds the best **confirmed** memory word by phonetic similarity
   (`0.3·phonetic-edit + 0.7·orthographic-edit` — the blend keeps *different
   names* apart: "Aditi" is not "Aaditya" — while still catching ASR
   respellings like `kiwi`/`kivi`, `panner`/`paneer`);
3. adds **context support** from learned evidence:
   - phrase templates (`call <word>`, `<word> service`) stored at learn time,
   - co-occurring content words (±6 tokens) that travelled with the word;
4. applies the **policy gates**, each with a machine-readable reason:
   - `real-word risk` — token is a dictionary word, memory word is not, and
     context support is zero → abstain (the fruit stays a fruit);
   - `sub-strong match` — similarity + context below the strong threshold →
     abstain (`Aditi` is not `Aaditya`, even though they sound alike);
5. applies the rewrite **right-to-left** so span offsets stay valid, and
   records the decision with its reason, similarity, and context support.

Every decision — intervention *and* abstention — is persisted to the
`word_event` audit log with the inputs that produced it.

---

## Architecture

```
             ┌───────────────────────────────────────────────┐
             │                 static/index.html             │
             │   observe · inspect memory · rewrite · reset  │
             └───────────────┬───────────────────────────────┘
                             │ JSON over HTTP (stdlib http.server)
             ┌───────────────▼───────────────┐
             │           app/server.py       │
             ├───────────────────────────────┤
             │           app/engine.py       │  learning policy + rewriting
             │   ┌───────────────────────┐   │
             │   │  app/phonetics.py     │   │  phonetic encoding, similarity,
             │   │  app/common_words.py  │   │  case-preserving rewrite
             │   └───────────────────────┘   │
             └───────────────┬───────────────┘
                             │
             ┌───────────────▼───────────────┐
             │           app/store.py        │  SQLite (WAL), schema.sql,
             │      db/migrations/*.sql      │  migrations, events, stats
             └───────────────────────────────┘
```

- **Zero third-party runtime dependencies.** Python 3.10+ standard library
  only (SQLite via `sqlite3`, HTTP via `http.server`).
- **Database**: SQLite in WAL mode. Schema in `db/schema.sql`; migrations in
  `db/migrations/` (applied idempotently by `Store.create()`).
- **Durability**: every observation, conflict, suppression and intervention is
  an append-only `word_event` row; per-word counters live in `word_stat`.

### Schema (summary)

| table | purpose |
|---|---|
| `word` | canonical memory entry: key, display form, pos, phonetic key, status, provenance |
| `word_form` | alternative spellings seen/accepted for a word |
| `word_context` | phrase templates + co-occurrence tokens (context evidence) |
| `word_event` | append-only audit log (learn / confirm / conflict / suppress / reset) |
| `word_stat` | per-word occurrence and intervention counters |

---

## The demonstration

A local web UI (no build step, no dependencies):

1. **Provide an observation** — teach Kivi the brief's example and watch a
   candidate become confirmed on its second sighting.
2. **Inspect memory** — every word with status, provenance, forms, learned
   contexts, and counters; suppress or forget any of them.
3. **Rewrite new speech** — feed a fresh formatted transcript and see the
   memory-aware output with per-span decisions *and reasons* (similarity,
   context support, real-word vetoes).
4. **Reset and replay** — wipe everything and run the journey again.

Primary review method and exact commands: see **[RUN.md](RUN.md)**.

---

## Evaluation

`python3 -m evals.run_eval` builds a fresh database, replays the seed
observations, and runs **16 declared cases** across four groups:

- **positive** — memory must intervene (the brief's example in a new
  sentence, lowercase input, food romanisation, casing preferences);
- **negative** — memory must *deliberately do nothing* (ordinary English;
  `Aditi`, a different person who merely sounds alike; `kiwi fruit` with no
  product context; a candidate that hasn't been corroborated);
- **boundary** — context rescues a sub-strong match; already-canonical text
  is untouched;
- **lifecycle** — candidate→confirmed→conflict→suppressed, each step
  verified behaviourally.

Every case records inputs, expected vs actual output, per-span decisions with
reasons, the relevant memory state, latency, and db size. Failures are not
hidden — the report shows them alongside their evidence.

Latest run (committed under `evals/`):

| metric | value |
|---|---|
| cases | 16 |
| passed | 16 |
| useful interventions | 8 |
| unnecessary/incorrect interventions | 0 |
| deliberate abstentions | 8 |
| avg latency per rewrite | ~13 ms |
| db size after evaluation | ~265 KB |
| model usage / cost | none — fully local, 0 API calls |

Reproduce with: `python3 -m evals.run_eval` (also runs offline in CI).

---

## Limitations, honestly

- **English-centric phonetics.** The rule table covers English graphemes and
  a few common transliteration patterns; other scripts need the same
  interface with a different encoder (the interface is one function:
  `encode_word`).
- **No semantic context.** Context support is lexical (templates +
  co-occurrence). "Kiwi" in `the kiwi launch went well` is rescued only
  because co-occurring tokens were learned; a genuinely novel sentence with
  product context but unseen tokens could abstain.
- **Single-user memory.** There is one memory store; multi-user Kivi would
  key every table by user id (schema change, no engine change).
- **Word-level scope.** Multi-word replacements (`new york` → `Nueva York`)
  and morphology (`kiwis`, plural inflections) are out of scope; the engine
  ignores non-1:1 span replacements by design.
- **No streaming.** Rewrites operate on complete formatted transcripts; a
  streaming product would apply decisions per finalised segment.
- **Evaluation scale.** 16 hand-authored cases plus unit tests; a larger
  corpus evaluation (hundreds of cases, generated ASR-noise variants) is the
  natural next step.

## AI use

Code and documentation were drafted with the help of a coding agent
(opencode, GLM) and reviewed by the applicant. The engine's policies
(thresholds, the real-word veto, the lifecycle) are stated explicitly in this
README and enforced in code where every decision is inspectable.
