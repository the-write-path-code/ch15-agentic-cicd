Chapter diagrams live in `workflow/` as standalone Mermaid files. Render them with any Mermaid toolchain (`mmdc -i workflow/eval-gate-15-1.mmd -o figure.png`) or paste them straight into your chapter tooling.

| File | Shows | Chapter section |
|---|---|---|
| `workflow/overview-day2-merge-gate.mmd` | The Day 2 loop end to end: pull request, the three blocking workflows, merge, and the deploy pipeline handoff. | 15 opening |
| `workflow/eval-gate-15-1.mmd` | The evaluation gate: golden set to answer to merge decision. | 15.1 |
| `workflow/migration-15-2.mmd` | Model migration as a checklist of gates ending in promote or block. | 15.2 |
| `workflow/telemetry-drift-15-3.mmd` | Live drift detection: two signals, two detectors, one alert path. | 15.3 |
| `workflow/redteam-pipeline-15-4.mmd` | The red-team pipeline: four layers in order, audit logging, fail-closed path. | 15.4 |
| `workflow/hitl-loop-15-5.mmd` | The HITL loop: overrides to PROVISIONAL cases, the promotion ratchet, and what promotion enforces in CI. | 15.5 |

All six diagrams use the same vocabulary as the code, so a reader can go from any figure to the module that implements it.

## Interactive Workflow Diagrams

Standalone interactive Archify diagrams rendered with SVG animation, dark/light themes, source links, and export capabilities:

| Interactive Diagram | GitHub Pages Live URL | Focus Area |
|---|---|---|
| `workflow/01_overview_day2_merge_gate.html` | [View 01 Overview](https://the-write-path-code.github.io/ch15-agentic-cicd/workflow/01_overview_day2_merge_gate.html) | The Day 2 loop end to end: pull request, three parallel blocking workflows, and deploy handoff |
| `workflow/02_eval_gate_pipeline.html` | [View 02 Eval Gate](https://the-write-path-code.github.io/ch15-agentic-cicd/workflow/02_eval_gate_pipeline.html) | Golden Set replay, multi-dimensional scoring, policy cascade, and baseline comparison |
| `workflow/03_model_migration_checklist.html` | [View 03 Migration](https://the-write-path-code.github.io/ch15-agentic-cicd/workflow/03_model_migration_checklist.html) | Model migration checklist: deltas, tool schema contracts, token budgets, and frozen cases |
| `workflow/04_telemetry_drift_detection.html` | [View 04 Drift Detection](https://the-write-path-code.github.io/ch15-agentic-cicd/workflow/04_telemetry_drift_detection.html) | Dual-signal drift detection: OCC contention retry engine and retrieval similarity band |
| `workflow/05_redteam_security_pipeline.html` | [View 05 Red-Team](https://the-write-path-code.github.io/ch15-agentic-cicd/workflow/05_redteam_security_pipeline.html) | Automated red-team pipeline: L1, L2, L10, L7 security seam, benign controls, and fail-closed proof |
| `workflow/06_hitl_governance_ratchet.html` | [View 06 HITL Ratchet](https://the-write-path-code.github.io/ch15-agentic-cicd/workflow/06_hitl_governance_ratchet.html) | Human-in-the-loop loop: overrides, case generation, adversarial twins, and one-way promotion ratchet |

