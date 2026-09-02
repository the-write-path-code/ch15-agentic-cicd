# Chapter 15: CI/CD for Agentic Systems

Companion code for *Building Safe Agentic AI for Enterprise Systems* by Mohit Aggarwal.

This repository shows how to keep an agentic system from degrading after it is deployed. A prompt changes, a model changes, a tool schema changes, a corpus changes, or operational traffic changes. None of those changes needs to raise an exception. The system can keep returning fluent, cited, and wrong answers.

The repository provides the other half of deployment. A deployment pipeline moves a change into production. A merge gate decides whether the change should move at all. The default path is an offline, deterministic evaluation stack over committed synthetic data, baselines, traces, and adversarial cases. It requires no API keys, model server, or network connection.

## What You Will Run

| Chapter section | Demonstration | What it shows |
| --- | --- | --- |
| 15.1 | Continuous grounding validation | A 60-case golden set, committed baseline, deterministic policy gate, and GitHub Actions merge gate that exits nonzero on regression. |
| 15.2 | Prompt regression and model migration | A deliberately degraded prompt, recorded candidate traces, tolerance bands, frozen-case protection, tool-schema checks, and token-budget checks. |
| 15.3 | Live telemetry and drift detection | Offline telemetry fixtures for optimistic-concurrency conflict rates and retrieval-similarity drift. |
| 15.4 | Automated red-teaming | Thirty-nine malicious cases paired with thirty-nine benign controls, plus Layer 7 fault injection to prove fail-closed behavior. |
| 15.5 | Human-in-the-loop feedback | Reviewer overrides become provisional golden cases; reviewed cases can be promoted to `PRODUCTION_FROZEN`; security findings also become adversarial twins. |

The running example is a synthetic policy-compliance question-answering system. It continues the measurement approach from Chapter 4 and applies a compact safety pipeline modeled on the controls in Chapter 14.

## Production Warning

Passing a CI gate does not prove that an agent is safe for production. It proves only that the committed evaluation suite observed the expected behavior for the cases it covers. A missing case, an unrepresentative corpus, a stale baseline, or a poorly chosen threshold can leave a real failure undetected.

Do not use `--update-baseline` to make a failed merge gate pass without reviewing why the behavior changed. A baseline is part of the release contract. Updating it after a regression without human review turns the gate into a record of whatever happened last.

The default mock path is deliberately deterministic. It is a test harness, not a substitute for recording and reviewing real candidate-model behavior before model promotion.

## Prerequisites

