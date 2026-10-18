#!/usr/bin/env bash
# Diagnostic-only Slurm entry. Submission authority/duplicate audit stays external.
set -euo pipefail
: "${SLURM_JOB_ID:?}" "${SLURMD_NODENAME:?}"
: "${CUPID_PROJECT_DIR:?}" "${CUPID_EXPECTED_COMMIT:?}" "${CUPID_EXPECTED_TREE:?}"
: "${POSECROSS_AUDIT_OUTPUT:?}" "${POSECROSS_AUDIT_MODE:?}"
cd "$CUPID_PROJECT_DIR"
[[ "$(git rev-parse HEAD)" == "$CUPID_EXPECTED_COMMIT" ]]
[[ "$(git rev-parse 'HEAD^{tree}')" == "$CUPID_EXPECTED_TREE" ]]
[[ -z "$(git status --porcelain)" ]]
[[ ! -e "$POSECROSS_AUDIT_OUTPUT" ]]
runtime=/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12
export PYTHONDONTWRITEBYTECODE=1 HDF5_USE_FILE_LOCKING=FALSE
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 SPCONV_ALGO=native ATTN_BACKEND=xformers
export LD_LIBRARY_PATH="$runtime/lib:/public/home/ricky/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
for d in /public/home/ricky/.local/lib/python3.12/site-packages/nvidia/*/lib; do
    export LD_LIBRARY_PATH="$d:$LD_LIBRARY_PATH"
done
export PYTHONPATH="$PWD:/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r2:/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1:${PYTHONPATH:-}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
case "$POSECROSS_AUDIT_MODE" in
  components) exec "$runtime/bin/python3" -u scripts/posecross_component_audit.py --output "$POSECROSS_AUDIT_OUTPUT" ;;
  data) exec "$runtime/bin/python3" -u scripts/posecross_data_audit.py --config configs/stereo/train_stage1_full_gso_engineering_candidate.json --output "$POSECROSS_AUDIT_OUTPUT" ;;
  *) echo 'Unknown diagnostic mode' >&2; exit 2 ;;
esac
