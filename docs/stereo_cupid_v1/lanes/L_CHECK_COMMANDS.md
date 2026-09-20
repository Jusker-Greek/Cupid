# L bounded checks for R and I

Status: commands prepared, NOT executed locally. Tests require Slurm compute.
R owns duplicate audit, fresh checkout/root/job and dispatch. No GPU is required
for these stdlib-only analytic fixtures. Preserve stdout/stderr and sacct terminal.
No optional scientific thresholds or real datasets are needed for this check.

After R has synchronized exact pushed L/I commit into a fresh checkout, and has
established the existing portable Python path from the accepted launcher:

```bash
# On allocated compute node (or R's bounded CPU sbatch script):
cd "$CUPID_PROJECT_DIR"
"$CUPID_PYTHON" scripts/stereo_evaluate_fixture.py
```

R may wrap with one CPU / 1G / 5 minutes on the established cpu partition;
first inspect `/opt/gridview/slurm/bin/squeue -u ricky` and avoid any active
STEREO_CUPID_L fixture duplicate. Do not independently submit from L/T/I.
Fixture uses TemporaryDirectory only for generated mock telemetry and removes
those temporary files; R retains the job log as the engineering receipt.

For real evaluation, an immutable expected-sample manifest is required:

```bash
"$CUPID_PYTHON" scripts/stereo_evaluate.py \
  --v1-manifest "$EXPECTED_SAMPLE_MANIFEST" --output "$FRESH_EVAL_RECEIPT"
```

For post-run W&B verification, use the actual run receipt's entity/project/id
and a fresh output path. Existing secure credentials are used by SDK; never
supply keys as command arguments or print secrets. Each invocation is one
readback attempt; transient failure records UNVERIFIED, returns 2, keeps logs.

```bash
"$CUPID_PYTHON" scripts/stereo_evaluate.py \
  --wandb-root "$RUN_ROOT/stereo_observability" \
  --run-path "$EXACT_WANDB_RUN_PATH" --output "$FRESH_READBACK_RECEIPT"
```

TensorBoard is fed via the existing writer and remains independently inspectable;
the old verify_cupid_tensorboard.py has the GL-specific N/A contract and must not
be used to declare this Stereo run accepted. The new W&B readback establishes
exact event transport; Controller separately adjudicates missing/N/A scientific
metrics and all S07 requirements. L never auto-promotes a stage.
