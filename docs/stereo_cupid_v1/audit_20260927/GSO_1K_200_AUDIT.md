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
No GT occupancy or scientific claim follows from these file counts.

For comparison, the existing original CUPID reproduction launcher defaults
to `/data/group_gao/trellis/HSSD` (`scripts/submit_cupid_gl_full.sh`, line 22),
and the historically checked original HSSD run was job `296164`. The published
CUPID supplement lists ABO, HSSD, 3D-FUTURE and a subset of Objaverse-XL as
its training assets, rather than this GSO stereo directory. The local
`GSO_1K_200` directory is a rendered stereo derivative keyed to Gazebo GSO
mesh names. Its object IDs and mesh presence establish the GSO family but do
not prove byte identity or canonical-frame equivalence to any separate
historical GSO copy. If “Qubit” names a different experiment, its exact
dataset manifest/checkpoint is still needed for an identity comparison.

Source code: `scripts/stereo_gso_population_audit.py`,
`scripts/stereo_gso_retry_lock_failures.py`, and
`cupid/datasets/stereo_gso.py`. Original inventory artifacts are preserved
in the two linked receipt directories above.
