"""Kivi word-level memory engine.

The engine sits between Kivi's ASR/formatting models and the final
memory-aware transcript. It owns two behaviours:

1. LEARN   - ingest observations (corrections, confirmations, edits,
             deletions) and maintain durable word memory.
2. REWRITE - given a formatted transcript, find spans that resemble a
             remembered word and, when policy allows, rewrite them.

Every decision returns a machine-checkable reason string, so the demo
and the evaluation can always answer "why did it do that?".

Design notes
------------
- Confirmation: one correction makes a word a `candidate`; a second
  independent sighting (or any evidence the formatted model itself
  spells the word correctly) confirms it. Only confirmed words rewrite.
- Context evidence: corrections store co-occurring content words and
  phrase templates ("call <word>", "<word> service"). At rewrite time
  this supports borderline matches and protects dictionary words -
  "kiwi" the fruit stays a fruit unless Kivi-product context appears.
- Real-word veto: if a token is a common English word and the memory
  word is not, rewriting requires nonzero context support.
- Edit conflict: when the user edits a span we rewrote to a third
  spelling, memory was wrong, not the user. The word is flagged
  `needs_review` and rewrites pause for it and all of its forms.
- Suppression: a user-silenced word (and all its forms) is never
  rewritten again; the abstention is still logged for inspectability.
"""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common_words import COMMON_WORDS  # noqa: E402
from phonetics import encode_word, similarity, rewrite as _rewrite_span  # noqa: E402
from store import Store, CONFIRM_MIN, now_iso  # noqa: E402

_WORD_RE = re.compile(r"[A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F'’]*")

_STOPWORDS = frozenset("""
the a an and or of to in on at for with is are was were be been being
it this that these those i you he she we they me him her them us my
your our their his its will would can could should shall may might do
does did have has had not no yes if then than so as by from up down
out about into over after before very just also there here what when
where why how who whom which whose
""".split())

_MIN_INTERVENE_SIM = 0.60    # below this: not even a candidate match
_STRONG_INTERVENE_SIM = 0.72  # at/above this, rewrite without context support
_TOKEN_WINDOW = 6             # context-token window around a span
_TOKEN_BOOST = 0.05           # per overlapping context token
_TEMPLATE_BOOST = 0.10        # for a matching phrase template
_MAX_CONTEXT_BOOST = 0.15

_LEAD_TEMPLATES = ("call", "email", "mail", "message", "msg", "ping", "text", "tell", "ask", "invite")
_TAIL_TEMPLATES = ("service", "support", "app", "team", "project", "review")


@dataclass
class Decision:
    """One intervention (or deliberate non-intervention) on a span."""
    start: int
    end: int
    original: str
    replacement: str | None
    action: str                     # rewrite | abstain
    reason: str
    matched_word: str | None = None
    similarity: float | None = None
    context_support: float | None = None


@dataclass
class RewriteResult:
    text: str
    decisions: list[Decision]
    latency_ms: float
    db_bytes: int


@dataclass
class LearnResult:
    accepted: bool
    word: str | None
    status: str
    reason: str
    promoted: bool = False


def _taught_cased(word: str, display: str) -> bool:
    """True when the user taught a capitalised form (Title, UPPER, or
    internally mixed like UrZoo) for a word that is not a dictionary word."""
    if word in COMMON_WORDS:
        return False
    if display.isupper() and len(display) > 1:
        return True
    if display[:1].isupper() and (len(display) == 1 or display[1:].islower()):
        return True
    return not (display.islower() or display.isupper())


