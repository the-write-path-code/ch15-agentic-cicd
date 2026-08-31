# Architecture

Three flows carry the chapter: the evaluation gate, the red-team pipeline, and the HITL promotion loop.

## Evaluation gate flow (15.1, builds on Chapter 4)

```mermaid
flowchart TD
    A[Golden set, 60 cases] --> B[BM25 retrieval over corpus]
    B --> C{Restricted documents?}
    C -- yes --> D[Drop for non-security role, report]
    C -- no --> E[Sufficiency: SUFFICIENT, PARTIAL, INSUFFICIENT, CONFLICTING]
    D --> E
    P[Versioned prompt] --> G[Mock generator or live model]
    E --> G
    G --> H[Heuristic scores: faithfulness, relevance, precision, recall]
    G --> I[Claim grounding: SUPPORTED, UNSUPPORTED, CONTRADICTED]
    H --> J[Policy gate cascade]
    I --> J
    E --> J
    J --> K{Merge gates}
    K -- frozen decision changed / faithfulness or grounding below bar / unsupported claim / recall below 0.90 --> L[Merge blocked]
    K -- clean --> M[Merge allowed, baseline compared, report posted to PR]
```

The gate compares against `baselines/metrics_baseline.json`, the committed record of the last approved run. `--update-baseline` rewrites it for review; the diff is reviewed like any other change.

## Red-team pipeline (15.4, builds on Chapter 14)

```mermaid
flowchart TD
    A[Adversarial suite, 39 cases + 39 controls] --> B[Layer 1: regex input validator]
    B -- direct injection or malformed input --> X1[Block, reason recorded]
    B --> C[Layer 2: rule-based semantic guard]
    C -- privilege escalation or override phrasing --> X2[Block, reason recorded]
    C --> D[Layer 10: agent identity: ceiling, sources, actions, signatures]
    D -- restricted source, claimed role above ceiling, bad tool call --> X3[Block, reason recorded]
    D --> E{Request includes retrieval?}
    E -- yes --> F[Layer 7: context isolator: classification filter, XML isolation wrap, active scan]
    F -- poisoned chunk or restricted doc for role --> X4[Block or quarantine, reason recorded]
    F --> G[Pass]
    E -- no --> G
    X1 --> H[Audit log, one JSONL record per case]
    X2 --> H
    X3 --> H
    X4 --> H
    G --> H
    T[Fault injection: layer7_scanner raises] --> F
    F -. any exception .-> Y[Fail closed: blocked, never passed]
```

With `--fault-inject layer7_scanner`, every retrieval-dependent case must block with a fail-closed reason and the run still exits 0. That is the Chapter 14 contract proven in CI, not asserted in a comment.

## HITL promotion loop (15.5)

```mermaid
flowchart TD
    A[Reviewer override record] --> B{Disposition}
    B -- ignore or escalate --> C[Recorded, no case written]
    B -- assert --> D[New PROVISIONAL golden case, origin hitl]
    B -- assert, security block --> E[Plus adversarial twin case]
    D --> F[Calibration: three profiles over full golden set, decision matrix with false pass and false block counts]
    G[Human review audit data] --> H{Promotion}
    F --> H
    H -- no audit entries --> I[Freeze refused: profile stays PROVISIONAL]
    H -- promote with reviewer and evidence --> J[Case flips to PRODUCTION-FROZEN, audit entry appended]
    J --> K[Regression on any frozen case is merge-blocking in eval-gate.yml]
    J -. demotion attempt .-> L[Refused: one-way ratchet]
```
