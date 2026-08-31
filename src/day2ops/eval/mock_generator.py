"""Deterministic mock generator driven by the versioned prompt files.

Single responsibility: stand in for the language model in mock mode. The
generator is an extractive reader: it picks the retrieved sentence with the
highest token overlap with the question and formats it per the active prompt.
Constraints: fully deterministic; the persona marker in the prompt frontmatter
is TEST HARNESS behavior that makes prompt regression demonstrable offline,
not production behavior; no prompt file ever reaches a real model here.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from day2ops.eval.textutils import content_tokens, split_sentences
from day2ops.schemas import (
    Chunk,
    GeneratedAnswer,
    PolicyDocument,
    PromptPersona,
    RetrievedChunk,
    SufficiencyClass,
    SufficiencyResult,
)

TEMPORAL_RE = re.compile(r"\b(?:2024|old|earlier)\b", re.IGNORECASE)
CITE_INSTRUCTION_RE = re.compile(r"\bcite\b", re.IGNORECASE)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
ABSTAIN_ANSWER = "I cannot answer this question from the available policies."
FABRICATED_SENTENCE = "This was confirmed in the latest handbook revision."


class AnswerPrompt:
    def __init__(self, version: str, persona: PromptPersona, requires_citations: bool, body: str) -> None:
        self.version = version
        self.persona = persona
        self.requires_citations = requires_citations
        self.body = body


def load_answer_prompt(path: Path) -> AnswerPrompt:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if match is None:
        raise ValueError(f"{path.name}: prompt files require YAML frontmatter")
    meta: dict[str, Any] = yaml.safe_load(match.group(1))
    body = text[match.end():]
    return AnswerPrompt(
        version=str(meta.get("version", path.stem)),
        persona=PromptPersona(str(meta.get("persona", "faithful"))),
        requires_citations=CITE_INSTRUCTION_RE.search(body) is not None,
        body=body,
    )


def load_system_prompt(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    return text[match.end():] if match is not None else text


def _best_sentence(question: str, chunks: list[Chunk]) -> tuple[str, Chunk]:
    q_tokens = content_tokens(question)
    best_sentence, best_chunk, best_score = "", chunks[0], -1.0
    for chunk in chunks:
        for sentence in split_sentences(chunk.text):
            tokens = content_tokens(sentence)
            if not tokens:
                continue
            score = len(tokens & q_tokens) / len(tokens | q_tokens)
            if score > best_score:
                best_sentence, best_chunk, best_score = sentence, chunk, score
    return best_sentence, best_chunk


def _find_in(chunks: list[Chunk], chunk_id: str) -> Chunk | None:
    for chunk in chunks:
        if chunk.chunk_id == chunk_id:
            return chunk
    return None


class MockGenerator:
    def __init__(self, prompt: AnswerPrompt) -> None:
        self._prompt = prompt

    def generate(
        self,
        question: str,
        retrieved: list[RetrievedChunk],
        chunks_by_id: dict[str, Chunk],
        docs_by_id: dict[str, PolicyDocument],
        sufficiency: SufficiencyResult,
    ) -> GeneratedAnswer:
        chunks = [chunks_by_id[rc.chunk_id] for rc in retrieved if rc.chunk_id in chunks_by_id]
        if self._prompt.persona == PromptPersona.FABRICATING:
            return self._fabricate(question, chunks)
        return self._answer_faithfully(question, retrieved, chunks, docs_by_id, sufficiency)

    def _fabricate(self, question: str, chunks: list[Chunk]) -> GeneratedAnswer:
        if not chunks:
            return GeneratedAnswer(
                answer=ABSTAIN_ANSWER, citations=[], persona=self._prompt.persona,
                prompt_version=self._prompt.version,
            )
        sentence, _chunk = _best_sentence(question, chunks)
        return GeneratedAnswer(
            answer=f"{sentence} {FABRICATED_SENTENCE}",
            citations=[],
            persona=self._prompt.persona,
            prompt_version=self._prompt.version,
        )

    def _answer_faithfully(
        self,
        question: str,
        retrieved: list[RetrievedChunk],
        chunks: list[Chunk],
        docs_by_id: dict[str, PolicyDocument],
        sufficiency: SufficiencyResult,
    ) -> GeneratedAnswer:
        if sufficiency.sufficiency == SufficiencyClass.INSUFFICIENT or not chunks:
            return GeneratedAnswer(
                answer=ABSTAIN_ANSWER, citations=[], persona=self._prompt.persona,
                prompt_version=self._prompt.version,
            )
        temporal = TEMPORAL_RE.search(question) is not None
        pool = [c for c in chunks if c.superseded] if temporal else [c for c in chunks if not c.superseded]
        pool = pool or chunks
        sentence, chunk = _best_sentence(question, pool)
        parts = [f"{sentence} [{chunk.chunk_id}]"]
        citations = [chunk.chunk_id]
        if sufficiency.sufficiency == SufficiencyClass.CONFLICTING:
            for cid in sufficiency.relevant_chunk_ids:
                other = _find_in(chunks, cid)
                if other is None or other.doc_id == chunk.doc_id:
                    continue
                for s in split_sentences(other.text):
                    if "approv" in s.lower():
                        parts.append(f"Note: {s} [{other.chunk_id}]")
                        citations.append(other.chunk_id)
                        break
                else:
                    continue
                break
        if (
            sufficiency.sufficiency == SufficiencyClass.PARTIAL
            and sufficiency.reason.startswith("all relevant evidence is superseded")
        ):
            doc = docs_by_id.get(chunk.doc_id)
            if doc is not None and doc.superseded_by:
                for rc in retrieved:
                    candidate = _find_in(chunks, rc.chunk_id)
                    if candidate is not None and candidate.doc_id == doc.superseded_by:
                        citations.append(candidate.chunk_id)
                parts.append(f"Note: {chunk.doc_id} is superseded by {doc.superseded_by}.")
        return GeneratedAnswer(
            answer=" ".join(parts),
            citations=citations,
            persona=self._prompt.persona,
            prompt_version=self._prompt.version,
        )
