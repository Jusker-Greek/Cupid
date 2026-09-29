#!/usr/bin/env bash
#SBATCH --partition=gpu,gpux
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=00:40:00
set -euo pipefail
cd "${CUPID_PROJECT_DIR:?}"
test "$(git rev-parse HEAD)" = "${CUPID_EXPECTED_COMMIT:?}"
git diff --quiet HEAD
export PYTHONDONTWRITEBYTECODE=1 HDF5_USE_FILE_LOCKING=FALSE
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 SPCONV_ALGO=native ATTN_BACKEND=xformers
runtime=/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12
export LD_LIBRARY_PATH="$runtime/lib:/public/home/ricky/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
for d in /public/home/ricky/.local/lib/python3.12/site-packages/nvidia/*/lib; do
    export LD_LIBRARY_PATH="$d:$LD_LIBRARY_PATH"
done
export PYTHONPATH="$PWD:/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r2:/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1:${PYTHONPATH:-}"
export OMP_NUM_THREADS=8
export http_proxy=http://hkuhpc.com:7999 https_proxy=http://hkuhpc.com:7999
"$runtime/bin/python3" -u scripts/eval_stereo_paper_metrics.py --output "${CUPID_EVAL_OUTPUT:?}" --limit "${CUPID_EVAL_LIMIT:-3}" --suite "${CUPID_EVAL_SUITE:-paper}"
