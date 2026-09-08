# CUPID Figure 3 Editable Mother Candidate Audit

Status: `CANDIDATE / NOT USER-APPROVED`

Date: 2026-09-08

## Scope

- Target slide(s): P02 dependency candidate only. No PPT/PPTX file was modified.
- Experiment group: CUPID original-paper baseline reconstruction.
- Figure role: first editable mother diagram for the CUPID baseline.
- Sole implementation delta: replace the v01 single embedded raster cell with native Draw.io objects while preserving Figure 3 semantics.
- Scientific delta: none.

## Primary Authority And Provenance

- Sole semantic authority: CUPID paper, Figure 3, arXiv:2510.20776.
- Paper URL: <https://arxiv.org/abs/2510.20776>
- Downloaded paper PDF SHA256: `557d810eb2ffe4608606fcf7c53db093bda2494763327db23772c1add05a4bd0`.
- Figure 3 caption contract: single-view input; occupancy and UV cube generation in canonical space; PnP camera recovery; pose-aligned conditioning with noisy structured latents; geometry and appearance generation; Gaussian splat and mesh decoding.
- Official code authority: `cupid3d/Cupid` main commit `10af9b26f9e1b55c54892dc35acb997b1c6b6bf2`.
- Official code evidence:
  - `cupid/pipelines/processing.py:86` names DINOv2 image conditioning.
  - `cupid/pipelines/processing.py:142` decodes UV sparse tensors into camera poses.
  - `cupid/pipelines/processing.py:181` decodes sparse structure and UV outputs.
  - `cupid/pipelines/pipeline.py:305` executes stage 1 structure and pose prediction.
  - `cupid/pipelines/pipeline.py:312` executes stage 2 structured-latent sampling.
  - `cupid/pipelines/pipeline.py:324` returns pose plus decoded output formats.
  - `cupid/models/structured_latent_flow.py:494` samples pose-aligned visual features through UV coordinates.
  - `cupid/models/structured_latent_flow.py:528` fuses DINO, visual and structured-latent features.

## Direct Parent Candidate

- Parent path: `/Users/ruikegu/.codex/worktrees/5c44/Cupid/outputs/figures/p02_cupid_repro_paper_pipeline_v01_candidate.drawio`.
- Parent SHA256: `bfb0f0f9c65bc583011fe5d8d8b84443def5f9c4e6ab557d3e230458b43b2f28`.
- Parent structure: one Draw.io image cell containing the complete Figure 3 raster.
- Preserved reference image: `outputs/figures/paper_figure3_original.png`.
- Reference image SHA256: `eca27971013150c77b06921f041666bca2d4839b4665542dab09206887d21dcd`.
- Limitation: the parent preserves pixels but exposes no editable pipeline objects or connectors.

## INIT_GATE

```text
Target slide(s): P02 candidate dependency; PPT unchanged
Experiment group: CUPID original-paper baseline
Reviewed mother diagram: CUPID paper Figure 3; primary-source semantic mother
Direct parent diagram: p02_cupid_repro_paper_pipeline_v01_candidate.drawio
Editable .drawio source: outputs/figures/p02_cupid_repro_paper_pipeline_v02_candidate.drawio
Sole local delta: raster-only parent -> native editable Draw.io objects
Terminology source: paper Figure 3/main text and official code at 10af9b2
File/worktree ownership: clean dedicated worktree; new output paths only
```

`INIT_GATE=PASS`

Rationale: no reviewed editable CUPID mother existed. The task explicitly authorizes creating the first editable candidate with Figure 3 as the only semantic authority.

## PRE_EDIT_GATE

### Terminology Register

| Figure concept | Visible English name |
| --- | --- |
| Input | `Single-view Input`, `Icond` |
| Image encoder | `DINOv2` |
| Stage 1 region | `Occupancy & Pose Generation` |
| Stage 1 generator | `Occupancy & Pose Flow Model` |
| Stage 1 decoders | `Occupancy Dec.`, `UV Cube Dec.` |
| Stage 1 outputs | `Occupancy Cube`, `UV Cube` |
| Pose recovery | `PnP` |
| Stage 2 latent | `Structured Latent` |
| Pose-aligned fusion | `Conditioner`, `Pose-aligned Cond.` |
| Stage 2 region | `Pose-aligned Geometry & Appearance Generation` |
| Stage 2 generator | `Geometry & Appearance Flow Model` |
| Output decoders | `Gaussian Dec.`, `Mesh Dec.` |
| Outputs | `Gaussian Splats`, `Mesh` |
| Global image features | `Attention-based Cond.` |