- Git
- [uv](https://docs.astral.sh/uv/)
- Python 3.12

Nothing else is required for the default path. The base test suite, evaluation gate, migration replay, drift detectors, red-team suite, and human-review fixture workflow all run offline.

Optional dependencies are used only when you deliberately enable a live or telemetry path:

- Ollama or a Gemini API key for live trace recording.
- Ragas for an optional Ragas judge.
- Opik or Prometheus for optional telemetry export.

## Quick Start

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and synchronize the repository

```bash
git clone https://github.com/the-write-path-code/ch15-agentic-cicd.git
cd ch15-agentic-cicd
uv sync --locked
```

The repository includes `.python-version` and `uv.lock`. `--locked` verifies that the lock file is current and installs the committed dependency set without changing it.

### 3. Run the local quality checks

```bash
uv run ruff check .
uv run mypy src
uv run pytest -q
```

### 4. Run the offline grounding gate

```bash
uv run python scripts/run_eval.py \
  --mode mock \
  --baseline baselines/metrics_baseline.json \
  --fail-on regression
```

This command runs the deterministic evaluation over the golden set, writes reports, and exits nonzero if a configured merge-gate rule fails.

## Configuration

The default repository path uses committed fixtures and configuration files. Do not create a `.env` file unless you are enabling a live integration.

| Path | Purpose |
| --- | --- |
| `data/config/thresholds.yaml` | Threshold profiles, CI merge-gate rules, and migration tolerance bands |
| `data/config/models.yaml` | Pinned generator, judge, embedding boundaries, and token budgets |
| `data/prompts/` | Versioned answer prompts, including the deliberately degraded prompt fixture |
| `data/golden/golden_v1.jsonl` | Golden evaluation cases, statuses, and expected outcomes |
| `baselines/metrics_baseline.json` | Committed metric and decision baseline used by the merge gate |
| `data/traces/` | Baseline and candidate trace fixtures used for deterministic replay |
| `data/adversarial/` | Malicious cases, paired benign controls, and human-review adversarial twins |

### Optional live mode

Install only the extras you intend to use:

```bash
uv sync --locked --extra live
uv sync --locked --extra ragas
uv sync --locked --extra telemetry
```

The live path requires a configured Ollama endpoint or Gemini credential. Keep live credentials in your CI secret store or local shell environment. Do not place them in committed fixtures, prompt files, or reports.

> **Tip**
>
> Run every command in mock mode first. If the offline gate fails, a live model call adds noise without helping you locate the regression.

## Run the Chapter Demonstrations

### 1. Run Continuous Grounding Validation, Section 15.1

```bash
uv run python scripts/run_eval.py \
  --mode mock \
  --baseline baselines/metrics_baseline.json \
  --fail-on regression
```

The runner evaluates the 60-case golden set and writes:

```text
reports/eval_report.json
reports/eval_summary.md
```

The gate checks more than aggregate scores. It also protects per-case outcomes, including `PRODUCTION_FROZEN` cases and high-risk false passes.

A frozen case is a ratchet. If a baseline held a high-risk case at `ABSTAIN`, `BLOCK`, or `HUMAN_REVIEW`, a change that now allows it to answer fails the merge even if aggregate metrics remain acceptable.

### 2. Demonstrate Prompt Regression, Section 15.2

Run the deliberately degraded prompt:

```bash
uv run python scripts/run_eval.py \
  --mode mock \
  --prompt data/prompts/answer_v1_broken.txt \
  --baseline baselines/metrics_baseline.json \
  --fail-on regression
```

The broken prompt is a committed test fixture. It simulates a generator that chooses a superficially matching result, ignores evidence recency, omits citations, and adds an unsupported verification statement. The expected outcome is a failed gate with per-case violations.

The fixture's prompt persona marker is test-harness behavior. It is not a method for controlling a real model in production.

### 3. Run a Model-Migration Replay, Section 15.2

Replay the passing candidate fixture:

```bash
uv run python scripts/swap_model.py --candidate traces_candidate_v1
```

Replay the regressed candidate fixture:

```bash
uv run python scripts/swap_model.py --candidate traces_candidate_regressed
```

The migration gate compares candidate traces against the committed baseline. It checks metric tolerance bands, high-risk faithfulness, frozen-case decisions, recorded tool-call schemas, and token usage.

A candidate can remain inside all aggregate tolerance bands and still fail because it changes a frozen case or violates a high-risk threshold. That is intentional.

The migration report is written to:

```text
reports/migration_report.md
```

### 4. Detect Operational Drift, Section 15.3

Run optimistic-concurrency conflict detection:

```bash
uv run python scripts/detect_drift.py \
  --source data/telemetry/fixtures/occ_retries.jsonl \
  --detector occ
```

Run retrieval-similarity drift detection:

```bash
uv run python scripts/detect_drift.py \
  --source data/telemetry/fixtures/retrieval_similarity.jsonl \
  --detector similarity
```

Each detector reads recorded telemetry windows and exits nonzero when it finds drift.

- The OCC detector alerts on a z-score of at least 3.0 or an absolute conflict count of 25 or more.
- The similarity detector alerts when mean top-five similarity falls below the configured expected-band floor.

A drift alert does not diagnose or repair the problem. It creates an observable event that a team can investigate.

### 5. Run the Red-Team Suite, Section 15.4

Run the paired adversarial suite:

```bash
uv run python scripts/run_redteam.py \
  --suite data/adversarial/adversarial_v1.jsonl
```

The suite contains 39 malicious cases and 39 paired benign controls. A passing run establishes both that each malicious case stopped at the intended layer with the expected reason and that each comparable benign request passed.

Run the Layer 7 failure proof:

```bash
uv run python scripts/run_redteam.py \
  --suite data/adversarial/adversarial_v1.jsonl \
  --fault-inject layer7_scanner
```

The fault-injection run forces the retrieved-context scanner to fail. Every retrieval-dependent case must block. A case that passes while the scanner is broken is a fail-closed violation.

Exit codes:

| Code | Meaning |
| ---: | --- |
| 0 | The expected suite behavior occurred. |
| 2 | A malicious case blocked at the wrong layer or with the wrong reason. |
| 3 | A benign control was blocked. |
| 4 | A retrieval-dependent case passed while the scanner was forced to fail. |

The runner writes a durable audit trail to:

```text
reports/redteam_audit.jsonl
```

### 6. Capture Human Review Feedback, Section 15.5

Process the committed reviewer override fixtures:

```bash
uv run python scripts/capture_overrides.py
```

An override has one of three dispositions:

| Disposition | Effect |
| --- | --- |
| `assert` | Creates a provisional golden case. A security assertion also produces an adversarial twin. |
| `ignore` | Records that the original system behavior was acceptable. No golden case is added. |
| `escalate` | Records that a policy owner or subject-matter decision is required. No golden case is added. |

A new golden case begins as `PROVISIONAL`. It can expose a regression, but it does not become an immutable merge requirement until a reviewer supplies evidence and promotes it.

Promote a reviewed case:

```bash
uv run python scripts/promote_cases.py \
  --case-id golden-0061 \
  --reviewer reviewer-id \
  --evidence ticket-or-policy-reference
```

Promotion is one-way. A `PRODUCTION_FROZEN` case cannot be silently demoted. When policy changes, add a new reviewed case or change the governing source through the appropriate review process.

### 7. Calibrate Threshold Profiles, Section 15.5

```bash
uv run python scripts/calibrate_thresholds.py
```

The script applies the repository's threshold profiles to the full golden set and prints decisions and false-pass and false-block counts by risk tier.

The profiles are:

```text
v1.0-standard
v1.1-strict-safety
v1.2-exploratory
```

A threshold profile must remain provisional until its effect has been reviewed against human-labeled evidence. Do not freeze a profile because it produces a more attractive pass rate.

### 8. Regenerate Committed Fixtures, Maintenance Only

After intentionally changing the corpus, golden set, or prompt, run:

```bash
uv run python scripts/generate_fixtures.py
```

Review the resulting changes to the baseline and trace fixtures as carefully as application-code changes. The GitHub Actions fixture-regeneration workflow performs the same operation when its generator changes.

## Expected Results

### Evaluation gate

A passing mock evaluation prints `GATE PASS`, writes the evaluation reports, and exits with code 0. A failed gate prints a violation list, writes the same reports, and exits nonzero.

### Prompt regression

The deliberately degraded prompt should fail. It creates unsupported claims and grounding violations. A passing result with the broken fixture means the gate has lost coverage.

### Model migration

The `traces_candidate_v1` fixture should pass the migration gate. The `traces_candidate_regressed` fixture should fail because it violates high-risk faithfulness and changes protected decisions.

### Drift detection

The supplied OCC and similarity fixtures are constructed to produce alerts. Each detector prints the affected windows and exits with code 1. An alert is the expected result for these test fixtures.

### Red-team suite

The normal suite should report that 39 malicious cases blocked at the expected layers and 39 benign controls passed. The Layer 7 fault-injection suite should report that the fail-closed contract held because every retrieval-dependent case blocked.

## Run the Tests

```bash
uv run pytest -q
```

The default suite is offline and excludes tests marked `live`.

Run the static checks used in CI:

```bash
uv run ruff check .
uv run mypy src
```

Live tests are opt-in. Configure the live dependencies and credentials first, then run:

```bash
uv run pytest -m live
```

Run the tests before changing prompts, corpus files, golden cases, baselines, threshold profiles, tool schemas, model traces, telemetry-detector logic, or red-team cases.

## Repository Layout

```text
.
├── README.md
├── pyproject.toml
├── uv.lock
├── .python-version
├── baselines/
│   └── metrics_baseline.json          # Committed evaluation baseline
├── data/
│   ├── config/
│   │   ├── thresholds.yaml            # Profiles, CI gates, and tolerances
│   │   └── models.yaml                # Model and token-budget boundaries
│   ├── corpus/                        # Synthetic policy documents
│   ├── prompts/                       # Versioned prompts and degraded fixture
│   ├── golden/                        # Cases, status, audit log, and retired IDs
│   ├── traces/                        # Baseline and candidate replay fixtures
│   ├── adversarial/                   # Malicious cases, controls, and HITL twins
│   ├── telemetry/fixtures/            # OCC, retrieval-similarity, and token windows
│   ├── tools/tool_schemas/            # Committed JSON Schemas for tool contracts
│   └── hitl/overrides/                # Human-review override fixtures
├── src/day2ops/
│   ├── eval/                          # Mock, replay, and optional live evaluation
│   ├── migration/                     # Schema compatibility and token reporting
│   ├── redteam/                       # Layer pipeline and adversarial harness
│   ├── telemetry/                     # Metrics stores and drift detectors
│   ├── hitl/                          # Override capture and promotion logic
│   └── reporting/                     # JSON and Markdown report rendering
├── scripts/
│   ├── run_eval.py
│   ├── swap_model.py
│   ├── detect_drift.py
│   ├── run_redteam.py
│   ├── capture_overrides.py
│   ├── promote_cases.py
│   ├── calibrate_thresholds.py
│   └── generate_fixtures.py
├── workflow/                           # Mermaid diagrams for Chapter 15
├── reports/                            # Generated, ignored output
└── .github/workflows/
    ├── ci.yml
    ├── eval-gate.yml
    ├── migration.yml
    ├── redteam.yml
    └── regen-fixtures.yml
```

## Architecture Diagrams and Supporting Documents

The `workflow/` directory holds six Mermaid diagrams for Chapter 15:

- The pull-request evaluation merge gate.
- A prompt regression caught before merge.
- Model migration replay against a baseline.
- Telemetry collection and drift detection.
- Automated red-teaming with paired benign controls and fault injection.
- The human-review feedback loop from override to frozen case.

Read the merge-gate diagram first. It shows the ordering that governs the repository: pull request, offline evaluation, baseline comparison, nonzero exit on violation, then deployment only after the change is allowed to merge.

## Safety and Operational Limits

- The corpus, prompts, golden cases, candidate traces, and adversarial inputs are synthetic. They demonstrate the evaluation machinery; they do not represent an organization's policies or threat model.
- A mock generator is useful because it makes regression behavior reproducible. It does not predict a live model's future behavior.
- Baseline metrics can hide per-case regressions. That is why frozen cases, false-pass checks, and high-risk thresholds exist alongside aggregate tolerance bands.
- A red-team suite can prove behavior only for the cases it contains. Add cases from real incidents, reviewer corrections, near misses, and newly discovered attack paths.
- A telemetry anomaly identifies a departure from the expected range. It does not identify root cause or prescribe recovery.
- Human overrides are evidence, not automatic training data. `assert`, `ignore`, and `escalate` exist so the system does not turn unresolved policy ambiguity into a permanent test by accident.
- Do not expose raw prompts, retrieved documents, user inputs, proprietary policy material, or live traces in a public CI artifact without a data-classification review.

## Troubleshooting

### `uv sync --locked` fails

The lock file is stale or missing a required resolution. On a development machine with approved network access, update the lock deliberately:

```bash
uv lock
```

Review and commit the resulting `uv.lock` change. Do not remove `--locked` from CI to hide a stale lock file.

### The evaluation gate fails after a prompt or corpus change

Read `reports/eval_summary.md` and `reports/eval_report.json`. Identify whether the violation is a metric regression, an unsupported claim, a frozen-case decision change, a high-risk false pass, or another gate rule. Do not update the baseline until the behavior change is understood and approved.

### The migration fixture cannot be found

Pass either a fixture name located under `data/traces/candidate_fixture/` or an explicit path to a trace file. Inspect the available fixtures before changing the migration command.

### The red-team suite blocks a benign control

This is exit code 3. Review the control and the layer that blocked it. A broad defense that blocks every request is not a passing security result.

### The Layer 7 fault-injection run passes a retrieval-dependent request

This is exit code 4 and a fail-closed defect. Inspect the context-isolation error path. The expected behavior is a typed block when the scanner is unavailable.

### A drift command exits with code 1

For the supplied fixtures, that is expected. The fixture contains windows designed to trigger an alert. In a scheduled production job, code 1 is the signal to create an incident, notify an operator, or begin deeper investigation.

### Live mode cannot connect to a model

The default mock and replay paths do not need a model. Confirm that the `live` extra is installed and that the selected Ollama or Gemini credentials are present before running a live command. Keep generated live traces separate from the approved baseline until review is complete.

## Related Chapters

- Chapter 4 establishes the retrieval, grounding, sufficiency, risk-tier, and deterministic policy-gate concepts that this repository enforces continuously.
- Chapter 8 introduces tool schemas and the boundary they define between a model and external systems.
- Chapter 10 explains why cloud deployments need explicit durability and observability rather than assumptions about one local process.
- Chapters 11 through 13 provide the idempotency and optimistic-concurrency signals that Chapter 15 can monitor for operational drift.
- Chapter 14 defines the fail-closed, context-isolation, action-boundary, and human-review controls tested by the red-team suite.

## License and Errata

See `LICENSE` for licensing terms. Report documentation or code issues through this repository's GitHub issue tracker. Do not include production prompts, secrets, customer data, proprietary documents, or unredacted traces in an issue.
