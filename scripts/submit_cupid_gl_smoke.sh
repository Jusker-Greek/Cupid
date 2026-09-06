#!/usr/bin/env bash
#SBATCH --job-name=cupid_gl_smoke
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=120G
#SBATCH --time=01:00:00
#SBATCH --output=/public/home/ricky/RESULTS/cupid_gl_smoke_%j.out

set -euo pipefail

CUPID_PROJECT_DIR="${CUPID_PROJECT_DIR:-/public/home/ricky/CODE/Cupid}"
CUPID_OUTPUT_DIR="${CUPID_OUTPUT_DIR:-/public/home/ricky/RESULTS/CUPID_REPRO_GL_SMOKE_V1}"
CUPID_PYTHON="${CUPID_PYTHON:-/public/home/ricky/CODE/venv/bin/python}"

mkdir -p /tmp/ricky_lib "$CUPID_OUTPUT_DIR"
ln -sf /usr/lib/x86_64-linux-gnu/libffi.so.8 /tmp/ricky_lib/libffi.so.6
export LD_LIBRARY_PATH="/tmp/ricky_lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export http_proxy="${http_proxy:-http://hkuhpc.com:7999}"
export https_proxy="${https_proxy:-http://hkuhpc.com:7999}"
export TORCH_HOME="${TORCH_HOME:-/public/home/ricky/.cache/torch}"
export PYTHONPATH="$CUPID_PROJECT_DIR:${PYTHONPATH:-}"

cd "$CUPID_PROJECT_DIR"
echo "HOST=$(hostname)"
echo "COMMIT=$(git rev-parse HEAD)"
echo "PYTHON=$CUPID_PYTHON"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

"$CUPID_PYTHON" -u cupid_train.py \
    --config configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond-smoke.json \
    --data_dir /data/group_gao/trellis/HSSD \
    --output_dir "$CUPID_OUTPUT_DIR" \
    --ckpt none \
    --auto_retry 0 \
    --num_gpus 1 \
    --smoke_steps 1
