"""Shared text utilities for the evaluation layers.

Single responsibility: sentence splitting, citation handling, stopword-filtered
content tokens, statement detection, and token coverage. Constraints: pure
functions, no model calls; the abstention rule mirrors Ragas, where an
abstention decomposes to zero factual statements and is excluded from
faithfulness and grounding denominators; a light plural stem is applied
consistently to both sides of every comparison.
"""
from __future__ import annotations

import re

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?!\[)")
ABSTENTION_RE = re.compile(
    r"^\s*(?:i\s+(?:cannot|can't|don't|do not|am unable to|do not have)|"
    r"unable to|no\s+(?:answer|relevant|information))",
    re.IGNORECASE,
)
CITATION_RE = re.compile(r"\[([A-Z]{2,4}-\d{4}-\d{2}#\d+)\]")
TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "to", "of", "in",
    "on", "for", "and", "or", "if", "it", "its", "this", "that", "these", "those",
    "with", "as", "by", "at", "from", "must", "may", "can", "could", "should",
    "will", "would", "do", "does", "did", "not", "no", "yes", "what", "which",
    "who", "whom", "how", "when", "where", "why", "all", "any", "each", "per",
    "than", "then", "so", "such", "their", "there", "they", "them", "we", "you",
    "i", "our", "your", "my", "he", "she", "his", "her", "have", "has", "had",
    "also", "into", "under", "over", "between", "within", "up", "down", "out",
    "about", "after", "before", "during", "while", "more", "most", "other",
    "some", "only", "own", "same", "too", "very", "just",
}


def split_sentences(answer: str) -> list[str]:
    return [s.strip() for s in SENTENCE_RE.split(answer.strip()) if s.strip()]


def strip_citations(text: str) -> str:
    return CITATION_RE.sub("", text).strip()


def _stem(token: str) -> str:
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def content_tokens(text: str) -> set[str]:
    return {
        _stem(token)
        for token in TOKEN_RE.findall(text.lower())
        if token not in STOPWORDS and len(token) > 1
    }


def is_abstention(sentence: str) -> bool:
    return ABSTENTION_RE.match(sentence) is not None


def is_statement(sentence: str) -> bool:
    return bool(content_tokens(strip_citations(sentence))) and not is_abstention(sentence)


def token_coverage(reference: str, candidate: str) -> float:
    ref = content_tokens(reference)
    if not ref:
        return 1.0
    return len(ref & content_tokens(candidate)) / len(ref)
