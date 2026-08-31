"""Loads the synthetic policy corpus and quarantines poisoned chunks.

Single responsibility: parse the Markdown files with YAML frontmatter under
data/corpus/, chunk them at paragraph level, and scan every chunk with the
Layer 1 and Layer 2 checks. Constraints: quarantined chunks stay in the total
count (denominator-preserving) but never enter the retrieval index; all data
is synthetic and contains no real company or personal data.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from day2ops import config
from day2ops.redteam.layers import check_input, check_semantics
from day2ops.schemas import Chunk, PolicyDocument

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
MIN_PARAGRAPH_WORDS = 5


class Corpus(BaseModel):
    documents: list[PolicyDocument] = Field(default_factory=list)
    chunks: list[Chunk] = Field(default_factory=list)
    index_chunks: list[Chunk] = Field(default_factory=list)
    quarantined_chunk_ids: list[str] = Field(default_factory=list)

    def chunks_by_id(self) -> dict[str, Chunk]:
        return {chunk.chunk_id: chunk for chunk in self.chunks}

    def docs_by_id(self) -> dict[str, PolicyDocument]:
        return {doc.doc_id: doc for doc in self.documents}

    def department_docs(self) -> dict[str, list[str]]:
        scoped: dict[str, list[str]] = {}
        for doc in self.documents:
            if doc.department_scope and doc.department_scope != "all":
                scoped.setdefault(doc.department_scope, []).append(doc.doc_id)
        return scoped


def _parse_document(text: str, path: Path) -> PolicyDocument:
    match = FRONTMATTER_RE.match(text)
    if match is None:
        raise ValueError(f"{path.name}: missing YAML frontmatter")
    meta: dict[str, Any] = yaml.safe_load(match.group(1))
    body = text[match.end():]
    doc = PolicyDocument(**meta)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if len(p.split()) >= MIN_PARAGRAPH_WORDS]
    doc.chunks = [
        Chunk(
            chunk_id=f"{doc.doc_id}#{i}",
            doc_id=doc.doc_id,
            text=paragraph,
            classification=doc.classification,
            superseded=doc.superseded_by is not None,
            contains_adversarial_payload=doc.contains_adversarial_payload,
            department_scope=doc.department_scope,
        )
        for i, paragraph in enumerate(paragraphs, start=1)
    ]
    return doc


def load_corpus(directory: Path | None = None) -> Corpus:
    d = directory or config.corpus_dir()
    corpus = Corpus()
    for path in sorted(d.glob("*.md")):
        corpus.documents.append(_parse_document(path.read_text(encoding="utf-8"), path))
    for doc in corpus.documents:
        for chunk in doc.chunks:
            corpus.chunks.append(chunk)
            reason = check_input(chunk.text) or check_semantics(chunk.text)
            if reason is not None:
                corpus.quarantined_chunk_ids.append(chunk.chunk_id)
            else:
                corpus.index_chunks.append(chunk)
    return corpus
