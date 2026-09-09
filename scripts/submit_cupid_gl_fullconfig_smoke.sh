#!/usr/bin/env bash
#SBATCH --job-name=cupid_gl_fullcfg_smoke
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=200G
#SBATCH --time=01:00:00
#SBATCH --output=/public/home/ricky/RESULTS/cupid_gl_fullcfg_smoke_%j.out

set -euo pipefail

CUPID_PROJECT_DIR="${CUPID_PROJECT_DIR:?CUPID_PROJECT_DIR is required}"
CUPID_OUTPUT_DIR="${CUPID_OUTPUT_DIR:?CUPID_OUTPUT_DIR is required}"
CUPID_EXPECTED_COMMIT="${CUPID_EXPECTED_COMMIT:?CUPID_EXPECTED_COMMIT is required}"
CUPID_PYTHON="${CUPID_PYTHON:-/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12/bin/python3}"
CUPID_NVDIFFRAST_OVERLAY="${CUPID_NVDIFFRAST_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r1}"
CUPID_BASE_PYTHON_OVERLAY="${CUPID_BASE_PYTHON_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1}"
CUPID_NVIDIA_PYTHON_ROOT="${CUPID_NVIDIA_PYTHON_ROOT:-/public/home/ricky/.local/lib/python3.12/site-packages/nvidia}"
CUPID_PYTHON_OVERLAY="${CUPID_PYTHON_OVERLAY:-$CUPID_NVDIFFRAST_OVERLAY:$CUPID_BASE_PYTHON_OVERLAY}"
CUPID_NUM_GPUS="${CUPID_NUM_GPUS:-1}"
CUPID_MASTER_PORT="${CUPID_MASTER_PORT:-12345}"
CUPID_WANDB_PROJECT="${CUPID_WANDB_PROJECT:-cupid-reproduction}"
CUPID_WANDB_ENTITY="${CUPID_WANDB_ENTITY:-}"
CUPID_WANDB_NAME="${CUPID_WANDB_NAME:-cupid-gl-wandb-smoke-${SLURM_JOB_ID}}"
CUPID_WANDB_ID="${CUPID_WANDB_ID:-cupid-gl-wandb-smoke-${SLURM_JOB_ID}}"
CUPID_WANDB_GROUP="${CUPID_WANDB_GROUP:-CUPID_REPRO_GL_SMOKE_V1}"

test "$CUPID_NUM_GPUS" -ge 1

mkdir -p /tmp/ricky_lib "$CUPID_OUTPUT_DIR"
ln -sf /usr/lib/x86_64-linux-gnu/libffi.so.8 /tmp/ricky_lib/libffi.so.6
python_root="$(dirname "$(dirname "$CUPID_PYTHON")")"
test -f "$python_root/lib/libpython3.12.so.1.0"
nvidia_library_path=""
for library_dir in "$CUPID_NVIDIA_PYTHON_ROOT"/*/lib; do
    test -d "$library_dir" || continue
    nvidia_library_path="${nvidia_library_path:+$nvidia_library_path:}$library_dir"
done
test -n "$nvidia_library_path"
export LD_LIBRARY_PATH="$nvidia_library_path:$python_root/lib:/tmp/ricky_lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export TORCH_HOME="${TORCH_HOME:-/public/home/ricky/.cache/torch}"
export PYTHONPATH="$CUPID_PROJECT_DIR:$CUPID_PYTHON_OVERLAY:${PYTHONPATH:-}"
export ATTN_BACKEND="${ATTN_BACKEND:-xformers}"
source "$CUPID_PROJECT_DIR/scripts/lib/wandb_env.sh"
export WANDB_DIR="$CUPID_OUTPUT_DIR/wandb"

cd "$CUPID_PROJECT_DIR"
actual_commit="$(git rev-parse HEAD)"
test "$actual_commit" = "$CUPID_EXPECTED_COMMIT"
test -z "$(git status --porcelain)"

echo "HOST=$(hostname)"
echo "COMMIT=$actual_commit"
echo "PYTHON_OVERLAY=$CUPID_PYTHON_OVERLAY"
echo "NUM_GPUS=$CUPID_NUM_GPUS"
echo "RUN_CLASS=SMOKE_DEBUG"
echo "EVIDENCE_ELIGIBILITY=DEBUG_ONLY/NO_SCIENCE"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader

"$CUPID_PYTHON" - <<'PY'
import spconv
import tensorboard
import utils3d
import wandb
import xformers
import nvdiffrast.torch

print("CUPID_FULLCFG_IMPORT_GATE=PASS")
PY

"$CUPID_PYTHON" -u cupid_train.py \
    --config configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond-cluster.json \
    --data_dir /data/group_gao/trellis/HSSD \
    --output_dir "$CUPID_OUTPUT_DIR" \
    --ckpt none \
    --auto_retry 0 \
    --num_gpus "$CUPID_NUM_GPUS" \
    --master_port "$CUPID_MASTER_PORT" \
    --wandb_project "$CUPID_WANDB_PROJECT" \
    --wandb_entity "$CUPID_WANDB_ENTITY" \
    --wandb_name "$CUPID_WANDB_NAME" \
    --wandb_id "$CUPID_WANDB_ID" \
    --wandb_group "$CUPID_WANDB_GROUP" \
    --smoke_full_entry \
    --smoke_steps 1 \
    --smoke_max_attempts 16

"$CUPID_PYTHON" scripts/verify_cupid_wandb.py --output_dir "$CUPID_OUTPUT_DIR"
