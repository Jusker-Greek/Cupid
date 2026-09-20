#!/usr/bin/env bash
# Local Git + SSH only. No source-directory transport and no job submission.
set -euo pipefail
[[ $# == 4 ]] || { echo 'Usage: stereo_runtime_sync.sh BRANCH COMMIT TREE NEW_CLUSTER_CHECKOUT' >&2; exit 2; }
branch=$1 commit=$2 tree=$3 checkout=$4
[[ "$branch" =~ ^codex/[A-Za-z0-9._/-]+$ ]]
[[ "$commit" =~ ^[0-9a-f]{40}$ && "$tree" =~ ^[0-9a-f]{40}$ ]]
[[ "$checkout" =~ ^/public/home/ricky/CODE/[A-Za-z0-9_-]+$ ]]
repo=https://github.com/Jusker-Greek/Cupid.git
[[ -z "$(git status --porcelain)" ]]
[[ "$(git rev-parse HEAD)" == "$commit" ]]
[[ "$(git rev-parse 'HEAD^{tree}')" == "$tree" ]]
[[ "$(git ls-remote "$repo" "refs/heads/$branch" | awk '{print $1}')" == "$commit" ]]
# Fetch the exact pushed object back before accepting its tree identity.
git fetch --no-tags "$repo" "$commit"
[[ "$(git rev-parse 'FETCH_HEAD^{tree}')" == "$tree" ]]
ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 \
    -o ServerAliveInterval=15 -o ServerAliveCountMax=3 ricky@10.10.7.1 \
    bash -s -- "$branch" "$commit" "$tree" "$checkout" <<'REMOTE'
set -euo pipefail
branch=$1 commit=$2 tree=$3 checkout=$4
[[ ! -e "$checkout" && ! -e "$checkout.partial" ]]
# Preserve a failed partial clone. A successor needs a fresh identity.
git clone --no-checkout --single-branch --branch "$branch" \
    https://github.com/Jusker-Greek/Cupid.git "$checkout.partial"
git -C "$checkout.partial" checkout --detach "$commit"
[[ "$(git -C "$checkout.partial" rev-parse HEAD)" == "$commit" ]]
[[ "$(git -C "$checkout.partial" rev-parse 'HEAD^{tree}')" == "$tree" ]]
git -C "$checkout.partial" diff --quiet HEAD --
[[ -z "$(git -C "$checkout.partial" ls-files --others --exclude-standard)" ]]
mv "$checkout.partial" "$checkout"
printf 'SOURCE_SYNC=VERIFIED\nCOMMIT=%s\nTREE=%s\nCHECKOUT=%s\n' "$commit" "$tree" "$checkout"
REMOTE
