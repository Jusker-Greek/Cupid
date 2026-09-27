#!/usr/bin/env bash
set -euo pipefail
export HDF5_USE_FILE_LOCKING=FALSE
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export PYTHONDONTWRITEBYTECODE=1
cd "$REPO_ROOT"
test "$(git rev-parse HEAD)" = "${EXPECTED_COMMIT:?}"
test -z "$(git status --porcelain)"
runtime=/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12
export LD_LIBRARY_PATH="/public/home/ricky/lib:$runtime/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$REPO_ROOT:/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r2:/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1:${PYTHONPATH:-}"
printf 'CHECKOUT %s\n' "$(git rev-parse HEAD)"
printf 'TREE %s\n' "$(git rev-parse HEAD^{tree})"
printf 'NODE %s\n' "$(hostname)"
"$runtime/bin/python3" -u scripts/stereo_gso_1k_cross_audit.py \
  --config configs/stereo/data_gso_stage1_v1.json \
  --candidate-receipt /public/home/ricky/RESULTS/STEREO_GSO_1K_CANDIDATE_5D0F740_A1/receipt.json \
  --candidate-manifest /public/home/ricky/RESULTS/STEREO_GSO_1K_CANDIDATE_5D0F740_A1/pairs.jsonl \
  --output "$OUTPUT_ROOT/audit"