class Engine:
    def __init__(self, store: Store):
        self.store = store

    # ------------------------------------------------------------------
    # Observation intake
    # ------------------------------------------------------------------
    def observe(
        self,
        kind: str,                    # correction | confirm | edit | delete | seed
        asr: str = "",
        formatted: str = "",
        selection: str = "",
        replacement: str = "",
        app_context: str = "",
        note: str = "",
        weight: int = 1,
    ) -> LearnResult:
        if kind not in ("correction", "confirm", "edit", "delete", "seed"):
            return LearnResult(False, None, "rejected", f"unknown kind {kind!r}")

        if kind == "delete":
            return self._handle_delete(selection)

        if not selection:
            return LearnResult(False, None, "rejected", "no selection provided")

        sel = selection.strip().lstrip("@#").lower()
        if not sel or sel in _STOPWORDS:
            return LearnResult(False, None, "rejected", f"ignoring common word {sel!r}")

        rep = replacement.strip().lstrip("@#") if replacement else ""
        rep_display = rep
        rep = rep.lower()

        if kind == "confirm":
            return self._handle_confirm(sel, asr, formatted, app_context)
        if kind in ("correction", "seed"):
            return self._handle_correction(sel, rep or sel, asr, formatted, app_context, kind, weight, rep_display)
        return self._handle_edit(sel, rep, asr, formatted, app_context, rep_display)

    # -- handlers ---------------------------------------------------------
    def _handle_correction(
        self, sel: str, rep: str, asr: str, formatted: str, ctx: str, kind: str, weight: int,
        display: str | None = None,
    ) -> LearnResult:
        pos = _classify_pos(sel, rep, ctx, asr, formatted)
        case_only = rep == sel and bool(display) and display.lower() == sel and display != sel
        if not rep or (rep == sel and not case_only):
            return LearnResult(False, sel, "rejected", "replacement equals selection")
        if rep.lower() in _STOPWORDS or rep.lower() in COMMON_WORDS:
            self.store.log_event(
                "learn_reject",
                {"selection": sel, "replacement": rep, "reason": "replacement is a common word"},
            )
            return LearnResult(False, sel, "rejected", "replacement is a common word")

        existing = self.store.find_by_form(sel)
        if existing and existing["word"] == rep:
            return self._reinforce(existing, sel, asr, formatted)
        if existing and existing["word"] != rep:
            return self._conflict(existing, sel, rep)

        # new memory entry
        promoted = False
        status = "candidate"
        w = weight
        # the replacement spelling already appearing in the formatted text
        # is independent evidence of the user's spelling habit
        if _contains_word(formatted, rep):
            w += 1
        if w >= CONFIRM_MIN:
            status = "confirmed"
            promoted = True
        word_id = self.store.upsert_word(
            rep, (display or rep), pos, encode_word(rep), status, f"user_{kind}",
            provenance={
                "first_observation": {
                    "kind": kind, "selection": sel, "replacement": rep,
                    "asr": asr, "formatted": formatted, "app_context": ctx, "at": now_iso(),
                }
            },
        )
        self.store.add_form(word_id, sel, f"user_{kind}")
        if rep != sel:
            self.store.add_form(word_id, rep, f"user_{kind}")
        self._store_contexts(word_id, sel, asr or formatted, status == "confirmed")
        self.store.bump_stat(word_id, "occurrence")
        self.store.log_event(
            "learn",
            {"kind": kind, "selection": sel, "replacement": rep, "status": status, "pos": pos, "weight": w},
        )
        return LearnResult(True, rep, status, f"stored as {status}", promoted=promoted)

    def _handle_confirm(self, sel: str, asr: str, formatted: str, ctx: str) -> LearnResult:
        """User highlighted a span and left it unchanged (approval)."""
        existing = self.store.find_by_form(sel)
        if not existing:
            pos = _classify_pos(sel, "", ctx, asr, formatted)
            word_id = self.store.upsert_word(
                sel, sel, pos, encode_word(sel), "candidate", "user_confirm",
                provenance={"first_observation": {"kind": "confirm", "selection": sel, "at": now_iso()}},
            )
            self.store.add_form(word_id, sel, "user_confirm")
            self.store.bump_stat(word_id, "occurrence")
            self.store.log_event("learn", {"kind": "confirm_new", "selection": sel, "status": "candidate"})
            return LearnResult(True, sel, "candidate", "stored as candidate")
        return self._reinforce(existing, sel, asr, formatted)

    def _handle_edit(self, sel: str, rep: str, asr: str, formatted: str, ctx: str, display: str | None = None) -> LearnResult:
        """User edited a span we did NOT rewrite, or re-edited a rewrite."""
        existing = self.store.find_by_form(rep) or self.store.find_by_form(sel)
        if existing and existing["word"] == rep and rep != sel:
            return self._reinforce(existing, sel, asr, formatted)
        if existing and existing["word"] != rep:
            return self._conflict(existing, sel, rep)
        return self._handle_correction(sel, rep, asr, formatted, ctx, "edit", 1, display)

    def _handle_delete(self, sel: str) -> LearnResult:
        existing = self.store.find_by_form(sel)
        if not existing:
            return LearnResult(False, sel, "unknown", "word not in memory")
        self.store.delete_word(existing["id"])
        self.store.log_event("delete", {"word": existing["word"], "selection": sel})
        return LearnResult(True, existing["word"], "deleted", "word removed from memory")

    def _reinforce(self, row, form: str, asr: str, formatted: str) -> LearnResult:
        word_id = row["id"]
        self.store.add_form(word_id, form, "reinforce")
        self.store.bump_stat(word_id, "occurrence")
        status = row["status"]
        promoted = False
        if status == "candidate":
            occurrences = self._occurrences(word_id)
            if occurrences >= CONFIRM_MIN:
                self.store.set_status(word_id, "confirmed")
                status = "confirmed"
                promoted = True
                self.store.log_event("confirm", {"word": row["word"], "via": "reinforcement"})
        if status == "confirmed":
            self._store_contexts(word_id, form, asr or formatted, True)
        self.store.log_event("learn", {"kind": "reinforce", "word": row["word"], "form": form, "status": status})
        return LearnResult(True, row["word"], status, "reinforced", promoted=promoted)

    def _conflict(self, row, sel: str, rep: str) -> LearnResult:
        """User changed a word we thought we knew: pause rewrites."""
        self.store.set_status(row["id"], "needs_review")
        self.store.log_event(
            "conflict",
            {"word": row["word"], "selection": sel, "replacement": rep,
             "note": "user overrode memory; rewriting paused until re-taught"},
        )
        return LearnResult(True, row["word"], "needs_review", "user overrode memory; paused")

    def _occurrences(self, word_id: str) -> int:
        import sqlite3

        with sqlite3.connect(self.store.path) as conn:
            r = conn.execute("SELECT occurrences FROM word_stat WHERE word_id=?", (word_id,)).fetchone()
            return int(r[0]) if r else 0

    def _store_contexts(self, word_id: str, sel: str, text: str, confirmed: bool) -> None:
        """Store phrase template + nearby content tokens as context evidence."""
        if not text:
            return
        idx = text.lower().find(sel.lower())
        if idx < 0:
            idx = text.lower().find(sel.lower().replace("aa", "a"))
        if idx < 0:
            idx = max(0, len(text) // 2 - 10)
        before, after = text[:idx].lower().strip(), text[idx + len(sel):].lower().strip()
        if confirmed:
            for verb in _LEAD_TEMPLATES:
                if before.endswith(verb):
                    self.store.add_context(word_id, f"{verb} <word>", "template", "observation")
                    break
            else:
                for noun in _TAIL_TEMPLATES:
                    if after.startswith(noun):
                        self.store.add_context(word_id, f"<word> {noun}", "template", "observation")
                        break
        tokens = [t.lower() for t in _WORD_RE.findall(text)]
        pos = len(_WORD_RE.findall(text[:idx]))
        near = [
            t for i, t in enumerate(tokens)
            if abs(i - pos) <= _TOKEN_WINDOW and t not in _STOPWORDS
            and t not in COMMON_WORDS and t not in (sel, sel.lower())
        ]
        for t in set(near):
            self.store.add_context(word_id, t, "token", "observation")

    # ------------------------------------------------------------------
    # Rewriting
    # ------------------------------------------------------------------
    def rewrite(self, formatted: str, asr: str = "") -> RewriteResult:
        """Produce memory-aware output from a formatted transcript."""
        t0 = time.perf_counter()
        decisions: list[Decision] = []
        if not formatted:
            return RewriteResult(formatted, decisions, 0.0, self.store.db_size_bytes())

        matches = list(_WORD_RE.finditer(formatted))
        if not matches:
            return RewriteResult(formatted, decisions, 0.0, self.store.db_size_bytes())

        confirmed = self.store.all_confirmed_words()
        contexts_by_id = self.store.contexts_by_word()
        needs_review = self.store.status_forms("needs_review")
        suppressed = self.store.status_forms("suppressed")

        # Process right-to-left so earlier replacements never shift the
        # spans of later matches.
        for m in reversed(matches):
            tok = m.group(0)
            low = tok.lower().strip("'’")
            if not low or low in _STOPWORDS:
                continue
            if low in needs_review:
                decisions.append(Decision(
                    m.start(), m.end(), tok, None, "abstain",
                    "word is flagged needs_review after user override; rewriting paused",
                ))
                continue
            if low in suppressed:
                decisions.append(
                    Decision(m.start(), m.end(), tok, None, "abstain",
                             "word is suppressed by user; never rewritten"))
                continue

            best: tuple[float, Any, float] | None = None  # (sim, row, ctxboost)
            for w in confirmed:
                s = similarity(low, w["word"])
                if s < _MIN_INTERVENE_SIM:
                    continue
                ctxboost = _context_boost(contexts_by_id.get(w["id"], []), formatted, m.start(), m.end())
                if best is None or s + ctxboost > best[0] + best[2]:
                    best = (s, w, ctxboost)
            if best is None:
                continue
            s, w, ctxboost = best
            display_row = (w["display"] or w["word"])
            if w["word"] == low and display_row == low:
                continue  # already canonical, including casing
            score = s + ctxboost
            if low in COMMON_WORDS and w["word"] not in COMMON_WORDS and ctxboost <= 0:
                decisions.append(
                    Decision(
                        m.start(), m.end(), tok, w["word"], "abstain",
                        f"real-word risk: '{low}' is a common word; rewriting to '{w['word']}' "
                        f"requires supporting context, which is absent",
                        matched_word=w["word"], similarity=s, context_support=ctxboost,
                    ))
                continue
            if score < _STRONG_INTERVENE_SIM:
                decisions.append(
                    Decision(
                        m.start(), m.end(), tok, w["word"], "abstain",
                        f"similarity {s:.2f} below strong threshold {_STRONG_INTERVENE_SIM:.2f} "
                        f"and context support {ctxboost:.2f} insufficient",
                        matched_word=w["word"], similarity=s, context_support=ctxboost,
                    ))
                continue
            display = w["display"] or w["word"]
            # If the user taught a capitalised form (Aaditya, Kivi, UrZoo),
            # that form is used verbatim: names and brands are Title case
            # in prose regardless of the input's case. Dictionary words and
            # all-lowercase taught forms preserve the span's own pattern.
            preserve = not _taught_cased(w["word"], display)
            formatted = _rewrite_span(formatted, display, m.start(), m.end(), preserve_case=preserve)
            decisions.append(
                Decision(
                    m.start(), m.end(), tok, display, "rewrite",
                    f"phonetic match to confirmed word '{w['word']}' "
                    f"(sim {s:.2f}, context +{ctxboost:.2f})",
                    matched_word=w["word"], similarity=s, context_support=ctxboost,
                ))
            self.store.bump_stat(w["id"], "intervention")

        latency = (time.perf_counter() - t0) * 1000
        return RewriteResult(formatted, decisions, latency, self.store.db_size_bytes())

    # ------------------------------------------------------------------
    # Memory management (UI actions)
    # ------------------------------------------------------------------
    def suppress(self, word_id: str) -> None:
        self.store.set_status(word_id, "suppressed")
        self.store.log_event("suppress", {"word_id": word_id})

    def reconfirm(self, word_id: str) -> None:
        self.store.set_status(word_id, "confirmed")
        self.store.log_event("reconfirm", {"word_id": word_id})

    def forget_all(self) -> None:
        self.store.reset()
        self.store.log_event("reset", {"note": "all memory cleared"})


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _classify_pos(sel: str, rep: str, ctx: str, asr: str, formatted: str) -> str:
    s = (rep or sel).lower()
    if s.isupper() and 2 <= len(s) <= 5:
        return "acronym"
    text = f"{ctx} {asr} {formatted}".lower()
    if any(k in text for k in ("slack", "email", "mail", "call", "message", "ping", "meet")):
        return "person"
    if any(k in text for k in ("team", "company", "labs", "inc")):
        return "org"
    if any(k in text for k in ("service", "app", "project", "product")):
        return "thing"
    return "other"


def _contains_word(text: str, w: str) -> bool:
    return bool(text) and w.lower() in [t.lower() for t in _WORD_RE.findall(text)]


def _context_boost(contexts: list[str], text: str, start: int, end: int) -> float:
    """Boost from stored phrase templates + co-occurring tokens."""
    if not contexts:
        return 0.0
    before = text[:start].lower()
    after = text[end:].lower()
    boost = 0.0
    for ctx in contexts:
        if "<word>" in ctx:
            lead, _, tail = ctx.partition("<word>")
            lead, tail = lead.strip(), tail.replace(">", "").strip()
            if lead and (before.endswith(" " + lead) or before.endswith(lead)):
                boost += _TEMPLATE_BOOST
            elif tail and after.startswith(" " + tail):
                boost += _TEMPLATE_BOOST
        else:
            # co-occurrence token: present anywhere in the transcript
            if ctx in text.lower():
                boost += _TOKEN_BOOST
    return min(boost, _MAX_CONTEXT_BOOST)