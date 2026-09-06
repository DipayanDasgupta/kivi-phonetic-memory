"""SQLite-backed durable store for Kivi word memory.

Tables
------
word         memory entry: canonical key (lowercase), display form
             (user's capitalisation), part of speech, phonetic key,
             status, source, provenance JSON
word_form    alternative spellings linked to a word (history of forms
             the user has shown or accepted for it)
word_context phrased usage templates ("call <word>", "<word> service")
             and co-occurrence tokens with position kind
word_event   append-only audit log; every learning decision is
             traceable to the events that caused it
word_stat    per-word counters (occurrences, interventions)

Status lifecycle: candidate -> confirmed | suppressed | needs_review.
Only `confirmed` words ever rewrite text.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("KIVI_DB", os.path.join(APP_DIR, "db", "kivi.db"))
SCHEMA_PATH = os.path.join(APP_DIR, "db", "schema.sql")
MIGRATIONS_DIR = os.path.join(APP_DIR, "db", "migrations")

# Learning policy constants - the numbers that govern when evidence
# becomes durable memory (see README "Learning policy" for rationale).
CONFIRM_MIN = 2              # observations needed to confirm a word
CANDIDATE_TTL = 3            # days a candidate survives un-reinforced (reserved)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


def new_id() -> str:
    return uuid.uuid4().hex


@contextmanager
def connect(path: str) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


class Store:
    """All persistence for Kivi word memory lives here."""

    def __init__(self, path: str | None = None):
        self.path = path or DB_PATH
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    # -- schema lifecycle -------------------------------------------------
    def create(self) -> None:
        with connect(self.path) as conn:
            with open(SCHEMA_PATH) as f:
                conn.executescript(f.read())
            conn.execute(
                "INSERT OR IGNORE INTO schema_migration(name, applied_at) VALUES('001_init', ?)",
                (now_iso(),),
            )

    def drop_all(self) -> None:
        with connect(self.path) as conn:
            for t in ("word_event", "word_context", "word_form", "word_stat", "word"):
                conn.execute(f"DROP TABLE IF EXISTS {t}")
            conn.execute("DROP TABLE IF EXISTS schema_migration")

    def reset(self) -> None:
        self.drop_all()
        self.create()

    # -- words -------------------------------------------------------------
    def upsert_word(
        self,
        word: str,
        display: str,
        pos: str,
        phonetic_key: str,
        status: str,
        source: str,
        provenance: dict[str, Any] | None = None,
    ) -> str:
        prov = json.dumps(provenance or {})
        with connect(self.path) as conn:
            conn.execute(
                """INSERT INTO word(id, word, display, pos, phonetic_key, status, source,
                                    provenance, created_at, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(word) DO UPDATE SET
                     display=excluded.display,
                     pos=excluded.pos,
                     status=excluded.status,
                     provenance=excluded.provenance,
                     updated_at=excluded.updated_at""",
                (new_id(), word, display, pos, phonetic_key, status, source, prov, now_iso(), now_iso()),
            )
            row = conn.execute("SELECT id FROM word WHERE word=?", (word,)).fetchone()
            return str(row["id"])

    def get_word(self, word: str) -> sqlite3.Row | None:
        with connect(self.path) as conn:
            return conn.execute("SELECT * FROM word WHERE word=?", (word.lower(),)).fetchone()

    def find_by_form(self, form: str) -> sqlite3.Row | None:
        """Find a word row by canonical spelling OR any stored form."""
        with connect(self.path) as conn:
            r = conn.execute("SELECT * FROM word WHERE word=?", (form.lower(),)).fetchone()
            if r:
                return r
            return conn.execute(
                "SELECT w.* FROM word w JOIN word_form f ON f.word_id=w.id WHERE f.form=?",
                (form.lower(),),
            ).fetchone()

    def all_confirmed_words(self) -> list[sqlite3.Row]:
        with connect(self.path) as conn:
            return conn.execute(
                "SELECT * FROM word WHERE status='confirmed' ORDER BY word"
            ).fetchall()

    def status_forms(self, status: str) -> set[str]:
        """All spellings (canonical + forms) that carry this status."""
        with connect(self.path) as conn:
            rows = conn.execute(
                """SELECT w.word AS word, f.form AS form
                   FROM word w LEFT JOIN word_form f ON f.word_id = w.id
                   WHERE w.status=?""",
                (status,),
            ).fetchall()
            out: set[str] = set()
            for r in rows:
                out.add(r["word"])
                if r["form"]:
                    out.add(r["form"])
            return out

    def delete_word(self, word_id: str) -> None:
        with connect(self.path) as conn:
            conn.execute("DELETE FROM word WHERE id=?", (word_id,))

    def set_status(self, word_id: str, status: str) -> None:
        with connect(self.path) as conn:
            conn.execute(
                "UPDATE word SET status=?, updated_at=? WHERE id=?",
                (status, now_iso(), word_id),
            )

    # -- forms / contexts / stats -------------------------------------------
    def add_form(self, word_id: str, form: str, source: str) -> None:
        f = form.lower().strip()
        if not f:
            return
        with connect(self.path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO word_form(id, word_id, form, source, first_seen, last_seen) "
                "VALUES(?,?,?,?,?,?)",
                (new_id(), word_id, f, source, now_iso(), now_iso()),
            )
            conn.execute(
                "UPDATE word_form SET last_seen=? WHERE word_id=? AND form=?",
                (now_iso(), word_id, f),
            )

    def add_context(self, word_id: str, context: str, position: str, source: str) -> None:
        ctx = context.lower().strip()
        if not ctx:
            return
        with connect(self.path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO word_context(id, word_id, context, position, source, first_seen, last_seen) "
                "VALUES(?,?,?,?,?,?,?)",
                (new_id(), word_id, ctx, position, source, now_iso(), now_iso()),
            )
            conn.execute(
                "UPDATE word_context SET last_seen=? WHERE word_id=? AND context=?",
                (now_iso(), word_id, ctx),
            )

    def contexts_by_word(self) -> dict[str, list[str]]:
        with connect(self.path) as conn:
            rows = conn.execute("SELECT word_id, context FROM word_context").fetchall()
            out: dict[str, list[str]] = {}
            for r in rows:
                out.setdefault(r["word_id"], []).append(r["context"])
            return out

    def bump_stat(self, word_id: str, kind: str) -> None:
        col = "occurrences" if kind == "occurrence" else "interventions"
        with connect(self.path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO word_stat(word_id, occurrences, interventions) VALUES(?,0,0)",
                (word_id,),
            )
            conn.execute(f"UPDATE word_stat SET {col} = {col} + 1 WHERE word_id=?", (word_id,))

    # -- events ---------------------------------------------------------------
    def log_event(self, kind: str, payload: dict[str, Any]) -> str:
        eid = new_id()
        with connect(self.path) as conn:
            conn.execute(
                "INSERT INTO word_event(id, kind, payload, at) VALUES(?,?,?,?)",
                (eid, kind, json.dumps(payload), now_iso()),
            )
        return eid

    def events(self, limit: int = 200) -> list[sqlite3.Row]:
        with connect(self.path) as conn:
            return conn.execute(
                "SELECT * FROM word_event ORDER BY at DESC, rowid DESC LIMIT ?", (limit,)
            ).fetchall()

    def db_size_bytes(self) -> int:
        total = 0
        for suffix in ("", "-wal", "-shm"):
            p = self.path + suffix
            if os.path.exists(p):
                total += os.path.getsize(p)
        return total

    def snapshot(self) -> dict[str, Any]:
        """Full inspectable memory state for the UI and evaluations."""
        with connect(self.path) as conn:
            words = conn.execute("SELECT * FROM word ORDER BY word").fetchall()
            out: dict[str, Any] = {"words": [], "db_bytes": self.db_size_bytes()}
            for w in words:
                forms = conn.execute(
                    "SELECT form, source, first_seen, last_seen FROM word_form WHERE word_id=?",
                    (w["id"],),
                ).fetchall()
                ctxs = conn.execute(
                    "SELECT context, position, source, first_seen, last_seen FROM word_context WHERE word_id=?",
                    (w["id"],),
                ).fetchall()
                stats = conn.execute(
                    "SELECT occurrences, interventions FROM word_stat WHERE word_id=?",
                    (w["id"],),
                ).fetchone()
                out["words"].append(
                    {
                        "id": w["id"],
                        "word": w["word"],
                        "display": w["display"],
                        "pos": w["pos"],
                        "phonetic_key": w["phonetic_key"],
                        "status": w["status"],
                        "source": w["source"],
                        "provenance": json.loads(w["provenance"]),
                        "created_at": w["created_at"],
                        "updated_at": w["updated_at"],
                        "forms": [dict(r) for r in forms],
                        "contexts": [dict(r) for r in ctxs],
                        "occurrences": stats["occurrences"] if stats else 0,
                        "interventions": stats["interventions"] if stats else 0,
                    }
                )
            evs = conn.execute(
                "SELECT kind, payload, at FROM word_event ORDER BY at DESC, rowid DESC LIMIT 50"
            ).fetchall()
            out["events"] = [
                {"kind": e["kind"], "payload": json.loads(e["payload"]), "at": e["at"]} for e in evs
            ]
            return out