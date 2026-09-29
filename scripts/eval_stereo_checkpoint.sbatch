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
if [[ "${CUPID_OFFICIAL_BASELINE:-0}" == 1 ]]; then
    weight_args=(--official-baseline)
else
    weight_args=(--checkpoint "${CUPID_EVAL_CHECKPOINT:-/public/home/ricky/RESULTS/STEREO_CUPID_2DE057A_FULL_A8/output/step_00000809.pt}"
      --checkpoint-sha256 "${CUPID_EVAL_CHECKPOINT_SHA256:-8d477ffe6cad8582d5474bc12c5c9a6493d9a775933dfcf22b43607fe54d8c5c}")
fi
eval_args=(--split "${CUPID_EVAL_SPLIT:-test}")
if [[ "${CUPID_RENDER_METRICS:-0}" == 1 ]]; then eval_args+=(--render-metrics); fi
if [[ -n "${CUPID_EVAL_SELECTION_SEED:-}" ]]; then eval_args+=(--selection-seed "$CUPID_EVAL_SELECTION_SEED"); fi
"$runtime/bin/python3" -u scripts/eval_stereo_checkpoint.py \
  --config "${CUPID_EVAL_CONFIG:-configs/stereo/train_stage1_full_gso_engineering_candidate.json}" \
  "${weight_args[@]}" "${eval_args[@]}" \
  --output "${CUPID_EVAL_OUTPUT:?}" --limit "${CUPID_EVAL_LIMIT:-3}"
