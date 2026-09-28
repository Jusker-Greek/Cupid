#!/usr/bin/env bash
set -euo pipefail
cd "${REPO_ROOT:?}"
test "$(git rev-parse HEAD)" = "${EXPECTED_COMMIT:?}"
test -z "$(git status --porcelain)"
export HDF5_USE_FILE_LOCKING=FALSE PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}" OPENBLAS_NUM_THREADS=1
runtime=/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12
export LD_LIBRARY_PATH="/public/home/ricky/lib:$runtime/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="/public/home/ricky/ENVIRONMENT/stereo_gso_open3d_cpu_0190_py312_a4:$REPO_ROOT:/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r2:/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1:${PYTHONPATH:-}"
"$runtime/bin/python3" -u scripts/stereo_gso_merged_adapter_preflight.py \
  --root "${OUTPUT_ROOT:?}" --data-root /public/home/ricky/DATASET/GSO_1K_200
