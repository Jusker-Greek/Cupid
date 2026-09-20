#!/usr/bin/env python3
"""Invoke exact official TRELLIS voxelizer on a verified canonical mesh (CPU)."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.datasets.stereo_gso import sha256_file

UPSTREAM_COMMIT = '442aa1e1afb9014e80681d3bf604e8d728a86ee7'
VOXELIZER_BLOB = '390575ab9e26e73b467151dadc8252eae3c96424'


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--voxelizer', required=True, help='Existing official dataset_toolkits/voxelize.py')
    parser.add_argument('--canonical-mesh', required=True, help='Verified canonical mesh.ply')
    parser.add_argument('--provenance', required=True, help='Mesh/canonical mapping receipt JSON')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        parser.error('Slurm compute allocation required')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    receipt = {'schema':'STEREO_GSO_OCCUPANCY_V1', 'job_id':os.environ['SLURM_JOB_ID'],
               'status':'RUNNING', 'upstream_commit':UPSTREAM_COMMIT,
               'voxelizer_git_blob':VOXELIZER_BLOB, 'scientific_evidence':False}
    try:
        source = Path(args.voxelizer).read_bytes()
        blob = hashlib.sha1(b'blob '+str(len(source)).encode()+b'\0'+source).hexdigest()
        if blob != VOXELIZER_BLOB:
            raise ValueError('voxelizer differs from pinned official Git blob')
        provenance = json.loads(Path(args.provenance).read_text())
        if provenance.get('canonical_mapping_verified') is not True or not provenance.get('canonical_mapping_evidence'):
            raise ValueError('canonical mapping requires verification and evidence')
        if not provenance.get('canonical_frame') or not provenance.get('asset_sha256'):
            raise ValueError('canonical frame/asset provenance missing')
        mesh = Path(args.canonical_mesh).resolve()
        mesh_hash = sha256_file(mesh)
        if mesh_hash != provenance['canonical_mesh_sha256']:
            raise ValueError('canonical mesh hash mismatch')
        receipt.update(mesh_sha256=mesh_hash, provenance=provenance,
                       provenance_sha256=sha256_file(args.provenance))
        spec = importlib.util.spec_from_file_location('stereo_official_voxelizer', args.voxelizer)
        official = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(official)
        # Check input bounds before the upstream boundary epsilon clip can conceal
        # an incorrect coordinate mapping. 1e-6 only allows float serialization.
        parsed_mesh = official.o3d.io.read_triangle_mesh(str(mesh))
        xyz = np.asarray(parsed_mesh.vertices)
        if not len(parsed_mesh.triangles) or not len(xyz) or not np.isfinite(xyz).all():
            raise ValueError('canonical mesh must have finite vertices and triangles')
        if (xyz < -.5-1e-6).any() or (xyz > .5+1e-6).any():
            raise ValueError('canonical mesh is outside official unit cube')
        stage = output/'renders'/mesh_hash
        stage.mkdir(parents=True)
        (stage/'mesh.ply').symlink_to(mesh)
        (output/'voxels').mkdir()
        official._voxelize(None, mesh_hash, str(output))
        voxel_path = output/'voxels'/(mesh_hash+'.ply')
        positions = official.utils3d.io.read_ply(str(voxel_path))[0]
        indices = ((np.asarray(positions)+.5)*64).astype(np.int64)
        if indices.ndim != 2 or indices.shape[1] != 3 or not len(indices) or (indices < 0).any() or (indices >= 64).any():
            raise ValueError('official voxelizer produced invalid coordinates')
        occupancy = np.zeros((1,64,64,64),dtype=np.uint8)
        occupancy[0,indices[:,0],indices[:,1],indices[:,2]] = 1
        with (output/'occupancy.npy').open('xb') as handle:
            np.save(handle,occupancy,allow_pickle=False)
        receipt.update(status='COMPLETED', occupancy_npy='occupancy.npy',
                       occupancy_sha256=sha256_file(output/'occupancy.npy'),
                       voxel_ply_sha256=sha256_file(voxel_path), occupied_voxels=int(occupancy.sum()))
    except Exception as exc:
        receipt.update(status='FAILED',error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        (output/'occupancy_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt,indent=2))


if __name__ == '__main__':
    main()
