Chapter diagrams live in `workflow/` as standalone Mermaid files. Render them with any Mermaid toolchain (`mmdc -i workflow/eval-gate-15-1.mmd -o figure.png`) or paste them straight into your chapter tooling. `ARCHITECTURE.md` embeds three of them inline with commentary.

| File | Shows | Chapter section |
|---|---|---|
| `workflow/overview-day2-merge-gate.mmd` | The Day 2 loop end to end: pull request, the three blocking workflows, and the handoff to the Chapter 9 deploy pipeline. | 15 opening |
| `workflow/eval-gate-15-1.mmd` | The evaluation gate: golden set and corpus through the five layers to the merge decision. | 15.1 |
| `workflow/migration-15-2.mmd` | Model migration: candidate traces replayed against the committed baseline with tolerance bands, signature validation, and token budgets. | 15.2 |
| `workflow/telemetry-drift-15-3.mmd` | Live drift detection: the OCC retry signal and retrieval similarity band feeding the detectors and the Prometheus export. | 15.3 |
| `workflow/redteam-pipeline-15-4.mmd` | The red-team pipeline: Layers 1, 2, 10, and 7 in order, audit logging, and the fail-closed fault injection path. | 15.4 |
| `workflow/hitl-loop-15-5.mmd` | The HITL loop: overrides to PROVISIONAL cases, adversarial twins, the promotion ratchet, and the calibration freeze. | 15.5 |

All six diagrams use the same vocabulary as the code, so a reader can go from any figure to the module that implements it using BOOK_MAPPING.md.
