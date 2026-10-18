# SC-POSECROSS-V1 component and data audit preparation

These entry points are engineering diagnostics, not a trainable cross-pose
method, proxy objective, pretrained model smoke, S05 pass, or scientific result.
They must only run on Slurm compute nodes after local commit/push and fresh
exact-source checkout. The native training and inference implementations are
unchanged. The main method remains at S01 pending the design/data contract.

- `scripts/posecross_component_audit.py`: use the real native Gaussian renderer
  on explicit synthetic primitives; compare camera autograd to translation
  finite differences and verify primitive gradients. Also audit native DLT's
  UV gradient and whether changing the supplied K changes its outputs.
- `scripts/posecross_data_audit.py`: re-read every bound GSO pair and target
  hash; check all three splits, object/image/source-asset overlap, existing
  empirical camera mapping, rectification residuals and effective crop K.
  Numeric consistency never approves historical renderer/canonical provenance.
- `scripts/posecross_audit_job.sh`: exact clean checkout and Slurm guards;
  `components` requires one GPU; `data` is a CPU job. No automatic submissions.

A completed diagnostic can report a failed component contract. Read the JSON
fields, not only the process exit. No optimizer/checkpoint/flow result is implied.

`cupid/renderers/posecross_gaussian.py` adds an opt-in SH0 camera-gradient
adapter. It transforms Gaussian means and covariances in Torch, preserving
fixed calibrated K, and uses the native rasterizer with an identity view.
Existing callers are unchanged. `scripts/posecross_renderer_adapter_audit.py`
checks native forward parity with anisotropic rotated primitives and compares
rotation/translation derivatives against central finite differences. This is
component-only evidence even if it passes; no full CUPID path is exercised.

GPU 371350 diagnosed the original finite-difference mismatch: epsilons crossing
nonzero-pixel support boundaries differ from a within-branch derivative. The
original coarse check remains in receipts and remains FAIL. A separate
`renderer-local-jacobian` component contract keeps the 5% tolerance and tests
all observed zero-support-change epsilons (at least two per parameter), with
three preregistered yaw/translation fixtures: (.13,.08), (-.17,-.06), (.21,.04).
No renderer thresholds, filtering, losses, or primitive values are changed.
A local derivative PASS does not make the renderer globally smooth and does
not pass the model smoke or scientific gates.

### Known-K component proposal

`cupid/utils/known_k_pnp.py` implements a single-sample fixed-K/fixed-XYZ
implicit PnP with an independent full reprojection Hessian backward. Forward
uses EPNP, iterative PnP and LM (100 iterations, 1e-12 stop tolerance), without
RANSAC. Rodrigues rotation plus direct translation is its 6D chart; translation
is not the translational part of an SE(3) logarithm. It accepts calibrated,
zero-skew pinhole K and corresponding normalized or pixel UV in matching units.
It rejects near-planar support, nonpositive depth, nonstationarity and ill-
conditioned Hessians instead of silently dropping losses. Float64 internally;
first derivatives only. Thresholds are a component proposal, not full-data
eligibility. Native CUPID inference/training does not call this component.

`scripts/posecross_known_k_audit.py` checks two noisy noncoplanar synthetic
fixtures, 18 central-FD comparisons per pose (six coordinates, three eps;
36 perturbed solves per pose),
every relative error <1%, calibrated-K sensitivity and invalid-input rejection.
It does not validate noisy predicted UV, full model gradients, pose ambiguity,
optimizer/checkpoint/evaluation, or a scientific training result. The implicit
formulation follows [BPnP](https://github.com/BoChenYS/BPnP); no source vendored.
