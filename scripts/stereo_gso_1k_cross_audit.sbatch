#!/usr/bin/env bash
set -euo pipefail
export HDF5_USE_FILE_LOCKING=FALSE
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
cd "$REPO_ROOT"
printf 'CHECKOUT %s\n' "$(git rev-parse HEAD)"
printf 'TREE %s\n' "$(git rev-parse HEAD^{tree})"
printf 'NODE %s\n' "$(hostname)"
python3 scripts/stereo_gso_1k_cross_audit.py \
  --config configs/stereo/data_gso_stage1_v1.json \
  --candidate-receipt /public/home/ricky/RESULTS/STEREO_GSO_1K_CANDIDATE_5D0F740_A1/receipt.json \
  --candidate-manifest /public/home/ricky/RESULTS/STEREO_GSO_1K_CANDIDATE_5D0F740_A1/pairs.jsonl \
  --output "$OUTPUT_ROOT/audit"
