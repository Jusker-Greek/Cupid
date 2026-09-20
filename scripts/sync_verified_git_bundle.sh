#!/usr/bin/env bash
set -euo pipefail

readonly HARD_MAX_BUNDLE_BYTES=104857600

usage() {
  cat <<'EOF'
Create and optionally transfer a verified incremental Git bundle.

Required local arguments:
  --work-tree PATH
  --branch NAME
  --expected FULL_SHA
  --base FULL_SHA

Optional local arguments:
  --git-dir PATH            Explicit worktree Git directory.
  --max-bytes N             May lower, but not exceed, 104857600.
  --prepare-only DIR        Create verified bundle and manifest locally only.

Required transfer arguments unless --prepare-only is used:
  --remote-host USER@HOST
  --remote-base-checkout PATH
  --remote-mirror PATH
  --remote-checkout PATH
  --remote-staging-root PATH

This helper never edits remote source files and never invokes sbatch.
Every remote destination must be new and absent.
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

validate_full_sha() {
  [[ "$1" =~ ^[0-9a-f]{40}$ ]] || die "$2 must be a full 40-character lowercase SHA."
}

validate_remote_path() {
  local value="$1"
  local label="$2"
  [[ "$value" =~ ^/[A-Za-z0-9._/-]+$ ]] || die "$label must be an absolute path without spaces or shell metacharacters."
  [[ "/$value/" != *"/../"* ]] || die "$label must not contain '..'."
}

work_tree=""
git_dir=""
branch=""
expected=""
base=""
max_bytes="${HARD_MAX_BUNDLE_BYTES}"
prepare_only=""
remote_host=""
remote_base_checkout=""
remote_mirror=""
remote_checkout=""
remote_staging_root=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-tree) work_tree="${2:?}"; shift 2 ;;
    --git-dir) git_dir="${2:?}"; shift 2 ;;
    --branch) branch="${2:?}"; shift 2 ;;
    --expected) expected="${2:?}"; shift 2 ;;
    --base) base="${2:?}"; shift 2 ;;
    --max-bytes) max_bytes="${2:?}"; shift 2 ;;
    --prepare-only) prepare_only="${2:?}"; shift 2 ;;
    --remote-host) remote_host="${2:?}"; shift 2 ;;
    --remote-base-checkout) remote_base_checkout="${2:?}"; shift 2 ;;
    --remote-mirror) remote_mirror="${2:?}"; shift 2 ;;
    --remote-checkout) remote_checkout="${2:?}"; shift 2 ;;
    --remote-staging-root) remote_staging_root="${2:?}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

[[ -n "$work_tree" && -n "$branch" && -n "$expected" && -n "$base" ]] || {
  usage >&2
  exit 2
}
[[ "$branch" =~ ^[A-Za-z0-9._/-]+$ ]] || die "branch contains unsupported characters."
validate_full_sha "$expected" "expected"
validate_full_sha "$base" "base"
[[ "$expected" != "$base" ]] || die "expected and base must differ for an incremental bundle."
[[ "$max_bytes" =~ ^[0-9]+$ ]] || die "max-bytes must be a positive integer."
(( max_bytes > 0 && max_bytes <= HARD_MAX_BUNDLE_BYTES )) || die "max-bytes must be between 1 and ${HARD_MAX_BUNDLE_BYTES}."

if [[ -z "$prepare_only" ]]; then
  [[ -n "$remote_host" && -n "$remote_base_checkout" && -n "$remote_mirror" && -n "$remote_checkout" && -n "$remote_staging_root" ]] || {
    usage >&2
    exit 2
  }
  [[ "$remote_host" =~ ^[A-Za-z0-9._@:-]+$ ]] || die "remote-host contains unsupported characters."
  validate_remote_path "$remote_base_checkout" "remote-base-checkout"
  validate_remote_path "$remote_mirror" "remote-mirror"
  validate_remote_path "$remote_checkout" "remote-checkout"
  validate_remote_path "$remote_staging_root" "remote-staging-root"
  [[ "$remote_base_checkout" != "$remote_mirror" ]] || die "remote base checkout and mirror must differ."
  [[ "$remote_base_checkout" != "$remote_checkout" ]] || die "remote base and target checkouts must differ."
  [[ "$remote_mirror" != "$remote_checkout" ]] || die "remote mirror and checkout must differ."
fi

GIT=()
if [[ -n "$git_dir" ]]; then
  GIT=(git --git-dir="$git_dir" --work-tree="$work_tree")
else
  GIT=(git -C "$work_tree")
fi

temp_dir=""
source_ref=""
control_path=""
master_open=0
child_transport_opts=()

