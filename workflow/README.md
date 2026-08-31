Chapter diagrams live in `workflow/` as standalone Mermaid files. Render them with any Mermaid toolchain (`mmdc -i workflow/eval-gate-15-1.mmd -o figure.png`) or paste them straight into your chapter tooling. `ARCHITECTURE.md` embeds three of them inline with commentary.

| File | Shows | Chapter section |
|---|---|---|
| `workflow/overview-day2-merge-gate.mmd` | The Day 2 loop end to end: pull request, the three blocking workflows, merge, and the deploy pipeline handoff. | 15 opening |
| `workflow/eval-gate-15-1.mmd` | The evaluation gate: golden set to answer to merge decision. | 15.1 |
| `workflow/migration-15-2.mmd` | Model migration as a checklist of gates ending in promote or block. | 15.2 |
| `workflow/telemetry-drift-15-3.mmd` | Live drift detection: two signals, two detectors, one alert path. | 15.3 |
| `workflow/redteam-pipeline-15-4.mmd` | The red-team pipeline: four layers in order, audit logging, fail-closed path. | 15.4 |
| `workflow/hitl-loop-15-5.mmd` | The HITL loop: overrides to PROVISIONAL cases, the promotion ratchet, and what promotion enforces in CI. | 15.5 |

All six diagrams use the same vocabulary as the code, so a reader can go from any figure to the module that implements it using BOOK_MAPPING.md.
