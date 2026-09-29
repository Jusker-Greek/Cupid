# Original CUPID image metrics connected to checkpoint evaluation

Implemented and executed, 2026-09-29. Runtime commit `8a20cf17848516c6d55b399c3605b941212ab172`, tree `0867e83f9ef3fb2540b7dfc206f8811dbc85550b`.

The checkpoint renderer directly imports `psnr`, `ssim` and `lpips` from the original `cupid/utils/loss_utils.py`. LPIPS uses the original VGG network and [0,1] to [-1,1] conversion. It uses the original colored `MeshRenderer` and adds rendered mask IoU. No image alignment to ground truth is performed. Evaluation uses native 512x512 full-frame images with black alpha-composited background and RGB in [0,1].

Entry point: `scripts/eval_stereo_checkpoint.py --render-metrics`. The Slurm launcher accepts arbitrary checkpoint paths/hashes, config, split, limit and deterministic selection seed. New trainer code passes this flag to its checkpoint evaluator; already-running job 327206 remains on its original immutable checkout and receives independent supplementary evaluations through the existing 30-minute heartbeat.

## Actual verification

- Job **327221**, **COMPLETED 0:0**, elapsed **00:03:11**, one GPU.
- Checkpoint step819, SHA256 `b942ea9229b481dd8dcfffea946b4007112612d20ebe6007f7958b0a98455292`.
- Eight fixed validation pairs, selected by seed20260929, identical to the step819 training evaluation.
- Original metric identity tests and off-centre renderer camera/depth tests passed. All eight samples succeeded under all three render conventions: 24 render evaluations, each with PSNR/SSIM/LPIPS/mask IoU, 100% metric coverage.
- Adding image evaluation preserved prior predictions: occupancy IoU `0.048301665215849214`, rotation error `128.56462914790467` and translation error `1.8585512003991804` exactly match job327172's aggregate values.

| Rendering convention | PSNR dB, higher better | SSIM, higher better | LPIPS VGG, lower better | Mask IoU, higher better |
|---|---:|---:|---:|---:|
| Original left DLT pose / predicted intrinsic | 11.604239 | 0.607241 | 0.294835 | 0.069944 |
| Stereo-estimated Sim(3), left calibrated camera | 11.816739 | 0.619084 | 0.318356 | 0.292733 |
| Stereo-estimated Sim(3), right calibrated camera | 11.963621 | 0.645734 | 0.303530 | 0.311213 |

The last two rows use stereo-estimated rotation, translation and scale; the right pose is obtained with the known right-from-left calibration. They do not use ground-truth object alignment. These are input-view reconstruction measurements, not novel-view synthesis or reproduction of the paper's exact benchmark. Low scores are retained as actual results.

Cluster output: `/public/home/ricky/RESULTS/STEREO_CUPID_RENDER_8A20CF1_STEP819_VAL8_A1`.
Local report: `outputs/stereo_render_327221/evaluation.json`.
Each sample contains render_metrics.json, rendered RGB PNGs and GT/prediction side-by-side PNGs. One inspected example shows the reconstructed object substantially outside its correct image location; the low image/mask scores must not be described as a missing evaluator.

## Continuing the live 50k run

Job327206 was read back RUNNING after 23:07 elapsed. Its existing training and geometry evaluations are unchanged. The monitor is configured to submit one supplementary image-evaluation job for each new complete checkpoint at step5000 and later, using the same fixed eight validation pairs; the final checkpoint also receives 98-pair test image evaluation. It checks active jobs, outputs and receipts before submission to prevent duplicates. The starting point for these curves is this completed step819 run.

A separate matched three-test-pair comparison, job327209, also completed (official monocular crop/full, official stereo and step809 stereo). Those are different samples and must not be mixed with this eight-validation-pair curve. Its geometry distances use their separately recorded scale/shift alignment protocol.

Remaining uncertainty: whether longer training improves these image metrics. The present measurements combine geometry, pose and appearance errors; they do not identify a single cause of failure.
