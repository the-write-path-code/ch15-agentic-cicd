# day2-agentic-cicd

[![ci](https://github.com/mohitagr18/day2-agentic-cicd/actions/workflows/ci.yml/badge.svg)](https://github.com/mohitagr18/day2-agentic-cicd/actions/workflows/ci.yml)
[![eval-gate](https://github.com/mohitagr18/day2-agentic-cicd/actions/workflows/eval-gate.yml/badge.svg)](https://github.com/mohitagr18/day2-agentic-cicd/actions/workflows/eval-gate.yml)
[![redteam](https://github.com/mohitagr18/day2-agentic-cicd/actions/workflows/redteam.yml/badge.svg)](https://github.com/mohitagr18/day2-agentic-cicd/actions/workflows/redteam.yml)

Companion repository for Chapter 15, "Day 2 Operations and CI/CD for Agentic Systems," of the Apress book *The Write Path: Building Safe Agentic AI for Enterprise Systems*. It demonstrates, as working code, how to run CI/CD on a non-deterministic agentic RAG system without weakening the deterministic validation gates the book builds in earlier chapters.

The running example is a policy-compliance question answering system over a synthetic HR and security policy corpus. It continues the Chapter 4 system and wraps it in a compact SentinelAI-style layered security pipeline from Chapter 14.

## Merge gate, not deploy pipeline

Chapter 9 covers the deploy pipeline: GitHub Actions to Cloud Run, the machinery that ships a change. This repository is the other half: the **merge gate** that decides whether a change should ship at all. Every workflow here either scores the system and blocks the merge on regression, or proves the security layers still hold. Nothing in this repo deploys anything.

## Quickstart

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # once, or brew install uv
uv sync                                            # creates .venv, installs project + dev deps
uv run pytest -q                                   # offline, deterministic, green
uv run python scripts/run_eval.py --mode mock      # run the grounding gate
```

No API keys, no Ollama server, no network. Every command goes through uv; never activate a venv by hand.

## What the repo demonstrates

- **Continuous grounding validation (15.1)**: five deterministic evaluation layers over a 60-case golden set, a GitHub Actions gate that blocks merges on regression, and a PR comment with the metrics table.
- **Prompt regression and model migration (15.2)**: a broken prompt fails the gate offline, and cached candidate traces replay against the committed baseline within tolerance bands.
- **Live telemetry and drift detection (15.3)**: OCC retry-rate and retrieval-similarity detectors over hourly windows, with an offline JSONL store and an opt-in Opik backend.
- **Automated red-teaming in CI (15.4)**: 39 malicious cases plus 39 paired benign controls through Layers 1, 2, 10, and 7, with fault injection proving the fail-closed contract.
- **The HITL feedback loop (15.5)**: reviewer overrides become PROVISIONAL golden cases, security blocks generate adversarial twins, and promotion is a one-way ratchet with an audit log.

## Chapter diagrams

The `workflow/` directory holds six standalone Mermaid figures sized for the chapter, one per section plus a bookend overview of the whole Day 2 loop. Render them with `mmdc -i workflow/eval-gate-15-1.mmd -o figure.png` or paste them into your diagram tooling. `workflow/README.md` indexes all six, and `ARCHITECTURE.md` embeds three of them inline with commentary. The diagrams use the same vocabulary as the code, so any figure leads to its implementing module through `BOOK_MAPPING.md`.

## Commands

```bash
uv run python scripts/run_eval.py --mode mock                # grounding gate, exit 0 on pass
uv run python scripts/run_redteam.py                       # 39/39 blocked, 39/39 controls clean
uv run python scripts/run_redteam.py --fault-inject layer7_scanner   # fail-closed proof
uv run python scripts/swap_model.py --candidate traces_candidate_v1        # migration pass
uv run python scripts/swap_model.py --candidate traces_candidate_regressed  # migration fail
uv run python scripts/detect_drift.py --source data/telemetry/fixtures/occ_retries.jsonl --detector occ
uv run python scripts/capture_overrides.py                  # overrides to PROVISIONAL cases
uv run python scripts/promote_cases.py --case-id golden-0061 --reviewer you --evidence ticket-42
uv run python scripts/calibrate_thresholds.py                # decision matrix, three profiles
uv run python scripts/generate_fixtures.py                   # regenerate trace fixtures after data changes
```

## Thresholds: book value to CI rule

| Book gate (Chapter 4) | Value | CI rule that enforces it |
|---|---|---|
| Faithfulness floor, any tier | 0.90 | `eval-gate.yml` fails if any tier aggregate drops below 0.90 |
| Faithfulness floor, high risk | 0.95 | `eval-gate.yml` fails if the high tier drops below 0.95 |
| Claim grounding floor | 0.95 | per-case violation when grounding drops below 0.95 on a should-answer case |
| Unsupported claim | any | per-case violation; an UNSUPPORTED claim blocks the merge |
| Recall@5 floor | 0.90 | aggregate recall@5 below 0.90 fails the run |
| PRODUCTION-FROZEN decision change | none allowed | any decision flip on a frozen case blocks the merge |
| False pass on high-risk case | none allowed | a baseline block that now answers blocks the merge |

The three calibration profiles (`v1.0-standard`, `v1.1-strict-safety`, `v1.2-exploratory`) carry the exact values from Chapter 4.5 and stay PROVISIONAL until human review audit labels land; `calibrate_thresholds.py` refuses to freeze a profile without them.

## Dataset card

All data is synthetic. No real company documents, no personal data.

| Path | Contents |
|---|---|
| `data/corpus/` | 18 Markdown policy documents with YAML frontmatter, chunked at paragraph level. Includes the 90-day notice policy, the superseded 2024 policy, the Field Operations exception, two conflicting remote-work policies, one restricted document, and one document carrying a synthetic injected directive (quarantined at load). |
| `data/golden/golden_v1.jsonl` | 60 golden cases: 12 frozen Chapter 4 seeds, clean answerable cases across risk tiers, retrieval-miss, fabrication-prone, stale-evidence, and scope-exception cases. |
| `data/golden/retired_ids.json` | Retired case ids; ids are never reused. |
| `data/golden/audit_log.jsonl` | Promotion audit entries (case, from, to, reviewer, evidence, timestamp). |
| `data/adversarial/adversarial_v1.jsonl` | 39 malicious cases plus 39 paired benign controls, six categories, each case naming the layer expected to block it. |
| `data/adversarial/adversarial_hitl.jsonl` | Adversarial twins generated from HITL security blocks (created on first capture run). |
| `data/traces/baseline/traces_v1.jsonl` | One recorded trace per golden case from the approved mock run. |
| `data/traces/candidate_fixture/` | The passing candidate (paraphrased, in tolerance) and the regressed candidate (three high-risk cases below 0.90 faithfulness). |
| `data/hitl/overrides/overrides_seed.jsonl` | Eight reviewer records: five assert, two ignore, one escalate. |
| `data/telemetry/fixtures/` | OCC retry windows, retrieval similarity windows, and per-run token usage. |
| `data/tools/tool_schemas/` | Four JSON Schemas with required fields and enums for signature validation. |
| `data/prompts/` | Versioned prompts, including `answer_v1_broken.txt`, the deliberately degraded prompt that fails the gate. |
| `data/config/thresholds.yaml` | The three profiles, the `ci_gates` block, and migration tolerances. |
| `data/config/models.yaml` | The pinned model boundary (generator, judge, embedder) and rate limits. |
| `workflow/` | Six standalone Mermaid diagrams for the chapter, indexed in `workflow/README.md`. |

The persona marker in prompt frontmatter (`faithful`, `fabricating`) is test harness behavior that makes prompt regression demonstrable offline. It is not production behavior; the mock generator reads it to decide which model persona to simulate.

## Live mode and trace recording

The default path is fully offline. To work against real inference:

```bash
uv sync --extra live --extra ragas --extra telemetry
uv run python scripts/run_eval.py --mode live    # needs an Ollama server or a Gemini key
```

Live paths carry `@pytest.mark.live` and are excluded from the default test run. Missing keys degrade to the offline path, they never error. The optional Ragas judge runs only with `--ragas` and the extra installed; CI never installs it. The migration workflow's live job is gated on repository secrets and records fresh traces; the Gemini example it mirrors is a next model release, never an upgrade from Gemini 1.5 Flash (the book's baseline is already Gemini 2.5 Flash).

## Regenerating fixtures

The committed baseline and trace fixtures are pure functions of the committed corpus, golden set, and prompts. After changing any of them, run `uv run python scripts/generate_fixtures.py` and review the diff like any other change. The `regen-fixtures` workflow does the same on GitHub when the generator itself changes and commits the result.

## Required status checks

To make the gates blocking, protect the `main` branch: Settings, Branches, Add rule, then require these checks:

- `ci` (lint, types, tests)
- `eval-gate` (grounding regression)
- `redteam` (adversarial suite plus fault injection)

Tick "Require branches to be up to date" and add CODEOWNERS reviewers as usual. The `migration` workflow is manual dispatch and non-blocking by design.

## Troubleshooting

- **`uv: command not found`**: install it with the curl command in the quickstart, or `brew install uv`. Every command in this README goes through uv.
- **`uv sync --locked` fails in CI with a stale or missing lockfile**: the lockfile is out of date. Run `uv lock` locally, commit `uv.lock`, and push. CI installs from the lockfile and never modifies it.
- **`uv.lock` does not exist yet**: run `uv lock` once on a networked machine and commit the result. Until then the `ci`, `eval-gate`, and `redteam` workflows fail at the sync step; the offline pytest path still passes locally with plain `uv sync`.
- **Live mode connection failures**: check that Ollama is running (`ollama serve`) or that `day2ops_GEMINI_API_KEY` is set. Live tests are skipped by default; run them explicitly with `uv run pytest -m live`.
- **The eval gate fails on a prompt change**: that is the gate working. Point the runner at your prompt with `--prompt data/prompts/your_prompt.txt`, or regenerate the baseline with `--update-baseline` and review the diff before committing it.
