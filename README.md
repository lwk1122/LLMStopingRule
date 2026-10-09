# Stopping Rules in LLM Code Repair

Core code and compact analysis data for **Stopping Rules in LLM Code Repair:
Editing Failures, Token Savings, and Missed Repairs**.

This repository studies two decisions: **when to stop generating code** and
**which generated version to return**. It replays these decisions on the same
recorded repair runs. Independent test outcomes are used only for evaluation,
never to make the stopping or selection decision.

[中文说明](README.zh-CN.md) · [Data definitions](data/README.md) ·
[Source provenance](SOURCE_MAP.md) · [Licensing](LICENSING.md)

## Quick start

Use **Python 3.10 or newer**. The core analysis and tests use only the standard
library. No installation, model API, LM Studio, Docker, or network access is
required.

```sh
python3 reproduce.py
python3 -m unittest discover -s tests -v
```

`reproduce.py` verifies the analysis files against the manifest, recomputes the analysis, and checks
it against frozen manuscript results. Eight complete analysis outputs must match
the archived output hashes. The script also checks all 16 Table 2 rows and the
28 versions and 11 stopping/output decisions in Figure 4. Outputs go to `results/`.
Run without Python's `-O` flag because verification uses assertions.

## What is included

| File or directory | Purpose |
|---|---|
| `analyze.py` | Budget replay, earliest/latest score ties, loss decomposition, joint missing-outcome bounds, and descriptive tie intervals |
| `reproduce.py` | One-command verification and manuscript table/trajectory exports |
| `editing/exact.py` | Exact replacements, editable-region checks, atomic application, tool schema, and original system prompt |
| `editing/matching.py` | Exact matching with the study's pinned Aider matching fallback |
| `editing/vendor/` | Unmodified upstream matching source and its Apache-2.0 license |
| `data/versions.csv` | 912 recorded version observations, including failures and incomplete evaluations |
| `data/provenance.json` | Input digest and source-relative hashes checked during export |
| `reference/` | Frozen expected results and hashes, separate from generated outputs |
| `tests/` | Synthetic checks for stopping, selection, unknown outcomes, and editor behavior |

The matching adapter is a component used inside the study's restricted editing
interface. It is not the complete Aider agent.

## Study sets

| Dataset key | Tasks | Recorded runs | Maximum revisions |
|---|---:|---:|---:|
| `Round9` (primary) | 18 | 54 | 3 |
| `Round7b` (historical) | 24 | 72 | 3 |
| `exact` (new, exact matching) | 9 | 27 | 6 |
| `aider_match` (new, matching component) | same 9 | 27 | 6 |
| `Extension` | 6 previously observed | 10 selected continuations | 6 |

Three runs share each task and configuration. The two new configurations share
the same tasks. The extension adds 30 calls at revisions 4--6; its earlier
versions come from the primary set. Those prefixes are reused for replay, not
counted as new observations or independent tasks.

## Reproduced outputs

| Manuscript content | Output under `results/` |
|---|---|
| Table 2: simple controls and stopping variants | `table2_controls.csv` |
| Table 3: new-task costs and successes | `table3_fresh.csv` |
| Table 4: generation and selection losses | `table4_losses.csv` |
| Table 5: budgets 0--6 on fixed new tasks | `table5_budgets.csv` |
| Figure 4: complete example trajectories | `figure4_versions.csv`, `figure4_decisions.csv` |
| Cost/success coordinates for Figures 2--3 | `budget_summary.csv`, `table2_controls.csv` |
| Every stopping and output decision | `policy_outcomes.csv` (8,568 rows) |
| Gains and losses within paired runs | `paired_changes.csv` |
| Loss counts and consistent unknown-outcome bounds | `loss_summary.csv` |
| Original labels and audit classifications | `outcome_audit.csv`, `audit_summary.json` |
| New-task descriptive tie intervals | `tie_task_effects.csv`, `tie_intervals.csv` |
| Verification summary | `verification.json` |

The figure exports contain the numerical data and decisions, not rendered PDF
figures. Table exports keep unrounded means; the manuscript rounds displayed
token means to integers.

## Core interpretation

For each run, the analysis counts whether a passing version exists anywhere in
the recorded budget, exists by the stopping point, and is returned. The first
minus the second is a repair missed by stopping; the second minus the third is
a repair already available but missed by selection. Each run contributes at
most once to each count. Different rules are alternatives on the same records;
their losses must not be added together.

The full record is an offline reference within the observed budget. It does not
give the best possible result beyond that budget. Repeated occurrences of the
same unknown task/patch outcome receive a consistent assignment in the bounds.
These are sensitivity bounds, not confidence intervals. The new-task tie
intervals are descriptive task bootstraps within the observed projects.

## Reuse the code

The reusable functions are `analyze.decision`, `analyze.diagnostics`, and
`analyze.loss_bounds`. To recalculate after changing analysis code, use
`python3 analyze.py`; `reproduce.py` intentionally rejects changes to the release
manifest and differences from the frozen manuscript results.

The editor components can be imported independently:

```python
from editing.exact import apply_edits, source

parts = [{"editable": True, "text": "value = 1\n"}]
operation = {
    "action": "edit",
    "replacements": [{"old_text": "value = 1", "new_text": "value = 2"}],
}
updated = apply_edits(parts, operation)
assert source(updated) == "value = 2\n"
```

The editor checks Python syntax without executing the supplied code. It leaves
the input state unchanged if an operation raises an error. The orchestration
layer in the original experiment retained that state and passed the error to
the next model request.

## Scope and full replication

This small release reproduces the **core numerical analysis from normalized
observations**. Their raw patch, usage, and grading-log hashes were checked at
export; the hashes are recorded in `data/provenance.json`. The raw files are not
bundled here, so running this package does not repeat that raw-log audit.

The full replication package separately contains prompts, generated patches,
original grading logs, admission controls, execution scripts, historical
sign-flip/Holm analyses, random-stopping experiments, and environment records.
Those materials and any public archive link must be supplied separately. This
release neither reruns the model nor executes benchmark tests and does not
reconstruct the original Docker environments.

## Citation and release status

The associated manuscript is by Li Wenkai and Li Yibing. Cite its title above;
add the publication/preprint identifier when available. No DOI or public archive
URL is claimed in this export.

README files and Git configuration are outside the analysis manifest, so the
maintainer can add repository/publication links and merge Git settings without
changing the frozen scientific inputs.

Before publishing, apply the destination repository's intended license to
author-owned files, retain the third-party license, and add the full-materials
link when available. See `LICENSING.md`.
