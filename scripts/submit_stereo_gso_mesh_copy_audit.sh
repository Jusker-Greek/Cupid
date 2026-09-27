#!/bin/bash
#SBATCH --job-name=stereo_gso_mesh_copy
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/public/home/ricky/RESULTS/stereo_gso_mesh_copy_%j.out
set -euo pipefail
: "${CUPID_PROJECT_DIR:?Set exact synced checkout}"
: "${CUPID_EXPECTED_COMMIT:?Set expected commit}"
: "${CUPID_OUTPUT_DIR:?Set fresh output directory}"
cd "$CUPID_PROJECT_DIR"
test "$(git rev-parse HEAD)" = "$CUPID_EXPECTED_COMMIT"
git diff --quiet --ignore-submodules=all HEAD --
test -z "$(git ls-files --others --exclude-standard)"
runtime=/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12
export PYTHONDONTWRITEBYTECODE=1
"$runtime/bin/python3" -u scripts/stereo_gso_mesh_copy_audit.py \
  --object-index "$CUPID_PROJECT_DIR/docs/stereo_cupid_v1/audit_20260927/STEREO_GSO_POPULATION_7E36546_A3/objects.jsonl" \
  --left-root /public/home/ricky/DATASET/Gazebo \
  --right-root /data/group_gao/trellis/GSO_mesh/gso_models \
  --output "$CUPID_OUTPUT_DIR"
