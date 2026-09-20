# HANDOFF_L — Stereo logging and independent evaluation

2026-09-21; owner task `01a0bfa4-b891-78c0-8348-9e91b7e84e4e`;
controller `01a0ba51-e1eb-7012-8147-c2cf36ad66b8`.

Local worktree `/Users/ruikegu/.codex/worktrees/ddc3/Cupid`;
branch `codex/stereo-cupid-l-observability-v1`;
base `0c77ae9c6648b918c820f79dbe15f80235c17709`.
Training identity `STEREO_CUPID_STAGE1_TRAIN_V1` candidate;
frozen inference `STEREO_CUPID_V1_SHARED_SS` unchanged.

## Delivered

1. `b5264958493a5b1d712b88b73a64b5838e4a9654`, tree
   `d858d21ffafc35d87e4a2d81c01e40a18d1db82b`: logger/evaluator core and contract.
2. `a8f275d9ae2b638f457881a8a274480fc0f1a8d8`, tree
   `4aab15627b99b8d8022959d032f27ca69c6fc2d9`: CPU fixture, exact server readback,
   offline replay, rank0 eval_factory, evaluation CLI and R commands.
3. The commit containing this handoff: preserve aggregate NOT_APPLICABLE reasons,
   derived-number overflow checks and extended fixtures. Exact tip/tree is reported
   separately after GitHub push/fetch, avoiding a self-referential commit hash.

Cherry-pick these in order, or the complete `0c77ae9..codex/stereo-cupid-l-observability-v1`
range after exact GitHub fetch. Only lane-owned files change: new
`cupid/stereo_observability/`, `scripts/stereo_evaluate*.py`, `lanes/L_*`.

Core interfaces and payload examples: `../L_CALLBACK_CONTRACT.md`.
R commands: `../L_CHECK_COMMANDS.md`. Imports require no Torch/CUDA/numpy.
Existing CUPID TensorBoard writer and W&B run are passed in; no replacement
tracker, credentials or scientific loss. Raw local events fsync before sink calls.
All callback sink failures preserve local logs; network exception text is omitted.
Replay does not claim delivery, readback does not auto-promote S07.

## Evidence boundary

- Performed: source-level logic/interface review; `git diff --check`; local commits,
  GitHub push + full SHA ls-remote + fetch tree readback for the first two commits.
- Not performed here: Python import/compile/tests (local execution forbidden),
  Slurm CPU fixture, actual TensorBoard writes, W&B SDK/server calls, model
  inference/training, actual dataset GT score, S05/S06/S07 acceptance.
- R received the finite CPU command through Controller. No L Slurm/GPU job was
  submitted, no task/automation created, no central ledger edited.
- Expected input still depends on D proving canonical axes/origin/normalization,
  target frame, independent GT, and units. No proof means explicit NA/UNVERIFIED.

## Immediate next actions and owners

1. I cherry-picks L commits; T wires logger_factory and its actual callback fields.
   Use existing W&B/TensorBoard objects; total/components/LR/epoch and AMP belong
   to their explicit keys. T owns DDP reductions, allrank validation FM loss and
   barrier/error broadcast; L hook never runs a collective or model forward.
2. R runs `"$CUPID_PYTHON" scripts/stereo_evaluate_fixture.py` once in fresh
   synchronized checkout on a bounded CPU Slurm allocation, preserving job ID,
   commit/tree, stdout/stderr and terminal. If failure: return first traceback
   to L, which repairs locally/pushes; no unchanged repeat.
3. I supplies complete expected-sample records to callback evaluation or a V1
   manifest to scripts/stereo_evaluate.py. Missing result files count as failed;
   sample_id duplicates error instead of inflating counts. No arbitrary research
   accuracy threshold is imposed. Raw errors carry unit and coverage.
4. R/T finish existing tracker normally, then R runs exact W&B readback with a
   fresh output receipt. Offline/cache-only state remains S07 UNVERIFIED. Controller
   adjudicates applicability and actual observed training/eval/checkpoint evidence.

## Reflection

- Unverified: real SDK, Slurm and T integration behavior; static code is not a run.
- Likely blind spot: a generic shared canonical name does not establish common
  axes/origin/normalization; a valid callback cannot prove that data assertion.
- Failure mode: calling only the logger but not executing validation/evaluation
  would produce telemetry without scientific coverage; inspect event contents and
  per-metric denominators rather than the presence of a W&B URL.
