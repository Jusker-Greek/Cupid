#!/usr/bin/env bash
#SBATCH --job-name=cupid_gl_full
#SBATCH --partition=gpu
#SBATCH --ntasks-per-node=1
#SBATCH --output=/public/home/ricky/RESULTS/cupid_gl_full_%j.out

set -euo pipefail

CUPID_PROJECT_DIR="${CUPID_PROJECT_DIR:?CUPID_PROJECT_DIR is required}"
CUPID_OUTPUT_DIR="${CUPID_OUTPUT_DIR:?CUPID_OUTPUT_DIR is required}"
CUPID_EXPECTED_COMMIT="${CUPID_EXPECTED_COMMIT:?CUPID_EXPECTED_COMMIT is required}"
CUPID_GPUS_PER_NODE="${CUPID_GPUS_PER_NODE:?CUPID_GPUS_PER_NODE is required}"
CUPID_EXPECTED_WORLD_SIZE="${CUPID_EXPECTED_WORLD_SIZE:?CUPID_EXPECTED_WORLD_SIZE is required}"
CUPID_PYTHON="${CUPID_PYTHON:-/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12/bin/python3}"
CUPID_NVDIFFRAST_OVERLAY="${CUPID_NVDIFFRAST_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v17}"
CUPID_BASE_PYTHON_OVERLAY="${CUPID_BASE_PYTHON_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1}"
CUPID_NVIDIA_PYTHON_ROOT="${CUPID_NVIDIA_PYTHON_ROOT:-/public/home/ricky/.local/lib/python3.12/site-packages/nvidia}"
CUPID_PYTHON_OVERLAY="${CUPID_PYTHON_OVERLAY:-$CUPID_NVDIFFRAST_OVERLAY:$CUPID_BASE_PYTHON_OVERLAY}"
CUPID_DATA_DIR="${CUPID_DATA_DIR:-/data/group_gao/trellis/HSSD}"
CUPID_CONFIG="${CUPID_CONFIG:-configs/generation/slat_flow_img_dit_L_64l8p2_fp16-posecond-cluster.json}"
CUPID_LOAD_DIR="${CUPID_LOAD_DIR:-$CUPID_OUTPUT_DIR}"
CUPID_CKPT="${CUPID_CKPT:-latest}"
CUPID_MASTER_PORT="${CUPID_MASTER_PORT:-29517}"
CUPID_WANDB_PROJECT="${CUPID_WANDB_PROJECT:-cupid-reproduction}"
CUPID_WANDB_ENTITY="${CUPID_WANDB_ENTITY:-}"
CUPID_WANDB_NAME="${CUPID_WANDB_NAME:-cupid-gl-hssd-8xh200-1m-${SLURM_JOB_ID}}"
CUPID_WANDB_ID="${CUPID_WANDB_ID:-cupid-gl-full-${SLURM_JOB_ID}}"
CUPID_WANDB_GROUP="${CUPID_WANDB_GROUP:-CUPID_REPRO_GL_SMOKE_V1}"

test "$CUPID_GPUS_PER_NODE" -ge 1
test "$CUPID_EXPECTED_WORLD_SIZE" -eq "$((SLURM_NNODES * CUPID_GPUS_PER_NODE))"
test ! -e "$CUPID_OUTPUT_DIR"

cd "$CUPID_PROJECT_DIR"
actual_commit="$(git rev-parse HEAD)"
test "$actual_commit" = "$CUPID_EXPECTED_COMMIT"
test -z "$(git status --porcelain --untracked-files=all)"

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
export WANDB_MODE=online
export WANDB_DIR="$CUPID_OUTPUT_DIR/wandb"

master_addr="$(scontrol show hostnames "$SLURM_JOB_NODELIST" | head -n 1)"
export CUPID_PROJECT_DIR CUPID_OUTPUT_DIR CUPID_EXPECTED_COMMIT
export CUPID_GPUS_PER_NODE CUPID_EXPECTED_WORLD_SIZE CUPID_PYTHON
export CUPID_DATA_DIR CUPID_CONFIG CUPID_LOAD_DIR CUPID_CKPT CUPID_MASTER_PORT
export CUPID_WANDB_PROJECT CUPID_WANDB_ENTITY CUPID_WANDB_NAME CUPID_WANDB_ID CUPID_WANDB_GROUP
export master_addr

