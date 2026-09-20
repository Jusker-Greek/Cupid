#!/usr/bin/env bash
#SBATCH --job-name=stereo_cupid_weights
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=/public/home/ricky/RESULTS/stereo_cupid_weights_%j.out
set -euo pipefail
: "${SLURM_JOB_ID:?}"
: "${CUPID_PROJECT_DIR:?}"
: "${CUPID_EXPECTED_COMMIT:?}"
: "${CUPID_MODEL_PATH:?}"
cd "$CUPID_PROJECT_DIR"
test "$(git rev-parse HEAD)" = "$CUPID_EXPECTED_COMMIT"
git diff --quiet HEAD
export http_proxy="${CUPID_DOWNLOAD_PROXY:-http://hkuhpc.com:7999}"
export https_proxy="$http_proxy"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r2:/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1:${PYTHONPATH:-}"
runtime=/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12
export LD_LIBRARY_PATH="/public/home/ricky/lib:$runtime/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
"$runtime/bin/python3" -u scripts/download_cupid_weights.py --output "$CUPID_MODEL_PATH"
