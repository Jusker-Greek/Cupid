#!/usr/bin/env bash
set -euo pipefail
export HDF5_USE_FILE_LOCKING=FALSE PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}" OPENBLAS_NUM_THREADS=1
cd "${REPO_ROOT:?}"
test "$(git rev-parse HEAD)" = "${EXPECTED_COMMIT:?}"
test -z "$(git status --porcelain)"
manifest=/public/home/ricky/RESULTS/STEREO_GSO_1K_D_CROSS_AUDIT_D7CA62E_A2/audit/pairs.jsonl
inventory=/public/home/ricky/RESULTS/STEREO_GSO_GEOMETRY_1K_468C042_A1/inventory/geometry_candidates.jsonl
warp=/public/home/ricky/RESULTS/STEREO_GSO_WARP_478DF73_A2/probe/receipt.json
projection=/public/home/ricky/RESULTS/STEREO_GSO_MESH_HOLDOUT_4D275F0_A1/holdout/receipt.json
objects=/public/home/ricky/RESULTS/STEREO_GSO_MESH_HOLDOUT_4D275F0_A1/holdout/objects.json
test "$(sha256sum "$manifest" | cut -d ' ' -f1)" = 0c6c6b9213554c39811323cca15733c19da1d9e848a3f0dd76ea079030e4b625
test "$(sha256sum "$inventory" | cut -d ' ' -f1)" = abf8e3bce87845b9cb0651e98e15a3a8cfa106e4eb7ce637d4c6750b1236ca92
test "$(sha256sum "$warp" | cut -d ' ' -f1)" = cbe03c99e250a5b650888b347b372e0006d20c1cc008e812101a25a78e40d112
test "$(sha256sum "$projection" | cut -d ' ' -f1)" = 66e9aea37892f5bb937b5070e43b4a8c671e718e10a247867a0aab09afa36732
test "$(sha256sum "$objects" | cut -d ' ' -f1)" = ccce06f5bed069c1f676e6ad6b7e385675cc91fbe8c84a5dfe8b8017d3da8220
runtime=/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12
export LD_LIBRARY_PATH="/public/home/ricky/lib:$runtime/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$REPO_ROOT:/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r2:/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1:${PYTHONPATH:-}"
"$runtime/bin/python3" -u scripts/stereo_gso_empirical_target_pilot.py \
  --manifest "$manifest" --root /public/home/ricky/DATASET/GSO_1K_200 \
  --asset-root /public/home/ricky/DATASET/Gazebo \
  --geometry-inventory "$inventory" --warp-receipt "$warp" \
  --projection-receipt "$projection" --projection-objects "$objects" \
  --voxelizer /public/home/ricky/CODE/TRELLIS/dataset_toolkits/voxelize.py \
  --output "${OUTPUT_ROOT:?}/pilot"
