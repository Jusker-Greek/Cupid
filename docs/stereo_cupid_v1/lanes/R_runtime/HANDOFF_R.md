# R runtime lane — 2026-09-21

Owner task: `01a0bfa4-b8ec-7bc3-ac05-ae1d58238a11`. Controller:
`01a0ba51-e1eb-7012-8147-c2cf36ad66b8`; integration I:
`01a0bfa4-bcf6-7761-a7a1-948b703719ee`.
Isolated checkout `/Users/ruikegu/.codex/worktrees/d23e/Cupid`, branch
`codex/stereo-cupid-r-runtime`, parent `0c77ae9c6648b918c820f79dbe15f80235c17709`.

## Scope and checklist

- [x] Read current rules, pinned controller authority `d88b19e0414aaf482b21f5630b64df604dc2c57a`, baseline reports and transfer implementation.
- [x] Implement offline 25-file assembly/hash/pipeline checks and immutable failed-attempt receipts.
- [x] Implement exact GitHub-to-fresh-checkout sync and serialized CPU assembly/1GPU pilot submission.
- [x] Add upload-only mode, optional official small metadata, and incoming-path persistence before transfer.
- [ ] Commit/push and exact GitHub commit/tree readback (see milestone message).
- [ ] Slurm syntax/contract checks, asset assembly and actual GPU inference.
- [ ] I-provided training integration: single GPU, two GPU DDP, W&B readback, frozen low-card full.

All implementation checkboxes describe static source work, not executed tests.
No model/data algorithm changed. Frozen inference remains
`STEREO_CUPID_V1_SHARED_SS`; training must use independent
`STEREO_CUPID_STAGE1_TRAIN_V1` candidate identity.

## First failed predicate and evidence

00:26 and 00:29 CST strict-hostkey SSH to the existing `ricky@10.10.7.1`
endpoint failed before server identification / key exchange. Debug tail:

```text
Local version string SSH-2.0-OpenSSH_10.3
kex_exchange_identification: Connection closed by remote host
Connection closed by 10.10.7.1 port 22
```

Read-only route observation: `10.10.7.1 -> gateway 198.18.0.1, utun8`.
System HTTP/HTTPS/SOCKS proxy flags are 0. Existing ClashX PID31816 listens
on `127.0.0.1:7890`. These facts do not prove ClashX is the root cause.
No SSH/VPN/system/route modifications, host scans, job submissions, or
remote hashes occurred. Known old jobs 306009/306014 and forwarding session
5028 remain historical terminals; no restart is authorized for those identities.

## Assets and interfaces

Local six verified weights: `/Users/ruikegu/Downloads/Cupid_official_1191de37_local_a1`,
4,168,403,480 bytes. Existing cluster five weights (must reverify after access):
`/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_a12`, 3,099,847,620 bytes.
Prior upload destination: `/public/home/ricky/CHECKPOINT/Cupid_official_1191de37_local_upload_a1`.
Remote partial/final existence is UNKNOWN until fresh inspection.

Pinned `R_official_manifest.json` is the saved official public API response
for `hbb1/Cupid@1191de37cc33b60273a631d4e07fbbe7cee798c1`.
Its SHA256 is `ce25e0cff494f4b0dce0966fa74e5ae815df752eaa6fb05950ffc98627600692`.
The complete release has 25 files / 7,268,259,545 bytes: 11 LFS weight
SHA256 checks plus 14 Git-blob-SHA1 small-file checks. The assembly code
pins the manifest bytes, rejects path escapes/duplicate names, verifies each
source and destination, and checks every pipeline model JSON/weight reference.
It never downloads a weight or mutates either source root. Hardlinks reuse
storage on the same filesystem; verification is repeated immediately before
model load to detect subsequent source mutation. EXDEV uses exclusive copy.

`stereo_runtime_assets.py --output NEW_ROOT --source STOPPED_A --source UPLOAD_B`
runs only in a Slurm compute allocation; `--verify-only` checks an assembled
root again without changing it. Failure preserves a FAILED receipt and files.

