"""Deterministic BM25 retrieval over the policy corpus.

Single responsibility: rank corpus chunks with BM25Okapi and return stable
top-k results. Constraints: ties break by chunk id so results are fully
deterministic; chunks scoring zero are never returned.
"""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from day2ops.schemas import Chunk, RetrievedChunk

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


class BM25Retriever:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        self._bm25 = BM25Okapi([tokenize(chunk.text) for chunk in chunks])

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        scores = self._bm25.get_scores(tokenize(query))
        order = sorted(
            range(len(scores)),
            key=lambda i: (-scores[i], self._chunks[i].chunk_id),
        )
        results: list[RetrievedChunk] = []
        for i in order[:top_k]:
            if scores[i] > 0:
                results.append(
                    RetrievedChunk(chunk_id=self._chunks[i].chunk_id, score=round(float(scores[i]), 4))
                )
        return results
