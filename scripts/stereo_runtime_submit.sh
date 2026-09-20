#!/usr/bin/env bash
# Login-node control-plane only: serialize audits and submit one bounded job.
set -euo pipefail
: "${CUPID_PROJECT_DIR:?}"
: "${CUPID_EXPECTED_COMMIT:?}"
: "${CUPID_EXPECTED_TREE:?}"
: "${CUPID_RUNTIME_MODE:?contract, asset-audit, assemble or pilot}"
: "${CUPID_RUNTIME_EVIDENCE:?New absolute evidence root}"
[[ "$CUPID_RUNTIME_EVIDENCE" =~ ^/public/home/ricky/RESULTS/[A-Za-z0-9_-]+$ ]]
[[ "$(id -un)" == ricky && -d /public/home/ricky ]]
[[ -z "${SLURM_JOB_ID:-}" ]]
cd "$CUPID_PROJECT_DIR"
[[ "$(git rev-parse HEAD)" == "$CUPID_EXPECTED_COMMIT" ]]
[[ "$(git rev-parse 'HEAD^{tree}')" == "$CUPID_EXPECTED_TREE" ]]
git diff --quiet HEAD --
[[ -z "$(git ls-files --others --exclude-standard)" ]]
[[ ! -e "$CUPID_RUNTIME_EVIDENCE" && ! -e "$CUPID_RUNTIME_EVIDENCE.submission" ]]
exec 9>/public/home/ricky/RESULTS/.stereo_cupid_runtime_submit.lock
flock -n 9
mkdir "$CUPID_RUNTIME_EVIDENCE.submission"
slurm=/opt/gridview/slurm/bin
"$slurm/squeue" -u ricky -h -o '%i|%j|%T|%R' > "$CUPID_RUNTIME_EVIDENCE.submission/queue.txt"
cat "$CUPID_RUNTIME_EVIDENCE.submission/queue.txt"
# Match inference, future training and old transfer/weight jobs from this campaign.
if awk -F'|' '$2 ~ /^(stereo_cupid|cupid_local_upload|cupid_weights)/ {found=1} END {exit !found}' \
        "$CUPID_RUNTIME_EVIDENCE.submission/queue.txt"; then
    echo 'ACTIVE_CAMPAIGN_JOB_EXISTS: preserve audit, do not submit' >&2
    exit 1
fi
"$slurm/sinfo" -p cpu,gpu,gpux -o '%P %a %l %D %t %G' \
    > "$CUPID_RUNTIME_EVIDENCE.submission/capacity.txt"
"$slurm/sacct" -u ricky -S now-1day -X -n -o JobID,JobName%40,State,ExitCode \
    > "$CUPID_RUNTIME_EVIDENCE.submission/history.txt"
cat "$CUPID_RUNTIME_EVIDENCE.submission/capacity.txt"
args=(--parsable --nodes=1 --ntasks=1 --time=00:30:00 --export=ALL \
    --output="$CUPID_RUNTIME_EVIDENCE.submission/slurm_%j.out")
case "$CUPID_RUNTIME_MODE" in
    contract) args+=(--partition=cpu --cpus-per-task=1 --mem=1G --time=00:05:00 --job-name=stereo_cupid_contract) ;;
    asset-audit) args+=(--partition=cpu --cpus-per-task=2 --mem=4G --job-name=stereo_cupid_asset_audit) ;;
    assemble) args+=(--partition=cpu --cpus-per-task=2 --mem=4G --job-name=stereo_cupid_assemble) ;;
    pilot) args+=(--partition=gpu,gpux --cpus-per-task=8 --mem=64G --gres=gpu:1 --job-name=stereo_cupid_pilot) ;;
    *) echo 'Unsupported mode' >&2; exit 2 ;;
esac
job=$("$slurm/sbatch" "${args[@]}" scripts/stereo_runtime_job.sh)
printf '%s\n' "$job" | tee "$CUPID_RUNTIME_EVIDENCE.submission/job_id.txt"
"$slurm/scontrol" show job "${job%%;*}" > "$CUPID_RUNTIME_EVIDENCE.submission/job_readback.txt"
cat "$CUPID_RUNTIME_EVIDENCE.submission/job_readback.txt"