`stereo_runtime_sync.sh BRANCH COMMIT TREE NEW_CLUSTER_CHECKOUT` runs locally,
checks GitHub SHA and fetched tree, and uses remote Git clone/checkout only.
Failed `.partial` roots are preserved. If cluster GitHub access fails, use
the existing approved `sync_verified_git_bundle.sh` with a fresh identity;
that helper expects the pushed repository as `origin`, so use an isolated
Git clone configured to the fork rather than change shared worktree remotes.
Pass `GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=yes'` only for Git;
the bundle helper's SSH calls additionally need existing strict hostkey policy
verified before use. Do not transfer source directories.

`stereo_runtime_submit.sh` is a remote control-plane wrapper. Required exported
environment: `CUPID_PROJECT_DIR`, `CUPID_EXPECTED_COMMIT`, `CUPID_EXPECTED_TREE`,
`CUPID_RUNTIME_MODE=assemble|pilot`, `CUPID_MODEL_PATH`,
`CUPID_RUNTIME_EVIDENCE` (fresh `/public/home/ricky/RESULTS/<identity>`).
It stores squeue/sacct/sinfo and scontrol readbacks, uses a campaign lock,
and rejects active campaign weight/upload/pilot jobs. No fixed node.
Assembly is CPU/2 cores/4GB/30min with `CUPID_ASSET_SOURCE_A/B`.
Pilot is 1GPU/8 cores/64GB/30min on `gpu,gpux` and requires `CUPID_FULL_MESH=1`.
The job wrapper records commit/tree, exact terminal exit and runtime log.
This wrapper does not yet implement training: I must provide that entrypoint.

## Next executable actions

1. Recheck existing endpoint with strict hostkeys, then fresh squeue/sacct
   for `cupid_local_upload*`, `cupid_weights*`, `stereo_cupid*`; inspect only
   the known upload root's incoming/final names. Do not treat earlier SSH
   failure as proof that no receiver job/root exists.
2. In a Slurm CPU allocation hash any existing upload finals/incomings;
   if valid finals already exist, reconcile local transfer receipts from
   actual official-hash readback before uploading remaining files. Never
   overwrite finals or discard incomings. Preserve an uncertain transfer
   attempt and use a fresh successor when correction is needed.
3. Download only missing small official metadata via existing authorized
   local proxy if needed; reuse all six existing local weights. Then use:

```sh
python3 scripts/cupid_local_asset_transfer.py \
  --root /Users/ruikegu/Downloads/Cupid_official_1191de37_local_a1 \
  --proxy http://127.0.0.1:7890 \
  --remote-root /public/home/ricky/CHECKPOINT/Cupid_official_1191de37_local_upload_a1 \
  --include-small --upload-only
```

4. Sync the exact pushed source to a new checkout. On the compute node run
   shell syntax checks / Python compilation with pycache outside checkout,
   then the CPU assembly job using the two roots above and a fresh final root.
5. Only after full `VERIFIED`, submit full frozen pilot. Existing paths:

```sh
export CUPID_PAIR_DIR=/public/home/ricky/DATASET/gso_stereo_output_random/Android_Figure_Panda/random_linear_0
export CUPID_DINO_REPO=/public/home/ricky/.cache/torch/hub/facebookresearch_dinov2_7764ea0f912e53c92e82eb78a2a1631e92725fc8
export CUPID_DINO_CHECKPOINT=/public/home/ricky/.cache/torch/hub/checkpoints/dinov2_vitl14_reg4_pretrain.pth
export CUPID_CAMERA_JSON="$CUPID_PROJECT_DIR/configs/stereo/gso_panda_random_linear_0_scene_unit.json"
export CUPID_FULL_MESH=1 CUPID_FRAME=000 CUPID_SEED=42
```

Set a new `CUPID_OUTPUT_DIR` and evidence identity for every attempt.
Scene units are not proven meters. Geometric rejection must remain visible;
do not align predictions to GT or label mesh/pipeline readiness scientific PASS.
Immediately send each terminal with first error or pass evidence to Controller
and I; ask I for next exact integration commit/config. R alone submits GPU jobs.

## Reflection

- Unverified: remote current job/root state, assembly execution, runtime dependencies and model path.
- Risk: split local/remote weight completion or a successful wrapper exit can be mistaken for complete model or scientific evidence; the actual receipts and artifacts control advancement.
