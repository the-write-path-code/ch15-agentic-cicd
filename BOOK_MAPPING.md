# Book mapping

Every module and script maps to the chapter section it demonstrates and the earlier chapter it builds on.

| Module or script | Chapter section | Builds on |
|---|---|---|
| `src/day2ops/eval/retrieval_metrics.py` | 15.1 | 4 (deterministic retrieval metrics) |
| `src/day2ops/eval/heuristics.py` | 15.1 | 4 (Ragas-aligned heuristic scores) |
| `src/day2ops/eval/grounding.py` | 15.1 | 4 (claim-level grounding) |
| `src/day2ops/eval/sufficiency.py` | 15.1 | 4 (evidence sufficiency) |
| `src/day2ops/eval/gate.py` | 15.1 | 4 (policy gate cascade) |
| `src/day2ops/eval/mock_generator.py` | 15.1 | 4 (evaluation stack), 15.2 (prompt versioning) |
| `src/day2ops/eval/runner.py` | 15.1 | 4 (evaluation orchestration) |
| `src/day2ops/eval/ragas_ci.py` | 15.1 | 4 (optional real Ragas judge, CI only) |
| `src/day2ops/reporting/render.py` | 15.1 | 4 (metrics reporting) |
| `scripts/run_eval.py` | 15.1 | 4 |
| `scripts/generate_fixtures.py` | 15.1 | 4 (baseline provenance) |
| `.github/workflows/eval-gate.yml` | 15.1 | 9 (GitHub Actions patterns) |
| `data/prompts/` | 15.2 | 4 (prompt as versioned input) |
| `data/config/models.yaml` | 15.2 | 9 (pinned model boundary) |
| `src/day2ops/migration/signature_compat.py` | 15.2 | 14 (tool schemas and validation) |
| `src/day2ops/migration/token_report.py` | 15.2 | 9 (rate limits) |
| `scripts/swap_model.py` | 15.2 | 4 (baseline comparison) |
| `.github/workflows/migration.yml` | 15.2 | 9 (dispatch workflows, secret gating) |
| `src/day2ops/telemetry/store.py` | 15.3 | 4 (OpikTracer pattern) |
| `src/day2ops/telemetry/drift.py` | 15.3 | 13 (OCC conflict and retry signal) |
| `src/day2ops/telemetry/prometheus_export.py` | 15.3 | 4 (telemetry export) |
| `scripts/detect_drift.py` | 15.3 | 13 |
| `src/day2ops/redteam/layers.py` | 15.4 | 14 (SentinelAI Layers 1, 2, 7, 10) |
| `src/day2ops/redteam/pipeline.py` | 15.4 | 14 (fail-closed run_pipeline contract) |
| `scripts/run_redteam.py` | 15.4 | 14 (adversarial evaluation, 39 cases) |
| `.github/workflows/redteam.yml` | 15.4 | 14 |
| `src/day2ops/hitl/capture.py` | 15.5 | 4 (golden set lifecycle) |
| `src/day2ops/hitl/promote.py` | 15.5 | 4.5 (PROVISIONAL to PRODUCTION-FROZEN) |
| `scripts/capture_overrides.py` | 15.5 | 4 |
| `scripts/promote_cases.py` | 15.5 | 4.5 |
| `scripts/calibrate_thresholds.py` | 15.5 | 4.5 (decision matrix, freeze ratchet) |
| `tests/` | all | 4, 13, 14 (behavior-named tests) |
