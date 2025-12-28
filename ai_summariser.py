# summariser.py
from __future__ import annotations

import re
from collections import Counter
from typing import List


def split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    # crude but works well enough
    sents = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sents if len(s.strip()) > 30]


def summarise(text: str, max_sentences: int = 6) -> str:
    if not text or len(text) < 200:
        return text.strip()

    sentences = split_sentences(text)
    if len(sentences) <= max_sentences:
        return "\n".join(sentences)

    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    freq = Counter(words)

    def score(s: str) -> float:
        w = re.findall(r"[a-zA-Z]{3,}", s.lower())
        if not w:
            return 0.0
        return sum(freq[x] for x in w) / (len(w) + 1)

    ranked = sorted(sentences, key=score, reverse=True)
    chosen = ranked[:max_sentences]

    # keep original order
    chosen_set = set(chosen)
    final = [s for s in sentences if s in chosen_set]
    return "\n".join(final)
