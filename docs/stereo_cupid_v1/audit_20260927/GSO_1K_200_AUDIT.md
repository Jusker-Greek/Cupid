# GSO_1K_200 population and provenance audit (2026-09-27)

The single Panda pair is a smoke-test input. The intended large stereo source is
`/public/home/ricky/DATASET/GSO_1K_200`. This audit measures available assets;
it does not certify the stereo training target or release a long training job.

The full inventory ran as Slurm CPU job `322841` on `server01`, `COMPLETED 0:0`,
from commit `7e36546985d3743dcb3cff6a8678a2fc40e0aa91`, tree
`30f8b2d1d681695b0e5a5bd9b941015f2342ec78`. Its
[receipt](STEREO_GSO_POPULATION_7E36546_A3/receipt.json) has SHA256
`0f65bb7a1865a8cf87e45b59fc48ea55cd4e262884b4ee5272501f003878a248`.
The scan walks every top-level object and trajectory, intersects numeric stems
across left/right PNG, left/right NPY and HDF5, and checks metadata. It does
not decode every one of the 1.7M frame candidates. It samples the first
complete frame of the first and last trajectory of 65 regularly spaced objects.

| Measurement | Result | Meaning |
| --- | ---: | --- |
| Object directories | 903 | 902 have at least one five-asset frame; one has none |
| Nonempty Gazebo `meshes/model.obj` | 903 | File existence/size, not a full mesh parse or source-equivalence proof |
| Trajectory directories | 173,480 | Strongly correlated within each object |
| Readable trajectory metadata | 173,433 | 47 lack readable metadata |
| Frame stems present in at least one asset type | 1,734,379 | File-level denominator |
| Five-asset frame intersections | 1,734,346 | Candidate stereo pairs, not verified GT targets |
| Missing-asset frame stems | 33 | Across six objects |
| Empty trajectories | 41 | One object has no usable paired frame |

The earlier registry's 1,025 planned object records were not a completed
object count. This directory currently has 903 object identities, and the
1,734,346 frame pairs cannot be treated as 1,734,346 independent 3D objects.
Training/evaluation splits must be by object ID.

The task-allocation README under
`/public/home/ricky/CODE/GSO_dataset/task_allocations/GSO_1K_200` describes
a plan for 1,000 objects and 200 trajectories per object (200,000 planned
trajectories). It is not an existing frozen 1,000-pair manifest. A bounded
search of the known GSO allocation and result roots did not locate a separate
manifest proving the claimed earlier 1,000 rendered pairs; this does not
prove absence elsewhere.

To provide a reviewable candidate, Slurm CPU job `323055` on `server01`,
`COMPLETED 0:0`, selected one content-readable pair per object and then a
second, distinct-trajectory pair from 98 objects chosen by stable
`SHA256(object_id)` order. The new [1K candidate receipt](STEREO_GSO_1K_CANDIDATE_5D0F740_A1/receipt.json)
has SHA256 `6e00f17e7bd80eed4edce89dd3885422eee2e046237bbcf27306eda1aeb7bcd9`;
its [immutable pair list](STEREO_GSO_1K_CANDIDATE_5D0F740_A1/pairs.jsonl)
has SHA256 `1a6ff1ce42ce230c60b3c07789620c322b2beec5cc09dd24aac4e61d51ac725a`.
It contains exactly 1,000 readback-checked pairs across 902 distinct objects:
809 train pairs/733 train objects, 93 validation pairs/81 validation objects,
and 98 test pairs/88 test objects. The split uses the existing
`STEREO_CUPID_STAGE1_TRAIN_V1` object-ID hash policy; no object is assigned
to multiple splits. The list is labeled `CANDIDATE_ONLY` and
`training_target_ready=false`; it is not the unlocated historical 1K subset
and contains no accepted canonical occupancy or CV geometry target.

