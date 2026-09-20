#!/usr/bin/env bash
# Invoked by stereo_runtime_submit.sh on an allocated Slurm compute node.
set -euo pipefail
: "${SLURM_JOB_ID:?Slurm required}"
: "${SLURMD_NODENAME:?Compute node required}"
: "${CUPID_PROJECT_DIR:?}"
: "${CUPID_EXPECTED_COMMIT:?}"
: "${CUPID_EXPECTED_TREE:?}"
: "${CUPID_RUNTIME_MODE:?assemble or pilot}"
: "${CUPID_MODEL_PATH:?}"
: "${CUPID_RUNTIME_EVIDENCE:?Fresh evidence directory required}"
CUPID_PYTHON="${CUPID_PYTHON:-/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12/bin/python3}"
export LD_LIBRARY_PATH="$(dirname "$(dirname "$CUPID_PYTHON")")/lib:/public/home/ricky/lib:${LD_LIBRARY_PATH:-}"
export PYTHONDONTWRITEBYTECODE=1
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
    "$CUPID_MODEL_PATH" "$CUPID_RUNTIME_MODE"
case "$CUPID_RUNTIME_MODE" in
    assemble)
        : "${CUPID_ASSET_SOURCE_A:?Stopped source root required}"
        : "${CUPID_ASSET_SOURCE_B:?Verified upload source root required}"
        "$CUPID_PYTHON" scripts/stereo_runtime_assets.py --output "$CUPID_MODEL_PATH" \
            --source "$CUPID_ASSET_SOURCE_A" --source "$CUPID_ASSET_SOURCE_B"
        ;;
    pilot)
        # Rehash on the compute node immediately before load; no receipt-only PASS.
        "$CUPID_PYTHON" scripts/stereo_runtime_assets.py --output "$CUPID_MODEL_PATH" --verify-only
        [[ "${CUPID_FULL_MESH:-}" == 1 ]]
        : "${CUPID_CAMERA_JSON:?Explicit frozen scene_unit camera required}"
        bash scripts/submit_stereo_cupid_pilot.sh
        ;;
    *) echo "Unsupported runtime mode: $CUPID_RUNTIME_MODE" >&2; exit 2 ;;
esac
