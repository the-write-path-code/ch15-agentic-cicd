# Substitutions

Deviations from the brief, with one-line reasons. If a future change removes one, delete its row.

| Item | Deviation | Reason |
|---|---|---|
| `uv.lock` | Not committed yet. Run `uv lock` once on a networked machine, commit, and push. | The build agent that produced this repo has no network access, so it cannot resolve and pin the dependency graph. CI uses `uv sync --locked` exactly as specified and will fail at the sync step until the lockfile lands. |
| Corpus count | 18 documents, with `HR-2026-04` omitted. | The brief names 18 documents but lists ids that sum to 19 (HR-2026-01 through HR-2026-10, plus HR-2024-11, plus 8 SEC docs). One id had to give; the frontmatter id sequence stays clean. |
| Golden case count | Clean answerable cases are 30, not 36. | The brief's category counts (12 seeds + 36 + 5 + 4 + 5 + 4) sum to 66 against a stated total of 60. The special categories are kept intact and the clean answerable pool was scaled to land on exactly 60. |
| Trace claims field | `traces_v1.jsonl` and the candidate fixtures omit the per-claim array. | The brief's trace field list does not include claims, and claims are recomputed on replay, so the committed fixtures stay lean. |
| `astral-sh/setup-uv` | Pinned to `v8.1.0` rather than a moving `@v8` tag. | From v8 the action publishes immutable releases and the moving major tag no longer resolves reliably, so a full version is pinned. |
| `actions/checkout` | Pinned to `v7`. | Current stable major; v7 also hardens fork PR checkouts. |
| HITL adversarial twins | Written to `data/adversarial/adversarial_hitl.jsonl`, not appended to `adversarial_v1.jsonl`. | The red-team suite is pinned at exactly 39 malicious plus 39 controls to match SentinelAI's published 39-case design; live twins grow in their own file. |
| `regen-fixtures` workflow | Added beyond the brief. | The committed fixtures are deterministic functions of committed inputs, so regeneration runs on GitHub's runners and commits the byte-identical result; it also serves maintainers after corpus or prompt changes. |
| Opik trace call | `OpikStore.record` forwards events to `log_trace`. | The sandbox verification environment cannot install the real `opik` client, so the call mirrors the Chapter 4 `OpikTracer` pattern and is exercised only through the inactive-store contract tests. |
