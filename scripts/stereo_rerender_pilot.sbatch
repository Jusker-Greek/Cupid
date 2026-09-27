#!/usr/bin/env bash
#SBATCH --partition=cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --job-name=cupid_stereo_pilot
set -euo pipefail

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
cd "$REPO_ROOT"
printf 'CHECKOUT %s\n' "$(git rev-parse HEAD)"
printf 'TREE %s\n' "$(git rev-parse HEAD^{tree})"
printf 'NODE %s\n' "$(hostname)"
"$BLENDER" -b --factory-startup -t "$OMP_NUM_THREADS" -P scripts/stereo_rerender_pilot.py -- \
  --dataset HSSD \
  --sha256 001065d01ce8bf908b78a03f32ae36d4e866faee1252ced8488b1225666f7d52 \
  --asset /data/group_gao/trellis/HSSD/raw/objects/3/3e4790548c158671fec162757053201da04b6259.glb \
  --transforms /data/group_gao/trellis/HSSD/renders_cond/001065d01ce8bf908b78a03f32ae36d4e866faee1252ced8488b1225666f7d52/transforms.json \
  --output "$OUTPUT_ROOT/HSSD_001065d0"
"$BLENDER" -b --factory-startup -t "$OMP_NUM_THREADS" -P scripts/stereo_rerender_pilot.py -- \
  --dataset ABO \
  --sha256 0006d4c69de70f84754df85c2ec0a34514223f941500f080c84c19da7e137998 \
  --asset /data/group_gao/trellis/ABO/raw/3/B07YBH2SR3.glb \
  --transforms /data/group_gao/trellis/ABO/renders_cond/0006d4c69de70f84754df85c2ec0a34514223f941500f080c84c19da7e137998/transforms.json \
  --output "$OUTPUT_ROOT/ABO_0006d4c6"
