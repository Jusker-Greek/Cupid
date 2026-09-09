# CUPID V1 Explainer Parts

Status: `DESIGN ONLY / S01 UNVERIFIED / NOT IMPLEMENTED / NOT USER-APPROVED`

These six editable Draw.io files are review crops derived from the same mother
diagram:

- `../p02_cupid_same_time_right_recon_v03_candidate.drawio`
- source commit: `4ff75c32d2968ee9ca8e96a3e19ece3634b9c5ca`
- frozen design specification: `1d3d9af:docs/CUPID_STEREO_INSERTION_SPEC_V1.md`

The crops preserve copied objects, labels, colors, locks, and connector
semantics from the v03 candidate. They do not introduce a replacement pipeline
or claim implementation, training, approval, or experimental results.

## Parts

1. `part01_inputs_and_supervision`: left conditioning input and synchronized
   right training target.
2. `part02_stage1_structure_and_pose`: frozen Stage 1 structure, UV, and pose
   path.
3. `part03_stage2_generation`: existing Stage 2 denoiser, the only trainable
   model in V1.
4. `part04_clean_latent_and_frozen_decode`: one-step clean-latent estimate and
   frozen but input-differentiable Gaussian decoder.
5. `part05_fixed_camera_render`: calibrated right camera and parameter-free,
   differentiable renderer consumer.
6. `part06_loss_and_gradient_boundary`: right-view reconstruction sink and the
   gradient boundary that stops at Stage 2.

Each part is supplied as an editable `.drawio` file and a rendered `.png` used
by `outputs/cupid_v1_right_reconstruction_explainer_v01.pptx`.
