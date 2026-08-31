"""Shared fixtures. The sys.path insert keeps tests working from a source
checkout even when the package is not installed."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(scope="session")
def corpus():
    from day2ops.corpus.loader import load_corpus

    return load_corpus()


@pytest.fixture(scope="session")
def golden():
    from day2ops.config import golden_path
    from day2ops.schemas import GoldenCase

    return [
        GoldenCase.model_validate_json(line)
        for line in golden_path().read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