echo "HOSTS=$(scontrol show hostnames "$SLURM_JOB_NODELIST" | paste -sd, -)"
echo "COMMIT=$actual_commit"
echo "RUN_CLASS=FULL_SCIENTIFIC"
echo "EVIDENCE_ELIGIBILITY=PENDING_S09_REVIEW"
echo "NUM_NODES=$SLURM_NNODES"
echo "GPUS_PER_NODE=$CUPID_GPUS_PER_NODE"
echo "WORLD_SIZE=$CUPID_EXPECTED_WORLD_SIZE"
echo "OUTPUT_DIR=$CUPID_OUTPUT_DIR"
echo "LOAD_DIR=$CUPID_LOAD_DIR"
echo "WANDB_PROJECT=$CUPID_WANDB_PROJECT"
echo "WANDB_NAME=$CUPID_WANDB_NAME"
echo "WANDB_ID=$CUPID_WANDB_ID"

"$CUPID_PYTHON" - <<'PY'
import nvdiffrast.torch

print("CUPID_NVDIFFRAST_IMPORT_GATE=PASS")
PY

"$CUPID_PYTHON" - <<'PY'
import json
import os
from pathlib import Path

project_dir = Path(os.environ["CUPID_PROJECT_DIR"])
output_dir = Path(os.environ["CUPID_OUTPUT_DIR"])
with (project_dir / os.environ["CUPID_CONFIG"]).open() as config_file:
    config = json.load(config_file)
trainer = config["trainer"]["args"]
receipt = {
    "schema": "cupid_full_launch/v1",
    "status": "SUBMITTED",
    "run_class": "FULL_SCIENTIFIC",
    "evidence_eligibility": "PENDING_S09_REVIEW",
    "commit": os.environ["CUPID_EXPECTED_COMMIT"],
    "config": os.environ["CUPID_CONFIG"],
    "data_dir": os.environ["CUPID_DATA_DIR"],
    "output_dir": str(output_dir),
    "load_dir": os.environ["CUPID_LOAD_DIR"],
    "ckpt": os.environ["CUPID_CKPT"],
    "num_nodes": int(os.environ["SLURM_NNODES"]),
    "gpus_per_node": int(os.environ["CUPID_GPUS_PER_NODE"]),
    "world_size": int(os.environ["CUPID_EXPECTED_WORLD_SIZE"]),
    "max_steps": trainer["max_steps"],
    "batch_size_per_gpu": trainer["batch_size_per_gpu"],
    "global_batch_size": trainer["batch_size_per_gpu"]
    * int(os.environ["CUPID_EXPECTED_WORLD_SIZE"]),
    "batch_split": trainer["batch_split"],
    "optimizer": trainer["optimizer"],
    "lr_scheduler": trainer["lr_scheduler"],
    "ema_rate": trainer["ema_rate"],
    "fp16_mode": trainer["fp16_mode"],
    "log_interval": trainer["i_log"],
    "sample_interval": trainer["i_sample"],
    "checkpoint_interval": trainer["i_save"],
    "wandb_run": {
        "project": os.environ["CUPID_WANDB_PROJECT"],
        "entity": os.environ["CUPID_WANDB_ENTITY"] or None,
        "name": os.environ["CUPID_WANDB_NAME"],
        "id": os.environ["CUPID_WANDB_ID"],
        "mode": "online",
        "receipt": str(output_dir / "wandb_run.json"),
    },
    "tensorboard_dir": str(output_dir / "tb_logs"),
}
(output_dir / "full_launch_receipt.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n"
)
print("CUPID_FULL_LAUNCH=" + json.dumps(receipt, sort_keys=True), flush=True)
PY

srun --nodes="$SLURM_NNODES" --ntasks="$SLURM_NNODES" --ntasks-per-node=1 \
    bash -c '
        set -euo pipefail
        node_rank="$SLURM_NODEID"
        "$CUPID_PYTHON" -u "$CUPID_PROJECT_DIR/cupid_train.py" \
            --config "$CUPID_CONFIG" \
            --data_dir "$CUPID_DATA_DIR" \
            --output_dir "$CUPID_OUTPUT_DIR" \
            --load_dir "$CUPID_LOAD_DIR" \
            --ckpt "$CUPID_CKPT" \
            --auto_retry 0 \
            --num_nodes "$SLURM_NNODES" \
            --node_rank "$node_rank" \
            --num_gpus "$CUPID_GPUS_PER_NODE" \
            --master_addr "$master_addr" \
            --master_port "$CUPID_MASTER_PORT" \
            --wandb_project "$CUPID_WANDB_PROJECT" \
            --wandb_entity "$CUPID_WANDB_ENTITY" \
            --wandb_name "$CUPID_WANDB_NAME" \
            --wandb_id "$CUPID_WANDB_ID" \
            --wandb_group "$CUPID_WANDB_GROUP"
    '

echo "FULL_TERMINAL=COMPLETED"
