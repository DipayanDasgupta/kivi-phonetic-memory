"""Phonetic fuzzy matching for Kivi word memory.

ASR errors are phonetically motivated ("aditya" vs "aaditya", "kiwi" vs
"kivi"), so similarity is computed over sound as well as spelling.

- encode_word(): maps graphemes to a compact phonetic token string using
  a rule table (digraphs, vowel teams, silent letters, soft c/g).
- similarity(): 0.3 * phonetic-edit + 0.7 * orthographic-edit (both
  normalised Levenshtein). The orthographic term keeps different names
  with similar sound apart ("Aditi" is NOT "Aaditya"); the phonetic term
  catches ASR-style respellings ("kiwi"/"kivi", "panner"/"paneer").
- rewrite(): span replacement preserving the capitalisation pattern.
"""

from __future__ import annotations

_RULES: dict[str, str] = {
    "tion": "SN", "sion": "SN", "tch": "C", "sch": "S",
    "ch": "C", "sh": "S", "th": "T", "ph": "F", "wh": "V",
    "ck": "K", "ng": "N", "qu": "KW", "gh": "", "kn": "N", "wr": "R",
    "ps": "S", "pn": "N", "mn": "N",
    "ai": "V", "ay": "V", "ea": "V", "ee": "V", "ei": "V", "ey": "V",
    "ie": "V", "oa": "V", "oe": "V", "oo": "V", "ou": "V", "ow": "V",
    "au": "V", "aw": "V", "ue": "V", "ui": "V", "eu": "V",
    "bb": "B", "dd": "D", "ff": "F", "gg": "G", "ll": "L", "mm": "M",
    "nn": "N", "pp": "P", "rr": "R", "ss": "S", "tt": "T", "zz": "Z",
}

_SINGLE: dict[str, str] = {
    "a": "V", "e": "V", "i": "V", "o": "V", "u": "V", "y": "V",
    "b": "B", "c": "K", "d": "D", "f": "F", "g": "G", "h": "",
    "j": "J", "k": "K", "l": "L", "m": "M", "n": "N", "p": "P",
    "q": "K", "r": "R", "s": "S", "t": "T", "v": "V", "w": "V",
    "x": "KS", "z": "S",
}

_SOFT_EI = set("eiy")


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cur[j] = min(
                prev[j] + 1,
                cur[j - 1] + 1,
                prev[j - 1] + (0 if ca == b[j - 1] else 1),
            )
        prev = cur
    return prev[lb]


def encode_word(word: str) -> str:
    """Encode a single word into its phonetic token string."""
    w = word.lower()
    out: list[str] = []
    i, n = 0, len(w)
    while i < n:
        matched = False
        for src in _RULES:
            if w.startswith(src, i):
                out.append(_RULES[src])
                i += len(src)
                matched = True
                break
        if matched:
            continue
        ch = w[i]
        nxt = w[i + 1] if i + 1 < n else ""
        token = _SINGLE.get(ch, "")
        if ch == "c" and nxt in _SOFT_EI:
            token = "S"
        elif ch == "g" and nxt in _SOFT_EI:
            token = "J"
        if token:
            out.append(token)
        i += 1
    collapsed: list[str] = []
    for t in out:
        if t and (not collapsed or collapsed[-1] != t or t not in ("V", "N")):
            collapsed.append(t)
    return "".join(collapsed)


def similarity(a: str, b: str) -> float:
    """Phonetic similarity between two words in [0, 1].

    0.3 * phonetic-edit + 0.7 * orthographic-edit. The orthographic term
    keeps different names with similar sound apart ("Aditi" is not
    "Aaditya"); the phonetic term catches ASR respellings.
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    pa, pb = encode_word(a), encode_word(b)
    if pa and pb:
        phon = 1.0 - _levenshtein(pa, pb) / max(len(pa), len(pb))
    else:
        phon = 0.0
    la, lb = a.lower(), b.lower()
    orth = 1.0 - _levenshtein(la, lb) / max(len(la), len(lb))
    return 0.3 * phon + 0.7 * orth


def rewrite(text: str, target: str, start: int, end: int, preserve_case: bool = True) -> str:
    """Replace text[start:end] with target. With preserve_case, the
    capitalisation pattern of the span is applied to the target
    (UPPER -> upper, Title -> Title, lower -> lower); otherwise the
    target is used verbatim (casing preferences like "UrZoo")."""
    if not preserve_case:
        return text[:start] + target + text[end:]
    span = text[start:end]
    if not span:
        return text[:start] + target + text[start:]
    if span.isupper() and len(span) > 1:
        tgt = target.upper()
    elif span[0].isupper():
        tgt = target[0].upper() + target[1:]
    else:
        tgt = target.lower()
    return text[:start] + tgt + text[end:]