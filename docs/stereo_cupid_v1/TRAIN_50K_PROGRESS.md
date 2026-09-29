# 50,000-update continuation with in-training evaluation

The 809 training pairs are a dataset count. With one GPU and one pair per optimizer update, the completed job 327039 performed 809 updates, exactly one epoch. A total budget of 50,000 updates is approximately 61.8 epochs over the same training split; it does not add samples. The dataset remains 1000 GSO stereo pairs / 902 objects, split by object into 809 training, 93 validation and 98 test pairs.

## Implemented schedule

- Resume optimizer, constant learning-rate scheduler, AMP scaler, random states and exact data cursor from the existing checkpoint. Allow the explicitly bound step809 checkpoint to extend the budget, while rejecting changes to data, objective, optimizer, batch size, model assets or topology.
- Validate flow-matching total/SS/UV losses on all 93 validation pairs every 1000 updates.
- Save a full-state checkpoint every 5000 updates. In the same GPU allocation, pause training and invoke the existing checkpoint evaluator on eight fixed validation pairs selected by SHA256 of seed 20260929 and pair ID. Save predictions, meshes, cameras, per-sample metrics, aggregate metrics and coverage.
- At update 50000, additionally evaluate all 98 test pairs. Three test pairs were previously inspected diagnostically; this is not an entirely unseen benchmark.
- Store training and generation metrics in durable JSONL, TensorBoard and W&B offline. No W&B server upload is claimed.

Configuration: `configs/stereo/train_stage1_gso_50k.json`, SHA256 `bb9698c45f7970a6044b8bcc81ab353ebac85e1f3de85a5d5f471a2461e27bda`.

## Completed end-to-end check

Job **327172**, server13, one GPU, **COMPLETED 0:0**, elapsed **00:08:03**. Runtime commit `917145957a99571abd0fff8f43280d9727abaab5`. Passed four budget-extension tests and nine existing trainer tests; resumed step809 and completed updates810–819. All 93 validation losses and all eight Stage1/Stage2 generation evaluations completed. All eight meshes were saved.

Checkpoint: `/public/home/ricky/RESULTS/STEREO_CUPID_50K_9171459_SMOKE_A1/output/step_00000819.pt`.
Checkpoint SHA256: `b942ea9229b481dd8dcfffea946b4007112612d20ebe6007f7958b0a98455292`.
Evaluation: same output root, `eval_step_00000819_validation/evaluation.json`.

| Step819 measurement | Value | Coverage |
|---|---:|---:|
| Validation FM loss, total | 0.2779966274 | 93/93 |
| Validation FM loss, SS | 0.2250026862 | 93/93 |
| Validation FM loss, UV | 0.3309905685 | 93/93 |
| Occupancy IoU | 0.0483016652 | 8/8 |
| Left UV projection error, pixels | 234.9308099 | 8/8 |
| Right UV projection error, pixels | 203.8094359 | 8/8 |
| Rotation error, degrees | 128.5646291 | 8/8 |
| Translation error, scene_unit | 1.8585512 | 8/8 |
| Relative scale error | 5.2894995 | 8/8 |
| Mesh generation success | 100% | 8/8 |

These are poor geometry results under the empirical GSO target convention, not absent evaluations. This validation subset differs from the earlier three test shoes, so their means must not be used as a before/after comparison. Mesh generation success is not mesh reconstruction accuracy. Similarity-fit RMSE and valid-triangulation counts are diagnostics, not independently supervised accuracy metrics.

## Long run

Job **327206** submitted for one H200 GPU and 24 hours, from step819 to a total of 50000. Code commit `36ac81850509ff62e1fbcf018188ee3f9d5dfe6b`, tree `7ea2d0a95bd281a89d935583f27afe32c310c7f8` (same runtime as the completed check, with the W&B generation x-axis renamed to the existing `train/global_step`).

Checkout: `/public/home/ricky/CODE/stereo_cupid_50k_36ac818_a1`.
Output: `/public/home/ricky/RESULTS/STEREO_CUPID_50K_36AC818_FULL_A1/output`.
Submission receipt: `/public/home/ricky/RESULTS/STEREO_CUPID_50K_36AC818_FULL_A1.submission`.

The existing Stereo-CUPID heartbeat now monitors this exact job every 30 minutes, retaining valid queued/running jobs and repairing actual failures through local editing, GitHub synchronization and a new cluster attempt. Completion of 50k training is not yet claimed.

## Metric availability and limits

Working on actual checkpoint predictions: occupancy IoU, left/right UV projection error, raw rotation/translation/translation-direction/norm/scale errors, triangulation count, similarity-fit RMSE, prediction and mesh success, and per-metric coverage. Flow losses are validated separately on all 93 pairs.

Existing original code but not connected and validated on this stereo split: PSNR, SSIM and LPIPS in `cupid/utils/loss_utils.py`. They still need predicted/GT render pairing under the same camera and image convention.

Not end-to-end implemented/validated in this checkpoint evaluator: rendered mask IoU, mesh/point-cloud Chamfer distance and F-score, normal accuracy, depth AbsRel/RMSE and correspondence EPE. Physical-metre translation error is explicitly NOT_APPLICABLE because the data contract only establishes scene_unit. The empirical canonical convention has not been established as equivalent to the official pretrained model or paper benchmark.

Main uncertainty: whether more updates improve geometric predictions rather than only latent flow loss. Principal risk: repeatedly fitting 809 pairs may overfit; the fixed validation geometry curve and final test evaluation must determine the conclusion.