### Preserved Route Inventory

1. Single-view input to DINOv2.
2. DINOv2 attention-based conditioning to the stage 1 flow model.
3. Stage 1 flow model to Occupancy Decoder to Occupancy Cube.
4. Stage 1 flow model to UV Cube Decoder to UV Cube.
5. Occupancy Cube to noisy Structured Latent support.
6. UV Cube through PnP to the recovered camera and input-image projection view.
7. Structured Latent and the pose-aligned image view to Conditioner.
8. Conditioner to the stage 2 flow model.
9. DINOv2 conditioning bus to Conditioner and the stage 2 flow model.
10. Stage 2 flow model to Gaussian Decoder to Gaussian Splats.
11. Stage 2 flow model to Mesh Decoder to Mesh.

- New project-owned module names: none.
- `NEW_MODULE_NAME_APPROVAL=NOT_REQUIRED`
- Candidate source path: `outputs/figures/p02_cupid_repro_paper_pipeline_v02_candidate.drawio`.
- Candidate export path: `outputs/figures/p02_cupid_repro_paper_pipeline_v02_candidate.png`.
- Approved backup path: intentionally unset until explicit user approval.

`PRE_EDIT_GATE=PASS`

## POST_RENDER_GATE

### Source And Export Checks

- Draw.io source parses successfully with `xmllint`.
- Source contains 130 Draw.io cells, including 102 editable vertices and 26 editable edges.
- Source contains no `shape=image` cell and no `data:image` payload.
- Every pipeline module, connector, label, cube, camera/frustum cue and output schematic is independently selectable and editable.
- Full export: 3322 x 1162 PNG.
- Projection-size preview: 1600 x 559 PNG, reviewed separately as a temporary QA artifact.
- Full-size and projection-size renders show no clipped module label, broken connector, missing output branch or overlapping output caption.
- Figure source SHA256: `b8e50697e92e25edb96be05c08f96fffd22b91c5f795fbd36923f710480ecdab`.
- PNG export SHA256: `7378e51d6b79a3be1272d584415a1c6996b3b3a5202eac865590b737ecd0e7c0`.

### Seven-Rule Audit

- Editable source: PASS. The `.drawio` file is the only editing authority.
- English-only visible text: PASS. No Chinese or bilingual diagram text exists.
- Graphic language: PASS. Short labels accompany native modules, cubes, camera/frustum cues and output objects; no explanatory paragraph exists inside the figure.
- Naming authority: PASS. All visible module and route names come from Figure 3 or official code.
- Pipeline-only boundary: PASS. The file contains no slide title, objective, result, risk, takeaway or presenter note.
- Parent inheritance: PASS at the semantic level. The direct parent has no reusable native object set, so the v02 candidate preserves its complete Figure 3 route inventory and visual grouping rather than claiming object-level inheritance.
- Approved freeze: PENDING. The candidate remains mutable until the user explicitly approves it.

```text
FIGURE_RULE_AUDIT=PASS
DRAWIO_SOURCE_VERIFIED=YES
ENGLISH_ONLY=YES
PIPELINE_ONLY=YES
TERMINOLOGY_VERIFIED=YES
PARENT_INHERITANCE_VERIFIED=YES
APPROVED_BACKUP_STATUS=PENDING
FIGURE_EDIT_RELEASE=YES
SLIDES_EMBED_RELEASE=NO
```

`POST_RENDER_GATE=PASS`

`SLIDES_EMBED_RELEASE=NO` records the current task boundary and candidate status. This task did not modify the deck, and no candidate may be described as approved before user review.

## Human Review Still Required

1. Confirm that the vector schematics preserve enough visual resemblance to Figure 3 for teacher-facing use.
2. Confirm the exact placement and reading order of `Structured Latent`, PnP and `Conditioner` at projected size.
3. Decide whether v02 becomes the approved CUPID baseline mother.
4. After explicit approval only, freeze a `_approved.drawio` copy with a matching export and register it in the project figure authority manifest.
