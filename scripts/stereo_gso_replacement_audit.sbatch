#!/usr/bin/env bash
set -euo pipefail
export HDF5_USE_FILE_LOCKING=FALSE PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
cd "${REPO_ROOT:?}"
test "$(git rev-parse HEAD)" = "${EXPECTED_COMMIT:?}"
test -z "$(git status --porcelain)"
runtime=/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12
export LD_LIBRARY_PATH="/public/home/ricky/lib:$runtime/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$REPO_ROOT:$REPO_ROOT/scripts:/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r2:/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1:${PYTHONPATH:-}"
"$runtime/bin/python3" scripts/stereo_data_contract_tests.py
"$runtime/bin/python3" -u scripts/stereo_gso_replacement_audit.py \
  --manifest /public/home/ricky/RESULTS/STEREO_GSO_1K_D_CROSS_AUDIT_D7CA62E_A2/audit/pairs.jsonl \
  --allpair-objects /public/home/ricky/RESULTS/STEREO_GSO_ALLPAIR_PROJECTION_18789F9_A1/allpair/objects.json \
  --allpair-receipt /public/home/ricky/RESULTS/STEREO_GSO_ALLPAIR_PROJECTION_18789F9_A1/allpair/receipt.json \
  --root /public/home/ricky/DATASET/GSO_1K_200 --asset-root /public/home/ricky/DATASET/Gazebo \
  --output "${OUTPUT_ROOT:?}/audit" --max-attempts-per-object 50
