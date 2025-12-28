# topics.py
from __future__ import annotations

import re
from typing import List

TOPIC_TAXONOMY = [
    "Arts, culture and sport",
    "Building and planning",
    "Business, economy and innovation",
    "Children and families",
    "Communities and regeneration",
    "Coronavirus (COVID-19)",
    "Digital",
    "Education and skills",
    "Employment and work",
    "Environment and climate change",
    "Equality and human rights",
    "Farming and countryside",
    "Health and social care",
    "Housing",
    "International and EU",
    "Justice and law",
    "Marine and fisheries",
    "Public sector",
    "Transport",
    "Welsh language",
]

TOPIC_KEYWORDS = {
    "Health and social care": ["nhs", "health", "care", "hospital", "dental", "cancer", "mental health"],
    "Education and skills": ["school", "education", "learner", "curriculum", "inset", "teacher", "university"],
    "Transport": ["transport", "rail", "bus", "road", "traffic", "20mph", "active travel"],
    "Environment and climate change": ["climate", "flood", "carbon", "emissions", "energy", "net zero", "environment"],
    "Business, economy and innovation": ["economy", "business", "investment", "innovation", "trade", "growth"],
    "Housing": ["housing", "rent", "landlord", "homeless", "property"],
    "Justice and law": ["law", "legal", "justice", "tribunal", "statutory", "legislation", "order"],
    "Public sector": ["public", "government", "local authority", "council", "procurement"],
    "Children and families": ["child", "children", "family", "safeguarding", "looked after"],
    "Coronavirus (COVID-19)": ["covid", "coronavirus", "pandemic"],
    "Welsh language": ["welsh language", "cymraeg", "welsh-speaking"],
    "Digital": ["digital", "data", "online", "ai", "technology"],
    "Employment and work": ["employment", "work", "jobs", "labour market", "wages"],
}

def _score(text: str) -> dict:
    t = (text or "").lower()
    scores = {k: 0 for k in TOPIC_TAXONOMY}
    for topic, kws in TOPIC_KEYWORDS.items():
        for kw in kws:
            if re.search(r"\b" + re.escape(kw) + r"\b", t):
                scores[topic] += 1
    return scores

def guess_topics(title: str, body: str, max_topics: int = 3) -> List[str]:
    scores = _score((title or "") + " " + (body or ""))
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    chosen = [t for t, s in ranked if s > 0][:max_topics]
    return chosen
