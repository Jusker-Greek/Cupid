#!/usr/bin/env bash
# Invoked by stereo_runtime_submit.sh on an allocated Slurm compute node.
set -euo pipefail
: "${SLURM_JOB_ID:?Slurm required}"
: "${SLURMD_NODENAME:?Compute node required}"
: "${CUPID_PROJECT_DIR:?}"
: "${CUPID_EXPECTED_COMMIT:?}"
: "${CUPID_EXPECTED_TREE:?}"
: "${CUPID_RUNTIME_MODE:?Runtime mode required}"
: "${CUPID_RUNTIME_EVIDENCE:?Fresh evidence directory required}"
CUPID_PYTHON="${CUPID_PYTHON:-/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12/bin/python3}"
export LD_LIBRARY_PATH="$(dirname "$(dirname "$CUPID_PYTHON")")/lib:/public/home/ricky/lib:${LD_LIBRARY_PATH:-}"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$CUPID_PROJECT_DIR:${CUPID_NVDIFFRAST_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r2}:${CUPID_BASE_PYTHON_OVERLAY:-/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1}:${PYTHONPATH:-}"
for library_dir in "${CUPID_NVIDIA_PYTHON_ROOT:-/public/home/ricky/.local/lib/python3.12/site-packages/nvidia}"/*/lib; do
    [[ -d "$library_dir" ]] || continue
    export LD_LIBRARY_PATH="$library_dir:$LD_LIBRARY_PATH"
done
if [[ -d /tmp/ricky_lib ]]; then export LD_LIBRARY_PATH="/tmp/ricky_lib:$LD_LIBRARY_PATH"; fi
export TORCH_HOME="${TORCH_HOME:-/public/home/ricky/.cache/torch}"
export ATTN_BACKEND="${ATTN_BACKEND:-xformers}"
export SPCONV_ALGO=native HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
cd "$CUPID_PROJECT_DIR"
[[ "$(git rev-parse HEAD)" == "$CUPID_EXPECTED_COMMIT" ]]
[[ "$(git rev-parse 'HEAD^{tree}')" == "$CUPID_EXPECTED_TREE" ]]
git diff --quiet HEAD --
[[ -z "$(git ls-files --others --exclude-standard)" ]]
mkdir "$CUPID_RUNTIME_EVIDENCE"
exec > >(tee "$CUPID_RUNTIME_EVIDENCE/runtime.log") 2>&1
finish() {
    result=$?
    trap - EXIT
    printf 'EXIT_CODE=%s\nJOB=%s\nCOMMIT=%s\nTREE=%s\nMODE=%s\n' \
        "$result" "$SLURM_JOB_ID" "$CUPID_EXPECTED_COMMIT" "$CUPID_EXPECTED_TREE" \
        "$CUPID_RUNTIME_MODE" > "$CUPID_RUNTIME_EVIDENCE/terminal.txt"
    exit "$result"
}
trap finish EXIT
printf 'JOB=%s\nNODE=%s\nCOMMIT=%s\nTREE=%s\nMODEL=%s\nMODE=%s\n' \
    "$SLURM_JOB_ID" "$SLURMD_NODENAME" "$CUPID_EXPECTED_COMMIT" "$CUPID_EXPECTED_TREE" \
    "${CUPID_MODEL_PATH:-NOT_USED}" "$CUPID_RUNTIME_MODE"
case "$CUPID_RUNTIME_MODE" in
    contract|data-contract)
        # I owns the checker; missing integration is an explicit failure.
        args=(--output "$CUPID_RUNTIME_EVIDENCE/source_contract.json" source
              --require-lane D --require-lane L --require-lane R)
        if [[ "${CUPID_REQUIRE_T:-0}" == 1 || "$CUPID_RUNTIME_MODE" == data-contract ]]; then
            args+=(--require-lane T)
        fi
        "$CUPID_PYTHON" scripts/stereo_integration_check.py "${args[@]}"
        for file in scripts/stereo_runtime_*.sh; do bash -n "$file"; done
        if [[ "$CUPID_RUNTIME_MODE" == data-contract ]]; then
            "$CUPID_PYTHON" scripts/stereo_data_contract_tests.py
            "$CUPID_PYTHON" scripts/stereo_evaluate_fixture.py
            "$CUPID_PYTHON" -m cupid.trainers.stereo_stage1_contract_tests
            "$CUPID_PYTHON" scripts/stereo_integration_contract_tests.py
            "$CUPID_PYTHON" scripts/stereo_data_manifest.py \
                --config configs/stereo/data_panda125_audit_v1.json \
                --output "$CUPID_RUNTIME_EVIDENCE/panda125_audit" \
                --verify-content --hash-assets
        else
            "$CUPID_PYTHON" scripts/stereo_data_manifest.py \
                --config configs/stereo/data_gso_stage1_v1.json \
                --output "$CUPID_RUNTIME_EVIDENCE/raw_pair_audit" \
                --verify-content --hash-assets --max-pairs 1
        fi
        if [[ "$CUPID_RUNTIME_MODE" == contract && "${CUPID_EVAL_FIXTURE:-0}" == 1 ]]; then
            "$CUPID_PYTHON" scripts/stereo_evaluate_fixture.py
        fi
        ;;
    asset-audit)
        : "${CUPID_ASSET_SOURCE_A:?}"
        : "${CUPID_ASSET_SOURCE_B:?}"
        "$CUPID_PYTHON" scripts/stereo_runtime_asset_audit.py \
            --root "$CUPID_ASSET_SOURCE_A" --root "$CUPID_ASSET_SOURCE_B" \
            --receipt "$CUPID_RUNTIME_EVIDENCE/asset_audit.json"
        ;;
    assemble)
        : "${CUPID_MODEL_PATH:?}"
        : "${CUPID_ASSET_SOURCE_A:?Stopped source root required}"
        : "${CUPID_ASSET_SOURCE_B:?Verified upload source root required}"
        "$CUPID_PYTHON" scripts/stereo_runtime_assets.py --output "$CUPID_MODEL_PATH" \
            --source "$CUPID_ASSET_SOURCE_A" --source "$CUPID_ASSET_SOURCE_B"
        ;;
    pilot)
        : "${CUPID_MODEL_PATH:?}"
        # Rehash on the compute node immediately before load; no receipt-only PASS.
        "$CUPID_PYTHON" scripts/stereo_runtime_assets.py --output "$CUPID_MODEL_PATH" --verify-only
        [[ "${CUPID_FULL_MESH:-}" == 1 ]]
        [[ -z "${CUPID_STEPS:-}" ]] # Freeze the official pipeline's 25-step settings.
        : "${CUPID_CAMERA_JSON:?Explicit frozen scene_unit camera required}"
        bash scripts/submit_stereo_cupid_pilot.sh
        ;;
    train-smoke|train-ddp)
        : "${CUPID_TRAIN_CONFIG:?T-owned BOUND_FOR_EXECUTION config required}"
        : "${CUPID_TRAIN_CONFIG_SHA256:?Exact frozen configuration hash required}"
        : "${CUPID_OUTPUT_DIR:?Fresh output required even for optimizer resume}"
        [[ "$CUPID_TRAIN_CONFIG_SHA256" =~ ^[0-9a-f]{64}$ ]]
        [[ "$(sha256sum "$CUPID_TRAIN_CONFIG" | awk '{print $1}')" == "$CUPID_TRAIN_CONFIG_SHA256" ]]
        [[ ! -e "$CUPID_OUTPUT_DIR" ]]
        ranks=1
        if [[ "$CUPID_RUNTIME_MODE" == train-ddp ]]; then ranks=2; fi
        printf 'TRAIN_CONFIG=%s\nTRAIN_CONFIG_SHA256=%s\nWORLD_SIZE=%s\nOUTPUT=%s\n' \
            "$CUPID_TRAIN_CONFIG" "$CUPID_TRAIN_CONFIG_SHA256" "$ranks" "$CUPID_OUTPUT_DIR"
        train_args=(scripts/train_stereo_stage1.py --config "$CUPID_TRAIN_CONFIG"
            --expected-commit "$CUPID_EXPECTED_COMMIT" --output-dir "$CUPID_OUTPUT_DIR")
        if [[ -n "${CUPID_RESUME_OPTIMIZER:-}" ]]; then
            [[ -f "$CUPID_RESUME_OPTIMIZER" ]]
            train_args+=(--resume-optimizer "$CUPID_RESUME_OPTIMIZER")
        fi
        if [[ -n "${CUPID_STOP_AFTER_UPDATES:-}" ]]; then
            [[ "$CUPID_STOP_AFTER_UPDATES" == 10 ]]
            train_args+=(--stop-after-updates "$CUPID_STOP_AFTER_UPDATES")
        fi
        "$CUPID_PYTHON" -m torch.distributed.run --standalone --nnodes=1 \
            --nproc-per-node="$ranks" "${train_args[@]}"
        ;;
    *) echo "Unsupported runtime mode: $CUPID_RUNTIME_MODE" >&2; exit 2 ;;
esac