The sample content audit decoded 126 frames. Four other HDF5 reads initially
failed with `errno 37: No locks available`, an NFS locking failure. A separate
Slurm CPU job `322940` on `server01`, `COMPLETED 0:0`, used
`HDF5_USE_FILE_LOCKING=FALSE` and retried exactly those four immutable inputs;
all four decoded successfully. Its [receipt](STEREO_GSO_HDF5_RETRY_D4D34B3_A1/receipt.json)
has SHA256 `5bd861c84f68ba3cd7dac9db116e8799ea98b00d8b4a061721e14b5aed7fd8f4`.
Thus 130/130 selected pairs have readable 512x512 RGBA left/right images,
3x4 finite saved matrices, two 512x512 depth planes with positive foreground
depth, and HDF5 colors equal to the PNG pixels. This is a bounded sample, not
a full-content verification of all candidate pairs.

All 130 sampled saved left and right camera matrices have a rotation-block
determinant near **-1**. They cannot be used directly as proper CV extrinsics.
`cupid/datasets/stereo_gso.py` derives K from FOV only as a hypothesis and
keeps `calibration_verified=False` and `training_target_ready=False`. The
prior bounded target audit also found 20/20 GSO pairs content-readable but
0/20 valid targets. The external blocker audit lacks accepted asset-to-canonical
axis/scale mapping, pinned official occupancy/voxelizer provenance, and
per-pair proper canonical-to-CV extrinsics plus K/depth/crop/source binding.
The latest independent external blocker job `316398` completed successfully,
but its `EXTERNAL_BLOCKER_RECEIPT.json` (SHA256
`96e107167dc1b107dab2b421cb2b17b0e4496f66e4536700822013ce7b4e3939`)
still reports `EXTERNAL_BLOCKED`, `target_ready=false`. Its asset mapping
receipt hashes the source mesh and renderer, while `canonical_frame`, axis map,
and scale/offset remain null. No GT occupancy or scientific claim follows from
these file counts or the new 1K candidate list.

For comparison, the existing original CUPID reproduction launcher defaults
to `/data/group_gao/trellis/HSSD` (`scripts/submit_cupid_gl_full.sh`, line 22),
and the historically checked original HSSD run was job `296164`. The published
[CUPID supplement](https://openaccess.thecvf.com/content/CVPR2026/supplemental/Huang_CUPID_Generative_3D_CVPR_2026_supplemental.pdf)
lists ABO, HSSD, 3D-FUTURE and a subset of Objaverse-XL as
its training assets, rather than this GSO stereo directory. The local
`GSO_1K_200` directory is a rendered stereo derivative keyed to Gazebo GSO
mesh names. To compare the 3D assets against the separate shared
`/data/group_gao/trellis/GSO_mesh/gso_models` copy, Slurm CPU job `322965`
hashed all 903 inventoried Gazebo `model.obj` files and their shared-copy
counterparts. Its [receipt](STEREO_GSO_MESH_COPY_CBBB5E5_A1/receipt.json)
has SHA256 `e00f28c89068ff4faf1cd774e25fc34dd95948fdeec1dd7f45dd77f10968d549`.
For 901 objects, both OBJ files exist and are byte-for-byte identical. The
shared copy lacks the two `Pokémon_Omega_Ruby_Alpha_Sapphire_Dual_Pack_Nintendo_3DS`
and `Pokémon_Yellow_Special_Pikachu_Edition_Nintendo_Game_Boy_Color` OBJ files.
Thus the mesh copies substantially overlap but are not identical complete
directories. Identical OBJ bytes do not by themselves verify the
asset-to-canonical mapping or match a particular historical training manifest.
If “Qubit” names a different experiment, its exact dataset manifest/checkpoint
is still needed for an identity comparison.

Source code: `scripts/stereo_gso_population_audit.py`,
`scripts/stereo_gso_retry_lock_failures.py`,
`scripts/stereo_gso_mesh_copy_audit.py`,
`scripts/stereo_gso_freeze_1k_candidate.py`, and
`cupid/datasets/stereo_gso.py`. Original inventory artifacts are preserved
in the linked receipt directories above.
