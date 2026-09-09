# CUPID Same-time Right Reconstruction Candidate v03 Audit

Status: `DESIGN ONLY / S01 UNVERIFIED / NOT IMPLEMENTED`

Date: 2026-09-09

## Scope

- Target: editable CUPID integration candidate only. No PPT/PPTX file was modified.
- Gate: `CUPID-SAME-TIME-RIGHT-RECON-V1`.
- Scientific status: design-only architecture delta; no implementation, training run, metric result, or metric-scale claim.
- Parent: `p02_cupid_repro_paper_pipeline_v02_candidate.drawio`.
- Candidate outputs: `p02_cupid_same_time_right_recon_v03_candidate.drawio` and matching PNG.

## Primary Authority And Lineage

- Insertion authority: `docs/CUPID_STEREO_INSERTION_SPEC_V1.md`, commit `1d3d9af`, branch `fork/codex/cupid-stereo-ssl-slides-storyboard`.
- Baseline visual authority: CUPID paper Figure 3, arXiv:2510.20776, as reconstructed in baseline v02.
- Parent baseline SHA256: `b8e50697e92e25edb96be05c08f96fffd22b91c5f795fbd36923f710480ecdab`.
- Candidate Draw.io SHA256: `607c42f1ef1140144d88b596988351664f586a6d21661dbcbaefe79de0b7765a`.
- Candidate PNG SHA256: `48cd309c029403d3c2c8487924ce045d98911b86a6193c761a4acde7eb047d71`.
- Parent status: `CANDIDATE / NOT USER-APPROVED`.
- Candidate lineage: v03 is copied from v02; v02 is not overwritten.

## Frozen Baseline Contract

- All 130 v02 cells remain present.
- Baseline object contract is unchanged: every existing vertex/edge retains its geometry, style, label, source/target, and connector semantics.
- Stage 1, DINOv2, PnP, left pose-aligned conditioning, Stage 2, Mesh decoder, Mesh output, and the original Gaussian path remain visually unchanged.
- Left image remains the only conditioning image; the right observation is connected only to the training loss.
- Inference is explicitly labeled `Inference unchanged: left only`.

## Approved V1 Delta Only

The green dashed region is a single project-owned, training-only delta:

1. `Synchronized right observation (train target)` is a separate visual target and has no edge into DINOv2, Stage 1, or conditioning.
2. `Calibrated T_R<-L` and `Fixed right camera E_R, K_R` use fixed-geometry hexagons; the visible equation is `E_R = T_R<-L E_L`.
3. `One-step clean latent estimate` is a note-shaped deterministic consumer of the existing Stage 2 velocity output; it is not a learned module.
4. The existing `Gaussian Dec.` and `Gaussian Splats` objects are reused, with explicit `Frozen for V1 supervision` and `Reused 3D Gaussians` callouts; no second decoder is introduced.
5. `Render (right camera)` is a separate fixed differentiable consumer using the reused Gaussian output and fixed right-camera metadata.
6. `Rendered right view` and the synchronized right target feed one `Right-view L1 + LPIPS` supervision node.
7. The only backward-only edge returns from the right-view loss to `Geometry & Appearance Flow Model` (existing Stage 2 generation) and is labeled `BACKWARD ONLY` / `gradient stops at Stage 2`.
8. The delta is bracketed as `TRAIN ONLY · PROPOSED / PENDING REVIEW` and carries `DESIGN ONLY / S01 UNVERIFIED / NOT IMPLEMENTED` plus parent candidate lineage.

## Explicitly Excluded

- No `B=0.25 m` or baseline-normalization loss.
- No feature consistency, temporal quartet, historical four-view route, depth/pose supervision, relation head, stereo encoder, right-image encoder, confidence mask, or new learned head.
- No change to the inference API, sampler, Stage 1 camera path, Gaussian decoder weights, renderer parameters, or optimizer ownership.
- No claim that the branch is implemented, that gradients have been verified, that right-view metrics improve, or that physical scale is learned.

## INIT_GATE

```text
Target: CUPID integration candidate v03; PPT unchanged
Gate: CUPID-SAME-TIME-RIGHT-RECON-V1
Parent: p02_cupid_repro_paper_pipeline_v02_candidate.drawio
Insertion source: docs/CUPID_STEREO_INSERTION_SPEC_V1.md @ 1d3d9af
Change budget: one same-time right-view reconstruction branch/loss
Approval state: parent and candidate are NOT USER-APPROVED
```

`INIT_GATE=PASS`

## PRE_EDIT_GATE

- Source/target contract: Stage 2 velocity -> one-step clean latent -> frozen Gaussian decoder/3D Gaussians -> fixed right-camera render -> right-view L1 + LPIPS -> Stage 2 only.
- Camera contract: `T_R<-L` is fixed rig geometry and `E_R = T_R<-L E_L`; `E_R`, `K_R` do not receive gradient.
- Data contract is represented as design labels only; no random alternate view is presented as a stereo pair.
- Semantic shapes: fixed geometry = hexagon, deterministic clean-latent estimate = note, renderer = rounded consumer, loss = ellipse, target/prediction = framed visual examples.
- Terminology uses the exact V1 visible labels from Section 13 of the spec.

`PRE_EDIT_GATE=PASS`

## POST_RENDER_GATE

### Source And Export Checks

- Draw.io source parses successfully with `xmllint`.
- Candidate contains 181 cells: 141 vertices and 38 edges; 39 vertices and 12 edges are v03-prefixed delta objects.
- No `shape=image` cell and no Base64 `data:image` payload exist.
- Parent comparison: all 130 v02 cells are present and the normalized baseline object contract has zero changed IDs.
- Full export: `1686 x 1124` PNG.
- Full-size render inspected for clipped labels, missing connectors, and delta readability.

### Semantic Checks

- `Synchronized right observation (train target)` connects only to `Right-view L1 + LPIPS`.
- Fixed camera metadata connects to `Render (right camera)` only.
- Reused Gaussian output connects to `Render (right camera)`; no duplicate decoder is present.
- The backward-only gradient route terminates at the existing Stage 2 flow model and does not point to Stage 1, DINOv2, camera metadata, or frozen decoder weights.
- Inference remains explicitly left-only.
- Forbidden V1 alternatives are absent from source text.
- Visible diagram text is English-only.

```text
FIGURE_RULE_AUDIT=PASS
DRAWIO_SOURCE_VERIFIED=YES
ENGLISH_ONLY=YES
PIPELINE_ONLY=YES
TERMINOLOGY_VERIFIED=YES
PARENT_INHERITANCE_VERIFIED=YES
BASELINE_OBJECT_CONTRACT_UNCHANGED=YES
RIGHT_TARGET_ROUTING_VERIFIED=YES
CAMERA_FIXED_GEOMETRY_VERIFIED=YES
GRADIENT_BOUNDARY_VERIFIED=YES
APPROVED_BACKUP_STATUS=PENDING
FIGURE_EDIT_RELEASE=YES
SLIDES_EMBED_RELEASE=NO
```

`POST_RENDER_GATE=PASS`

## Human Review Still Required

1. Confirm the exact visual placement and terminology of the V1 delta against the intended teacher-facing story.
2. Confirm that baseline v02 and this v03 candidate are acceptable mother/integration diagrams.
3. Only after explicit user approval may an `_approved` copy or figure-authority manifest entry be created.
4. Implementation and cluster smoke remain separate future gates; this candidate does not authorize code changes or claims of scientific evidence.
