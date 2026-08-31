"""Loads repository configuration: threshold profiles, model boundary, optional secrets.

Single responsibility: turn the YAML files under data/config/ into typed
objects and expose standard data paths. Constraints: never raise on missing
optional environment keys; the offline default path must work with no
environment variables set at all.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


class Settings(BaseSettings):
    """Optional opt-ins. Missing keys degrade to the offline path, never error."""

    model_config = SettingsConfigDict(env_prefix="day2ops_", extra="ignore")

    opik_enabled: bool = False
    opik_api_key: str | None = None
    gemini_api_key: str | None = None
    ollama_host: str | None = None


class ThresholdProfile(BaseModel):
    name: str
    status: str = "PROVISIONAL"
    recall_at_5: float = 0.90
    context_precision: float = 0.75
    faithfulness: float = 0.90
    answer_relevance: float = 0.80
    claim_grounding: float = 0.95
    high_risk_faithfulness: float = 0.95
    high_risk_grounding: float = 0.98


class CIGates(BaseModel):
    faithfulness_min_any_tier: float = 0.90
    faithfulness_min_high_risk: float = 0.95
    claim_grounding_min: float = 0.95
    recall_at_5_min: float = 0.90
    block_frozen_decision_change: bool = True
    block_unsupported_on_should_answer: bool = True
    block_false_pass_high_risk: bool = True


class MigrationTolerances(BaseModel):
    faithfulness: float = 0.05
    claim_grounding: float = 0.05
    answer_relevance: float = 0.10
    context_precision: float = 0.10
    context_recall: float = 0.10
    recall_at_5: float = 0.02


class ThresholdConfig(BaseModel):
    active_profile: str
    profiles: dict[str, ThresholdProfile]
    ci_gates: CIGates
    migration_tolerances: MigrationTolerances = Field(default_factory=MigrationTolerances)


class RateLimits(BaseModel):
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000


class ModelSpec(BaseModel):
    provider: str
    model: str
    temperature: float
    rate_limits: RateLimits = Field(default_factory=RateLimits)


class ModelsConfig(BaseModel):
    generator: ModelSpec
    judge: ModelSpec
    embedder: ModelSpec


def load_thresholds(path: Path | None = None) -> ThresholdConfig:
    p = path or (DATA_DIR / "config" / "thresholds.yaml")
    raw: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8"))
    for key, profile in raw["profiles"].items():
        profile.setdefault("name", key)
    return ThresholdConfig.model_validate(raw)


def load_models(path: Path | None = None) -> ModelsConfig:
    p = path or (DATA_DIR / "config" / "models.yaml")
    raw: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8"))
    return ModelsConfig.model_validate(raw)


def data_dir() -> Path:
    return DATA_DIR


def corpus_dir() -> Path:
    return DATA_DIR / "corpus"


def golden_path() -> Path:
    return DATA_DIR / "golden" / "golden_v1.jsonl"
