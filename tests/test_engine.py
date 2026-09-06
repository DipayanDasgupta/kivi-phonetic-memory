"""Unit tests for the Kivi word memory engine.

Run:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(APP_DIR, "app"))

from engine import Engine  # noqa: E402
from phonetics import encode_word, similarity, rewrite as rewrite_span  # noqa: E402
from seed import SEEDS  # noqa: E402
from store import Store  # noqa: E402


def fresh_engine() -> tuple[Engine, Store]:
    path = os.path.join(tempfile.mkdtemp(), "test.db")
    store = Store(path)
    store.reset()
    return Engine(store), store


class TestPhonetics(unittest.TestCase):
    def test_asr_respellings_score_high(self):
        self.assertGreater(similarity("aditya", "aaditya"), 0.85)
        self.assertGreater(similarity("kiwi", "kivi"), 0.75)
        self.assertGreater(similarity("panner", "paneer"), 0.8)

    def test_different_names_stay_apart(self):
        self.assertLess(similarity("aditi", "aaditya"), 0.72)
        self.assertLess(similarity("arvind", "aaditya"), 0.6)

    def test_identical_words(self):
        self.assertEqual(similarity("kiwi", "kiwi"), 1.0)

    def test_encode_deterministic(self):
        self.assertEqual(encode_word("Kivi"), encode_word("kivi"))

    def test_rewrite_preserves_case(self):
        from phonetics import rewrite
        self.assertEqual(rewrite("call ADITYA now", "Aaditya", 5, 11, preserve_case=True),
                         "call AADITYA now")
        self.assertEqual(rewrite("call aditya now", "Aaditya", 5, 11, preserve_case=True),
                         "call aaditya now")
        self.assertEqual(rewrite("call aditya now", "Aaditya", 5, 11, preserve_case=False),
                         "call Aaditya now")


class TestLearning(unittest.TestCase):
    def test_first_correction_is_candidate(self):
        e, _ = fresh_engine()
        r = e.observe(kind="correction", asr="ping mehta", formatted="Ping Mehta.",
                      selection="Mehta", replacement="Mayhta", weight=1)
        self.assertEqual(r.status, "candidate")

    def test_second_sighting_confirms(self):
        e, _ = fresh_engine()
        e.observe(kind="correction", asr="ping mehta", formatted="Ping Mehta.",
                  selection="Mehta", replacement="Mayhta", weight=1)
        r = e.observe(kind="correction", asr="call mehta now", formatted="Call Mehta.",
                      selection="Mehta", replacement="Mayhta", weight=1)
        self.assertTrue(r.promoted)

    def test_common_word_replacement_rejected(self):
        e, _ = fresh_engine()
        r = e.observe(kind="correction", formatted="Send it.", selection="send",
                      replacement="the", weight=2)
        # corrections INTO a common word are refused (formatting's job, not memory)
        self.assertFalse(r.accepted)

    def test_candidate_never_rewrites(self):
        e, _ = fresh_engine()
        e.observe(kind="correction", formatted="Ping Mehta.", selection="Mehta",
                  replacement="Mayhta", weight=1)
        out = e.rewrite("Ping Mehta again.")
        self.assertEqual(out.text, "Ping Mehta again.")
        self.assertEqual(out.decisions, [])


class TestRewrite(unittest.TestCase):
    def test_brief_example(self):
        e, _ = fresh_engine()
        for s in SEEDS:
            e.observe(**s)
        out = e.rewrite("Ask Aditya to review the Sarvam Kiwi service.")
        self.assertEqual(out.text, "Ask Aaditya to review the Sarvam Kivi service.")
        self.assertEqual(len(out.decisions), 2)

    def test_real_word_veto(self):
        e, _ = fresh_engine()
        for s in SEEDS:
            e.observe(**s)
        out = e.rewrite("I like kiwi fruit in the morning.")
        self.assertEqual(out.text, "I like kiwi fruit in the morning.")
        self.assertTrue(all(d.action == "abstain" for d in out.decisions))

    def test_context_rescues(self):
        e, _ = fresh_engine()
        for s in SEEDS:
            e.observe(**s)
        out = e.rewrite("The kiwi service is down.")
        self.assertEqual(out.text, "The Kivi service is down.")

    def test_unrelated_text_untouched(self):
        e, _ = fresh_engine()
        for s in SEEDS:
            e.observe(**s)
        out = e.rewrite("The quick brown fox jumps over the lazy dog.")
        self.assertEqual(out.text, "The quick brown fox jumps over the lazy dog.")

    def test_decisions_carry_reasons(self):
        e, _ = fresh_engine()
        for s in SEEDS:
            e.observe(**s)
        out = e.rewrite("Ask Aditya to review the Sarvam Kiwi service.")
        for d in out.decisions:
            self.assertTrue(d.reason)
            self.assertIsNotNone(d.similarity)


class TestLifecycle(unittest.TestCase):
    def _taught(self):
        e, _ = fresh_engine()
        e.observe(kind="correction", formatted="Email Ananya about the Mehta invoice.",
                  selection="Mehta", replacement="Mayhta", weight=1)
        e.observe(kind="confirm", formatted="Call Mehta about the invoice.",
                  selection="Mehta")
        return e

    def test_conflict_pauses_rewrites(self):
        e = self._taught()
        out = e.rewrite("Email Ananya about the Mehta invoice.")
        self.assertEqual(out.text, "Email Ananya about the Mayhta invoice.")
        # user overrides our rewrite with a third spelling
        e.observe(kind="edit", formatted="File the Mayhta report.", selection="Mayhta",
                  replacement="Mehta")
        out2 = e.rewrite("Email Ananya about the Mayhta invoice again.")
        self.assertEqual(out2.text, "Email Ananya about the Mayhta invoice again.")

    def test_suppressed_word_never_rewritten(self):
        e, store = fresh_engine()
        for s in SEEDS:
            e.observe(**s)
        row = store.get_word("kivi")
        e.suppress(row["id"])
        out = e.rewrite("The kiwi service is down.")
        self.assertEqual(out.text, "The kiwi service is down.")

    def test_delete_removes_memory(self):
        e, store = fresh_engine()
        for s in SEEDS:
            e.observe(**s)
        e.observe(kind="delete", selection="Kivi")
        out = e.rewrite("The kiwi service is down.")
        self.assertEqual(out.text, "The kiwi service is down.")


class TestPersistence(unittest.TestCase):
    def test_state_survives_reconnect(self):
        e, store = fresh_engine()
        for s in SEEDS:
            e.observe(**s)
        # reopen from disk
        store2 = Store(store.path)
        engine2 = Engine(store2)
        out = engine2.rewrite("Ask Aditya to review the Sarvam Kiwi service.")
        self.assertEqual(out.text, "Ask Aaditya to review the Sarvam Kivi service.")

    def test_reset_clears_everything(self):
        e, store = fresh_engine()
        for s in SEEDS:
            e.observe(**s)
        e.forget_all()
        snap = store.snapshot()
        self.assertEqual(snap["words"], [])
        out = e.rewrite("Ask Aditya to review the Sarvam Kiwi service.")
        self.assertEqual(out.text, "Ask Aditya to review the Sarvam Kiwi service.")


if __name__ == "__main__":
    unittest.main()