cleanup() {
  if [[ -n "$source_ref" ]]; then
    "${GIT[@]}" update-ref -d "$source_ref" >/dev/null 2>&1 || true
  fi
  if (( master_open == 1 )); then
    ssh "${child_transport_opts[@]}" -O exit "$remote_host" >/dev/null 2>&1 || true
  fi
  [[ -z "$control_path" ]] || rm -f "$control_path"
  [[ -z "$temp_dir" ]] || rm -rf "$temp_dir"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

[[ -d "$work_tree" ]] || die "work-tree does not exist: $work_tree"
"${GIT[@]}" rev-parse --is-inside-work-tree >/dev/null
[[ -z "$("${GIT[@]}" status --porcelain --untracked-files=normal)" ]] || die "local worktree is not clean."
"${GIT[@]}" cat-file -e "${expected}^{commit}" || die "expected commit is not present locally."
"${GIT[@]}" cat-file -e "${base}^{commit}" || die "base commit is not present locally."
"${GIT[@]}" merge-base --is-ancestor "$base" "$expected" || die "base is not an ancestor of expected."

origin_url="$("${GIT[@]}" remote get-url origin)"
[[ "$origin_url" =~ ^https://github\.com/[A-Za-z0-9._/-]+$ ]] || die "origin must be a credential-free GitHub HTTPS URL."
remote_line="$("${GIT[@]}" ls-remote --exit-code origin "refs/heads/${branch}")" || die "GitHub branch readback failed."
remote_sha="$(printf '%s\n' "$remote_line" | awk 'NR == 1 {print $1}')"
[[ "$remote_sha" == "$expected" ]] || die "GitHub branch SHA ${remote_sha:-NONE} does not equal expected $expected."

slug="$(printf '%s' "$branch" | tr -c 'A-Za-z0-9._-' '_')"
source_ref="refs/verified-bundle-source/${slug}/${expected}"
"${GIT[@]}" fetch --no-tags origin "+refs/heads/${branch}:${source_ref}"
[[ "$("${GIT[@]}" rev-parse "$source_ref")" == "$expected" ]] || die "fetched source ref does not equal expected."

temp_dir="$(mktemp -d /private/tmp/verified_git_bundle.XXXXXX)"
bundle_path="${temp_dir}/${slug}_${expected}.bundle"
manifest_path="${temp_dir}/${slug}_${expected}.manifest.json"

"${GIT[@]}" bundle create "$bundle_path" "$source_ref" "^${base}"
"${GIT[@]}" bundle verify "$bundle_path" >/dev/null
bundle_head="$(git bundle list-heads "$bundle_path" | awk -v ref="$source_ref" '$2 == ref {print $1}')"
[[ "$bundle_head" == "$expected" ]] || die "bundle head ${bundle_head:-NONE} does not equal expected $expected."

bundle_bytes="$(wc -c < "$bundle_path" | tr -d ' ')"
(( bundle_bytes > 0 && bundle_bytes <= max_bytes )) || die "bundle size ${bundle_bytes} exceeds the approved cap ${max_bytes}."
bundle_sha="$(sha256_file "$bundle_path")"
tree_sha="$("${GIT[@]}" rev-parse "${expected}^{tree}")"

cat > "$manifest_path" <<EOF
{
  "schema": "verified_git_bundle/v1",
  "sync_mode": "verified_incremental_git_bundle",
  "github_branch": "${branch}",
  "github_readback_commit": "${remote_sha}",
  "expected_commit": "${expected}",
  "base_commit": "${base}",
  "expected_tree": "${tree_sha}",
  "bundle_source_ref": "${source_ref}",
  "bundle_sha256": "${bundle_sha}",
  "bundle_bytes": ${bundle_bytes},
  "bundle_size_cap": ${max_bytes},
  "slurm_submission_authorized": false
}
EOF
manifest_sha="$(sha256_file "$manifest_path")"

if [[ -n "$prepare_only" ]]; then
  mkdir -p "$prepare_only"
  out_bundle="${prepare_only}/$(basename "$bundle_path")"
  out_manifest="${prepare_only}/$(basename "$manifest_path")"
  [[ ! -e "$out_bundle" && ! -e "$out_manifest" ]] || die "prepare-only output already exists."
  cp "$bundle_path" "$out_bundle"
  cp "$manifest_path" "$out_manifest"
  printf 'PREPARED_BUNDLE=%s\n' "$out_bundle"
  printf 'PREPARED_MANIFEST=%s\n' "$out_manifest"
  printf 'EXPECTED_COMMIT=%s\nBUNDLE_SHA256=%s\nMANIFEST_SHA256=%s\nBUNDLE_BYTES=%s\n' \
    "$expected" "$bundle_sha" "$manifest_sha" "$bundle_bytes"
  exit 0
fi

staging_dir="${remote_staging_root}/${slug}_${expected:0:12}"
control_path="/tmp/vgb.$$.sock"
fallback_proxy="${temp_dir}/reject_new_ssh_connection.sh"
cat > "$fallback_proxy" <<'EOF'
#!/bin/sh
exit 255
EOF
chmod 700 "$fallback_proxy"

master_ssh_opts=(
  -o BatchMode=yes
  -o ConnectTimeout=15
  -o ConnectionAttempts=1
  -o ServerAliveInterval=10
  -o ServerAliveCountMax=2
  -o ControlMaster=yes
  -o ControlPersist=no
  -o ControlPath="$control_path"
)
child_transport_opts=(
  -o BatchMode=yes
  -o ConnectTimeout=15
  -o ConnectionAttempts=1
  -o ServerAliveInterval=10
  -o ServerAliveCountMax=2
  -o ControlMaster=no
  -o ControlPersist=no
  -o ControlPath="$control_path"
  -o "ProxyCommand=${fallback_proxy}"
)

assert_original_master() {
  [[ -S "$control_path" ]] || die "original SSH control socket is unavailable; refusing a new connection."
  ssh "${child_transport_opts[@]}" -O check "$remote_host" >/dev/null 2>&1 || \
    die "original SSH control connection is unavailable; refusing reconnect or retry."
}

run_child_ssh() {
  assert_original_master
  ssh "${child_transport_opts[@]}" "$remote_host" "$@"
}

run_child_scp() {
  assert_original_master
  scp "${child_transport_opts[@]}" "$@"
}

[[ ! -e "$control_path" ]] || die "SSH control path already exists: $control_path"
ssh -MNf "${master_ssh_opts[@]}" "$remote_host"
master_open=1
assert_original_master

run_child_ssh bash -s -- \
  "$remote_base_checkout" "$remote_mirror" "$remote_checkout" \
  "$remote_staging_root" "$staging_dir" "$branch" "$expected" "$base" \
  "$tree_sha" "$source_ref" "$bundle_sha" "$manifest_sha" "$bundle_bytes" <<'REMOTE_PREFLIGHT'
set -euo pipefail
base_checkout="$1"
mirror="$2"
checkout="$3"
staging_root="$4"
staging="$5"
branch="$6"
expected="$7"
base="$8"
tree_sha="$9"
source_ref="${10}"
bundle_sha="${11}"
manifest_sha="${12}"
bundle_bytes="${13}"

command -v git >/dev/null
command -v flock >/dev/null
command -v sha256sum >/dev/null

[[ "$(git -C "$base_checkout" rev-parse HEAD)" == "$base" ]]
[[ -z "$(git -C "$base_checkout" status --porcelain --untracked-files=all)" ]]
[[ ! -e "$mirror" && ! -e "${mirror}.partial" ]]
[[ ! -e "$checkout" && ! -e "${checkout}.partial" ]]

mkdir -p "$staging_root" "$(dirname "$mirror")" "$(dirname "$checkout")"
exec 9>"${staging_root}/.verified_bundle_sync.lock"
flock -x 9
[[ ! -e "$staging" ]]
mkdir -m 700 "$staging"
cat > "${staging}/intent.json.partial" <<EOF
{
  "schema": "verified_git_bundle_intent/v1",
  "github_branch": "${branch}",
  "expected_commit": "${expected}",
  "base_commit": "${base}",
  "expected_tree": "${tree_sha}",
  "bundle_source_ref": "${source_ref}",
  "bundle_sha256": "${bundle_sha}",
  "manifest_sha256": "${manifest_sha}",
  "bundle_bytes": ${bundle_bytes},
  "remote_base_checkout": "${base_checkout}",
  "remote_mirror": "${mirror}",
  "remote_checkout": "${checkout}",
  "slurm_submission_authorized": false
}
EOF
mv "${staging}/intent.json.partial" "${staging}/intent.json"
REMOTE_PREFLIGHT

run_child_scp "$bundle_path" "${remote_host}:${staging_dir}/payload.bundle.partial"
run_child_scp "$manifest_path" "${remote_host}:${staging_dir}/manifest.json.partial"

run_child_ssh bash -s -- \
  "$remote_base_checkout" "$remote_mirror" "$remote_checkout" \
  "$remote_staging_root" "$staging_dir" "$branch" "$expected" "$base" \
  "$tree_sha" "$source_ref" "$bundle_sha" "$manifest_sha" "$bundle_bytes" <<'REMOTE_IMPORT'
set -euo pipefail
trap 'printf "SYNC_FAILED line=%s command=%s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR
base_checkout="$1"
mirror="$2"
checkout="$3"
staging_root="$4"
staging="$5"
branch="$6"
expected="$7"
base="$8"
tree_sha="$9"
source_ref="${10}"
bundle_sha="${11}"
manifest_sha="${12}"
bundle_bytes="${13}"
bundle_partial="${staging}/payload.bundle.partial"
manifest_partial="${staging}/manifest.json.partial"
bundle="${staging}/payload.bundle"
manifest="${staging}/manifest.json"
mirror_partial="${mirror}.partial"
checkout_partial="${checkout}.partial"

exec 9>"${staging_root}/.verified_bundle_sync.lock"
flock -x 9
[[ -f "$bundle_partial" && -f "$manifest_partial" ]]
[[ "$(stat -c %s "$bundle_partial")" == "$bundle_bytes" ]]
[[ "$(sha256sum "$bundle_partial" | awk '{print $1}')" == "$bundle_sha" ]]
[[ "$(sha256sum "$manifest_partial" | awk '{print $1}')" == "$manifest_sha" ]]
mv "$bundle_partial" "$bundle"
mv "$manifest_partial" "$manifest"

git -C "$base_checkout" bundle verify "$bundle" >/dev/null
bundle_head="$(git bundle list-heads "$bundle" | awk -v ref="$source_ref" '$2 == ref {print $1}')"
[[ "$bundle_head" == "$expected" ]]
[[ "$(git -C "$base_checkout" rev-parse HEAD)" == "$base" ]]
[[ -z "$(git -C "$base_checkout" status --porcelain --untracked-files=all)" ]]
[[ ! -e "$mirror" && ! -e "$mirror_partial" ]]
[[ ! -e "$checkout" && ! -e "$checkout_partial" ]]

git clone --bare "$base_checkout" "$mirror_partial"
git --git-dir="$mirror_partial" cat-file -e "${base}^{commit}"
git --git-dir="$mirror_partial" fetch "$bundle" "${source_ref}:refs/heads/${branch}"
[[ "$(git --git-dir="$mirror_partial" rev-parse "refs/heads/${branch}")" == "$expected" ]]
[[ "$(git --git-dir="$mirror_partial" rev-parse "${expected}^{tree}")" == "$tree_sha" ]]
mv "$mirror_partial" "$mirror"

git clone --no-checkout "$mirror" "$checkout_partial"
git -C "$checkout_partial" checkout --detach "$expected"
[[ "$(git -C "$checkout_partial" rev-parse HEAD)" == "$expected" ]]
[[ "$(git -C "$checkout_partial" rev-parse "HEAD^{tree}")" == "$tree_sha" ]]
# Avoid `git status` here: on this cluster it can remove the private `.git`
# directory of a just-created local-mirror clone. `git diff` verifies content
# rather than relying on the cluster filesystem's stale post-checkout stat data.
git -C "$checkout_partial" diff --quiet --ignore-submodules=all HEAD --
[[ -z "$(git -C "$checkout_partial" ls-files --others --exclude-standard)" ]]
# `git remote get-url` also removes the private `.git` directory on this
# cluster's just-created local-mirror clone. Read the explicit config file
# without repository discovery instead.
[[ "$(git config --file "$checkout_partial/.git/config" --get remote.origin.url)" == "$mirror" ]]
mv "$checkout_partial" "$checkout"

[[ "$(git -C "$checkout" rev-parse HEAD)" == "$expected" ]]
[[ "$(git -C "$checkout" rev-parse "HEAD^{tree}")" == "$tree_sha" ]]
git -C "$checkout" diff --quiet --ignore-submodules=all HEAD --
[[ -z "$(git -C "$checkout" ls-files --others --exclude-standard)" ]]
cat > "${staging}/remote_verification.json.partial" <<EOF
{
  "schema": "verified_git_bundle_remote/v1",
  "sync_mode": "verified_incremental_git_bundle",
  "github_branch": "${branch}",
  "expected_commit": "${expected}",
  "base_commit": "${base}",
  "checkout_head": "$(git -C "$checkout" rev-parse HEAD)",
  "checkout_tree": "$(git -C "$checkout" rev-parse "HEAD^{tree}")",
  "checkout_clean": true,
  "checkout_clean_method": "diff-index plus ls-files others; gitlinks uninitialized",
  "bundle_sha256": "${bundle_sha}",
  "manifest_sha256": "${manifest_sha}",
  "remote_mirror": "${mirror}",
  "remote_checkout": "${checkout}",
  "slurm_submission_authorized": false
}
EOF
mv "${staging}/remote_verification.json.partial" "${staging}/remote_verification.json"
REMOTE_IMPORT

printf 'VERIFIED_REMOTE_CHECKOUT=%s\n' "$remote_checkout"
printf 'VERIFIED_REMOTE_MANIFEST=%s/remote_verification.json\n' "$staging_dir"
printf 'EXPECTED_COMMIT=%s\nBUNDLE_SHA256=%s\nBUNDLE_BYTES=%s\n' \
  "$expected" "$bundle_sha" "$bundle_bytes"
printf 'SLURM_SUBMISSION_AUTHORIZED=false\n'
