#!/usr/bin/env bash
set -euo pipefail
cd "${REPO_ROOT:?}"
test "$(git rev-parse HEAD)" = "${EXPECTED_COMMIT:?}"
test -z "$(git status --porcelain)"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1
runtime=/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12
export LD_LIBRARY_PATH="/public/home/ricky/lib:$runtime/lib:/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$REPO_ROOT:/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r2:/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1:${PYTHONPATH:-}"
"$runtime/bin/python3" -u scripts/stereo_gso_prepare_1k_increment.py \
  --original-manifest /public/home/ricky/RESULTS/STEREO_GSO_1K_D_CROSS_AUDIT_D7CA62E_A2/audit/pairs.jsonl \
  --base-manifest /public/home/ricky/RESULTS/STEREO_GSO_ELIGIBLE_TARGETS_AC79F9F_A1/merged_manifest.jsonl \
  --allpair-objects /public/home/ricky/RESULTS/STEREO_GSO_ALLPAIR_PROJECTION_18789F9_A1/allpair/objects.json \
  --allpair-receipt /public/home/ricky/RESULTS/STEREO_GSO_ALLPAIR_PROJECTION_18789F9_A1/allpair/receipt.json \
  --replacement-manifest /public/home/ricky/RESULTS/STEREO_GSO_REPLACEMENTS_AEFF5D0_A1/audit/replacement_manifest.jsonl \
  --replacement-map /public/home/ricky/RESULTS/STEREO_GSO_REPLACEMENTS_AEFF5D0_A1/audit/replacement_map.jsonl \
  --replacement-receipt /public/home/ricky/RESULTS/STEREO_GSO_REPLACEMENTS_AEFF5D0_A1/audit/receipt.json \
  --output "${OUTPUT_ROOT:?}/selection"
