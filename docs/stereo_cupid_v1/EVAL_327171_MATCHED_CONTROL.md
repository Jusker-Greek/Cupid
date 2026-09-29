# Official-weight control and step809 comparison

Control job 327171 completed 0:0 on server13, one GPU, 00:01:57.
Code commit: c9dd56daecdcfb85a28de373f3b231d1f14afd1d.
Checkout: /public/home/ricky/CODE/stereo_cupid_eval_c9dd56d_a2.
Output: /public/home/ricky/RESULTS/STEREO_CUPID_EVAL_OFFICIAL_C9DD56D_A1.
Official SUV weight SHA256: e3d0b50ffbb70295b5f6528180d0671d0d71bcf55a19e8c51e0fd19229aab459.
Control flag: CUPID_OFFICIAL_BASELINE=1 scripts/eval_stereo_checkpoint.sbatch.
Local raw reports and copied training events: outputs/stereo_eval_327171/.

Compared with job 327135, the three sorted test pair IDs, seed 42, full-image preprocessing, 25-step stereo sampler, Stage2, cameras, targets and evaluator are identical. The control keeps official SUV weights instead of replacing them with step809 weights. Both jobs produced all three meshes and geometry results. This measures the effect of fine-tuning under our stereo inference and empirical target convention. It does NOT reproduce the original monocular CUPID benchmark.

| Test object | Official occupancy IoU | Step809 IoU | Official rotation deg | Step809 rotation deg | Official translation scene_unit | Step809 translation scene_unit |
|---|---:|---:|---:|---:|---:|---:|
| ASICS GELBlur33 | 0.073339 | 0.061837 | 166.0623 | 90.0260 | 1.557085 | 0.759259 |
| ASICS GELLinksmaster | 0.059336 | 0.157881 | 117.0388 | 92.6562 | 0.673052 | 7.098878 |
| Adrenaline GTS13 | 0.066462 | 0.101658 | 169.1561 | 124.4705 | 0.392060 | 0.167191 |
| Mean | 0.066379 | 0.107125 | 150.7524 | 102.3842 | 0.874066 | 2.675109 |

Mean occupancy and rotation improve, but mean translation deteriorates. The second object dominates translation regression; its predicted scale rises from 5.032457 to 19.773386 against target 1. Neither model is geometrically accurate in this diagnostic. All samples are shoes; one seed and three pairs do not establish dataset-wide or category-wide improvement. Canonical axes/normalization are the empirical training convention, not a demonstrated match to the original pretrained model's preferred canonical orientation.

## Training and split facts

Training job 327039 completed 809 optimizer updates in one epoch, batch one stereo pair, one GPU, 00:15:34. Runtime events confirm pretrained_init (no optimizer resume), all SUV flow parameters trained, frozen DINO and target encoders, and no Stage2 training. The dataset contains 1000 pairs from 902 objects: 809 train / 93 validation / 98 test, assigned by object_id hash. Evaluations 327135 and 327171 each cover the same first three test pairs, not train/validation pairs and not all 98.

| Validation metric, 93 pairs | Before fine-tuning, step0 | Step809 |
|---|---:|---:|
| Total FM loss | 5.2802544204 | 0.2868434017 |
| SS FM loss | 0.2080905283 | 0.2266308109 |
| UV FM loss | 10.3524183612 | 0.3470559908 |

Loss reduction is driven by the UV branch, while SS loss worsens. The objective is latent velocity MSE, not triangulated pose/reprojection loss (cupid/trainers/stereo_stage1_objective.py). Shared SS sampling does not by itself enforce geometrically consistent UV correspondences. These observations explain why loss reduction cannot establish improved final geometry. Coordinate/preprocessing distribution mismatch, insufficient adaptation, and UV correspondence instability remain hypotheses, not isolated causal findings.

## Published CUPID comparison boundary

Source: https://arxiv.org/html/2510.20776v2, Tables 1, 2, 5 and Appendix A.1.

GSO Table1: mask IoU 95.27, CD mean 1.823 / median 0.434, F-score@0.01 61.01 / @0.05 95.59 (paper display units). Table2: PSNR 28.68, SSIM 95.49, LPIPS 0.0354. Table5 pose-encoding/decoding fidelity means: normalized reprojection 0.0009, RRE 0.46, RTE 0.45, RFov 0.15. Table5 is not our image-to-stereo Sim(3) evaluation.

The paper trains on ABO/HSSD/3D-FUTURE/Objaverse-XL and evaluates on GSO/Toys4K. We additionally fine-tuned on our GSO train split. The paper's GSO evaluation cannot be identified with our renderer, selected pair IDs, or 809/93/98 split. No published per-sample result matching these exact three stereo pairs has been verified. Mask IoU is not occupancy IoU; the paper's visible point cloud metrics use scale-shift alignment. Our raw canonical rotation and scene_unit translation are not those published benchmark metrics. PSNR/SSIM/LPIPS/CD/F-score have not yet been evaluated for step809.

Next discriminating measurements: original monocular CUPID on the identical left images with render-space metrics; full held-out comparison; and GT UV encode/decode plus reprojection overlays to separate coordinate/representation error from generated correspondence error. A small bounded improvement must not be presented as beating the paper.
