# L callback contract v1

Experiment `STEREO_CUPID_STAGE1_TRAIN_V1` candidate; inference baseline
`STEREO_CUPID_V1_SHARED_SS` remains frozen. Engineering implementation, no run claim.

- Hypothesis: explicit status/provenance and durable records expose missing Stereo
  metrics without changing optimization or scoring after GT alignment.
- Baseline: 0c77ae9c6648b918c820f79dbe15f80235c17709; existing CUPID
  `cupid/trainers/base.py` writer/run, `cupid_train.py` initialization and
  `scripts/verify_cupid_wandb.py` scan_history pattern are reused.
- Sole change: observability adapter/evaluator. Model/loss/data/split untouched.
- Check: exact independent fixtures, coverage, proper rotations, no GT alignment,
  no silent metre conversion, local records surviving sink failure.
- Failure plan: preserve attempt, repair first predicate, push and run fresh CPU
  fixture on Slurm through R. No full-training or S07 acceptance from local files.

## Training callback

```python
from cupid.stereo_observability.logger import logger_factory
callback = logger_factory({
    'identity': {'experiment_id': 'STEREO_CUPID_STAGE1_TRAIN_V1',
                 'attempt_id': attempt_id, 'git_commit': commit,
                 'git_tree': tree, 'slurm_job_id': job_id},
    'writer': existing_tensorboard_writer, 'wandb_run': existing_wandb_run,
}, output_dir, rank)
callback('loss', step, dict(split='train', total=total, components=components,
    epoch=epoch, learning_rates=[group['lr'] for group in optimizer.param_groups],
    num_samples=global_num_samples))
callback('optimizer', step, dict(applied=optimizer_step_applied,
    grad_norm=unscaled_grad_norm, amp_log_scale=amp_log2_scale))
callback('checkpoint', step, dict(path=checkpoint_path, status='WRITTEN', sha256=sha256))
callback('status', step, dict(metric='test/loss_total', status='UNVERIFIED',
    reason='held_out_test_not_executed_in_this_smoke'))
callback('evaluation', step, dict(split='validation', samples=all_expected_samples))
```

`loss` also accepts validation/test; evaluate held-out losses under caller-owned
no_grad and weighted by actual sample count, not average of unequal batch means.
Components retain the T trainer's actual names and values; L invents no weights.
Required event names: loss/optimizer/checkpoint/status/evaluation. Every sample
must have a stable sample_id; missing/failed predictions remain in samples.
Gradient norm is after AMP unscale, with before/after clipping convention recorded
by T. `amp/log_scale` is numerical log2 scaling; `pose_scale` is a geometric
Sim(3) coefficient. Neither substitutes for the other.

This callback performs **no collective and no model forward**. Construct on all
ranks; rank>0 calls are no-op. T owns global reductions before callbacks.
For rank0 eval_hook(model,step,context), pass unwrapped `model.module`, not the DDP
wrapper. All ranks must enter matching before/after barriers outside the hook;
T must propagate rank0 evaluation errors to all ranks before the next collective.
If validation forwards use DDP or distributed datasets, run them on all ranks and
reduce/gather before rank0 logging. Never invoke a DDP forward on rank0 alone.

W&B/TensorBoard objects belong to T; L does not initialize, finish or close them.
Use this path once per event, not a second call to the old trainer W&B emission.
W&B uses SDK history row numbering; train/global_step remains the training axis,
so repeated events at one optimizer step cannot overwrite/drop each other.
Failures record only exception type, never credential-bearing exception strings.
Use existing `scripts/lib/wandb_env.sh` only for explicitly online runs; it forces
online mode and is intentionally NOT sourced for offline caching. Pass no run
or an existing offline run when offline; events.jsonl remains durable regardless.
An offline cache, SDK success, URL, or TensorBoard file never proves S07.

## Independent sample schema

```json
{"sample_id":"object/trajectory/frame", "prediction_status":"OK",
 "prediction_uses_gt_alignment":false,
 "prediction":{"rotation":[[1,0,0],[0,1,0],[0,0,1]],"translation":[0,0,2],
  "scale":1,"canonical_id":"audited_axes_origin_normalization_v1",
  "target_frame":"left_camera_opencv_pair_id","length_unit":"scene_unit"},
 "gt":null}
```

GT, when independently established, has the same pose/frame/unit fields plus
`verified:true`, nonempty `provenance`, and `metric_unit_verified:true` only for
verified physical metres. Common canonical_id certifies **axes + origin +
normalization**, not just shared occupancy indices or the label cupid_canonical.
Rotation error is raw SO(3) geodesic degrees, translation Euclidean error in the
common unit, direction angular error, norm ratio/absolute difference, positive
scale relative/absolute difference. No scale fitting or GT alignment occurs.
Scene-unit errors can be reported in scene units when provenance is valid;
translation_error_m remains NOT_APPLICABLE without metre proof. Reflection
matrices are invalid. Zero vector direction/zero GT norm ratio are undefined.
GT absent: errors NOT_APPLICABLE with reason; raw predicted norm/scale remain
available. Missing origin/frame/provenance: UNVERIFIED. Missing predictions are
UNVERIFIED and count in each coverage denominator. Per-sample reason survives.
`from_v1_result` reads only raw stereo similarity; generic V1 canonical is not
promoted to an audited canonical, and pose_left_predicted is not GT.

## Ownership

L only adds cupid/stereo_observability/, scripts/stereo_evaluate*.py and
lanes/L_* files. T connects callbacks; I connects optional frozen V1 postprocess;
D owns coordinate evidence; R owns actual Slurm tests and W&B network/readback.

## Rank0 evaluation factory and delivery/readback

`cupid.stereo_observability.integration.eval_factory(fullconfig, output_dir, rank)`
returns `hook(model=bareSharedStereoFlow, step=step, context={'samples': records})`.
The hook performs no forward or collectives; T owns val FM loss on all ranks,
barriers and exception broadcast. It evaluates raw pose records furnished by I/T
and returns JSON. Absent records explicitly return UNVERIFIED. Call
`callback('evaluation', step, {'samples': records})` for durable per-sample and
aggregate logs. Do not pass the hook's already-evaluated rows back as raw records.

`readback.load_events(root)` verifies event sequence, identity and hashes.
`readback.replay(root, existing_run)` replays offline JSONL without creating a
tracker or accessing credentials. Identical repeated event IDs are acceptable
following interrupted replay; conflicting server records fail exact readback.
The independent CLI `scripts/stereo_evaluate.py --wandb-root ... --run-path ...`
scans W&B server history using the same existing CUPID scan_history approach,
then checks every event payload, not just presence of a key. It produces
READBACK_PASS or UNVERIFIED; **s07_status always remains UNVERIFIED**, because
Controller must separately verify applicable contracts, S05/S06 and real run
paths. Replay enqueue is not delivery, and readback success is not science.
Local details hashes bind full per-sample results retained in events.jsonl.

I can evaluate frozen V1 results without editing the V1 inference code:
`--v1-manifest manifest.json` contains one object per expected sample with
sample_id, result_path and optional independently audited gt/canonical_id.
A missing/malformed result becomes a failed sample, preserving the denominator.
