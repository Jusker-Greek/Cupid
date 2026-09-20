# CPU A1 exact execution plan, not executed

Controller released I source `4de419aa03e0307cc290c9a5d9c8f04e32018fc8`, tree
`53f68678bfbc1a2deb75fd6c910ff32632b11176`, branch
`codex/stereo-cupid-lane-i-integration`. Read `I_REVIEW_A1.md` at that commit.
00:40 strict-hostkey SSH still closed before banner. No checkout or JobID exists
for this plan. Newer I integration with runtime contract mode may replace this
source only after exact SHA/tree binding; never silently follow branch tip.

First executable command:

```sh
ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=12 \
  ricky@10.10.7.1 \
  '/opt/gridview/slurm/bin/squeue -u ricky -o "%.18i %.32j %.8T %.12M %.20R"'
```

After access, inspect squeue/sacct for old uploads and active campaign jobs;
do not submit duplicate work. Fetch the I commit with Git on the cluster to
new `/public/home/ricky/CODE/stereo_cupid_i_4de419a_r_cpu_a1` (preserve partials).
Verify exact commit/tree and clean tracked/untracked source. GitHub is the
source; no source copying or remote editing. If normal Git transport fails,
use only the approved incremental verified-bundle helper and a fresh attempt.

I A1 predates the new R contract job mode, so execute these **inside a bounded
1CPU/1GB/5min Slurm allocation**, with the existing portable Python and
v21r2/base overlays from `submit_stereo_cupid_pilot.sh`:

```sh
cd /public/home/ricky/CODE/stereo_cupid_i_4de419a_r_cpu_a1
test "$(git rev-parse HEAD)" = 4de419aa03e0307cc290c9a5d9c8f04e32018fc8
test "$(git rev-parse 'HEAD^{tree}')" = 53f68678bfbc1a2deb75fd6c910ff32632b11176
git diff --quiet HEAD --
test -z "$(git ls-files --others --exclude-standard)"
export CUPID_PYTHON=/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12/bin/python3
export LD_LIBRARY_PATH=/public/home/ricky/ENVIRONMENT/XFactor/portable_cpython_3_12_6_3003da95_a3/python3.12/lib:/public/home/ricky/lib:${LD_LIBRARY_PATH:-}
export PYTHONPATH="$PWD:/public/home/ricky/ENVIRONMENT/cupid_nvdiffrast_253ac4f_py312_v21r2:/public/home/ricky/ENVIRONMENT/cupid_trellis_py312_localcheck_b12f303_a29r1:${PYTHONPATH:-}"
export PYTHONDONTWRITEBYTECODE=1
mkdir /public/home/ricky/RESULTS/STEREO_CUPID_I_4DE419A_R_CPU_A1
"$CUPID_PYTHON" scripts/stereo_integration_check.py \
  --output /public/home/ricky/RESULTS/STEREO_CUPID_I_4DE419A_R_CPU_A1/source.json \
  source --require-lane D --require-lane L --require-lane R
"$CUPID_PYTHON" scripts/stereo_data_manifest.py \
  --config configs/stereo/data_gso_stage1_v1.json \
  --output /public/home/ricky/RESULTS/STEREO_CUPID_I_4DE419A_R_CPU_A1/raw_pair \
  --verify-content --hash-assets --max-pairs 1
```

The 11-case L evaluator fixture is not present in this A1 source. Run it only
after I binds integration containing L successor
`a8f275d9ae2b638f457881a8a274480fc0f1a8d8` with a fresh receipt identity.
R's subsequent `contract` launcher encapsulates this package; use that instead
of ad hoc shell once it is integrated. Source PASS/raw-pair inspection is
engineering only, not training-target readiness, full dataset validity, or
scientific result. Record Slurm job/terminal, stdout, JSON status and counts;
send first failure or success immediately to Controller and I.
