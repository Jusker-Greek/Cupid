#!/usr/bin/env bash
set -euo pipefail
export HDF5_USE_FILE_LOCKING=FALSE PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}" OPENBLAS_NUM_THREADS=1
cd "${REPO_ROOT:?}"
test "$(git rev-parse HEAD)" = "${EXPECTED_COMMIT:?}"
test -z "$(git status --porcelain)"
runtime=/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12
export LD_LIBRARY_PATH="/public/home/ricky/lib:$runtime/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="/public/home/ricky/ENVIRONMENT/stereo_gso_open3d_cpu_0190_py312_a4:$REPO_ROOT:$REPO_ROOT/scripts:/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r2:/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1:${PYTHONPATH:-}"
printf -v shard_dir 'shard_%02d' "${SLURM_ARRAY_TASK_ID:?}"
"$runtime/bin/python3" -u scripts/stereo_gso_1k_increment_targets.py \
  --selection-root /public/home/ricky/RESULTS/STEREO_GSO_1K_INCREMENT_562B9D5_A1/selection \
  --geometry-inventory /public/home/ricky/RESULTS/STEREO_GSO_GEOMETRY_1K_468C042_A1/inventory/geometry_candidates.jsonl \
  --root /public/home/ricky/DATASET/GSO_1K_200 --asset-root /public/home/ricky/DATASET/Gazebo \
  --voxelizer /public/home/ricky/CODE/TRELLIS/dataset_toolkits/voxelize.py \
  --output "${OUTPUT_ROOT:?}/$shard_dir" \
  --shard-index "$SLURM_ARRAY_TASK_ID" --shard-count "${SHARD_COUNT:?}"
