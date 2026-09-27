#!/bin/bash
#SBATCH --job-name=stereo_gso_population
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=/public/home/ricky/RESULTS/stereo_gso_population_%j.out
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
export PYTHONPATH="$CUPID_PROJECT_DIR:/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r2:/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1:${PYTHONPATH:-}"
"$runtime/bin/python3" -u scripts/stereo_gso_population_audit.py \
  --root /public/home/ricky/DATASET/GSO_1K_200 \
  --mesh-root /public/home/ricky/DATASET/Gazebo \
  --output "$CUPID_OUTPUT_DIR" \
  --sample-objects 64
