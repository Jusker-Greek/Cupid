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
CUPID_PYTHON="${CUPID_PYTHON:-/usr/local/python3.12/bin/python3}"
CUPID_PYTHON_OVERLAY="${CUPID_PYTHON_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_trellis_py312}"
CUPID_DINOV2_COMMIT="${CUPID_DINOV2_COMMIT:-7764ea0f912e53c92e82eb78a2a1631e92725fc8}"
CUPID_DINOV2_CHECKPOINT_SIZE="${CUPID_DINOV2_CHECKPOINT_SIZE:-1217607321}"
CUPID_SLAT_ENCODER="/data/haobin/huggingface/hub/models--microsoft--TRELLIS-image-large/snapshots/25e0d31ffbebe4b5a97464dd851910efc3002d96/ckpts/slat_enc_swin8_B_64l8_fp16"
CUPID_SLAT_ENCODER_CONFIG_SHA256="${CUPID_SLAT_ENCODER_CONFIG_SHA256:-7b7e2bd3e831bdd5a6129cea36424a47ad73c1b9ad109d1de54e0f14af4d28a2}"
CUPID_SLAT_ENCODER_WEIGHTS_SHA256="${CUPID_SLAT_ENCODER_WEIGHTS_SHA256:-21dceac6bee917ab6458ff52c9757ba89a779d03031c7bd17f9e7f0103bfd436}"

mkdir -p /tmp/ricky_lib "$CUPID_OUTPUT_DIR"
ln -sf /usr/lib/x86_64-linux-gnu/libffi.so.8 /tmp/ricky_lib/libffi.so.6
export LD_LIBRARY_PATH="/tmp/ricky_lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export http_proxy="${http_proxy:-http://hkuhpc.com:7999}"
export https_proxy="${https_proxy:-http://hkuhpc.com:7999}"
export HTTP_PROXY="$http_proxy"
export HTTPS_PROXY="$https_proxy"
export no_proxy="${CUPID_NO_PROXY:-localhost,127.0.0.1,codeload.github.com,dl.fbaipublicfiles.com}"
export NO_PROXY="$no_proxy"
export TORCH_HOME="${TORCH_HOME:-/public/home/ricky/.cache/torch}"
export CUPID_DINOV2_REPO="facebookresearch/dinov2:$CUPID_DINOV2_COMMIT"
export PYTHONPATH="$CUPID_PROJECT_DIR:$CUPID_PYTHON_OVERLAY:${PYTHONPATH:-}"
export ATTN_BACKEND="${ATTN_BACKEND:-xformers}"

test -f "$TORCH_HOME/hub/facebookresearch_dinov2_$CUPID_DINOV2_COMMIT/hubconf.py"
test "$(stat -c '%s' "$TORCH_HOME/hub/checkpoints/dinov2_vitl14_reg4_pretrain.pth")" = "$CUPID_DINOV2_CHECKPOINT_SIZE"
test "$(sha256sum "$CUPID_SLAT_ENCODER.json" | awk '{print $1}')" = "$CUPID_SLAT_ENCODER_CONFIG_SHA256"
test "$(sha256sum "$CUPID_SLAT_ENCODER.safetensors" | awk '{print $1}')" = "$CUPID_SLAT_ENCODER_WEIGHTS_SHA256"

cd "$CUPID_PROJECT_DIR"
if git_commit="$(git rev-parse HEAD 2>/dev/null)"; then
    :
elif [[ -n "${CUPID_COMMIT:-}" ]]; then
    git_commit="$CUPID_COMMIT"
else
    echo "CUPID_COMMIT is required when the checkout has no .git directory" >&2
    exit 2
fi
echo "HOST=$(hostname)"
echo "COMMIT=$git_commit"
echo "PYTHON=$CUPID_PYTHON"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
"$CUPID_PYTHON" -c "import orjson, spconv, tensorboard, utils3d, xformers"

"$CUPID_PYTHON" -u cupid_train.py \
    --config configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond-smoke.json \
    --data_dir /data/group_gao/trellis/HSSD \
    --output_dir "$CUPID_OUTPUT_DIR" \
    --ckpt none \
    --auto_retry 0 \
    --num_gpus 1 \
    --smoke_steps 1
