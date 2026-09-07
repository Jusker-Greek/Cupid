#!/usr/bin/env bash
#SBATCH --job-name=cupid_s08_data_audit
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:15:00
#SBATCH --output=/public/home/ricky/RESULTS/cupid_s08_data_audit_%j.out

set -euo pipefail

CUPID_AUDIT_CHECKOUT="${CUPID_AUDIT_CHECKOUT:?CUPID_AUDIT_CHECKOUT is required}"
CUPID_AUDIT_OUTPUT_DIR="${CUPID_AUDIT_OUTPUT_DIR:?CUPID_AUDIT_OUTPUT_DIR is required}"
CUPID_AUDIT_EXPECTED_COMMIT="${CUPID_AUDIT_EXPECTED_COMMIT:?CUPID_AUDIT_EXPECTED_COMMIT is required}"
CUPID_PYTHON="${CUPID_PYTHON:-/usr/local/python3.12/bin/python3}"
CUPID_DATA_DIR="${CUPID_DATA_DIR:-/data/group_gao/trellis/HSSD}"
CUPID_CONFIG="${CUPID_CONFIG:-configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond-cluster.json}"
CUPID_REQUIRED_CHECKPOINTS="${CUPID_REQUIRED_CHECKPOINTS:-/data/haobin/huggingface/hub/models--microsoft--TRELLIS-image-large/snapshots/25e0d31ffbebe4b5a97464dd851910efc3002d96/ckpts/slat_enc_swin8_B_64l8_fp16:/data/haobin/huggingface/hub/models--microsoft--TRELLIS-image-large/snapshots/25e0d31ffbebe4b5a97464dd851910efc3002d96/ckpts/slat_dec_gs_swin8_B_64l8gs32_fp16:/data/haobin/huggingface/hub/models--microsoft--TRELLIS-image-large/snapshots/25e0d31ffbebe4b5a97464dd851910efc3002d96/ckpts/slat_flow_img_dit_L_64l8p2_fp16.safetensors}"

export CUPID_AUDIT_CHECKOUT CUPID_AUDIT_OUTPUT_DIR CUPID_AUDIT_EXPECTED_COMMIT
export CUPID_DATA_DIR CUPID_CONFIG CUPID_REQUIRED_CHECKPOINTS

cd "$CUPID_AUDIT_CHECKOUT"
actual_commit="$(git rev-parse HEAD)"
test "$actual_commit" = "$CUPID_AUDIT_EXPECTED_COMMIT"
test -z "$(git status --porcelain)"
test ! -e "$CUPID_AUDIT_OUTPUT_DIR"

echo "HOST=$(hostname)"
echo "COMMIT=$actual_commit"
echo "RUN_CLASS=PREFLIGHT_DEBUG"
echo "EVIDENCE_ELIGIBILITY=DEBUG_ONLY/NO_SCIENCE"

"$CUPID_PYTHON" scripts/audit_cupid_s08_data.py
