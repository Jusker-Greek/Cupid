#!/usr/bin/env python3
"""Build two provenance-bound GSO targets in an explicitly new mirrored frame.

The transform is tested against the frozen images; it is not asserted to be the
historical renderer revision or the original CUPID/TRELLIS canonical frame.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import numpy as np
import open3d as o3d

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.datasets.stereo_gso import confined_path, load_pair, sha256_file


OBJECTS = ('30_CONSTRUCTION_SET', '45oz_RAMEKIN_ASST_DEEP_COLORS')
HYPOTHESIS = 'blender_obj_import_hypothesis/+--/saved_x_shift_-0.5B'
FRAME = 'GSO_STEREO_MIRRORED_RENDER_UNIT_CUBE_V1'
IMPORT = np.asarray([[1., 0., 0.], [0., 0., -1.], [0., 1., 0.]])
MIRROR = np.diag([1., -1., 1., 1.])
CAMERA_TO_CV = np.diag([1., -1., -1., 1.])


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def obj_bounds(path):
    vertices = []
    with path.open() as handle:
        for line in handle:
            if line.startswith('v '):
                vertices.append([float(value) for value in line.split()[1:4]])
    array = np.asarray(vertices, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3 or not len(array) or not np.isfinite(array).all():
        raise ValueError('OBJ has no finite vertices')
    return np.asarray([array.min(0), array.max(0)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--asset-root', required=True)
    parser.add_argument('--geometry-inventory', required=True)
    parser.add_argument('--warp-receipt', required=True)
    parser.add_argument('--projection-receipt', required=True)
    parser.add_argument('--projection-objects', required=True)
    parser.add_argument('--voxelizer', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        parser.error('Slurm compute allocation required')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    source_hashes = {name: sha256_file(getattr(args, name)) for name in
                     ('manifest', 'geometry_inventory', 'warp_receipt',
                      'projection_receipt', 'projection_objects')}
    warp = json.loads(Path(args.warp_receipt).read_text())
    projection = json.loads(Path(args.projection_receipt).read_text())
    if warp['job_id'] != '326654' or projection['job_id'] != '326774':
        raise ValueError('expected exact frozen diagnostic jobs')
    if warp['manifest_sha256'] != source_hashes['manifest'] or projection['manifest_sha256'] != source_hashes['manifest']:
        raise ValueError('diagnostic manifest identity differs')
    inventory = {item['object_id']: item for item in map(json.loads, Path(args.geometry_inventory).open())}
    projected = {item['object_id']: item for item in json.loads(Path(args.projection_objects).read_text())}
    records = {}
    with Path(args.manifest).open() as handle:
        for line in handle:
            record = json.loads(line)
            if record['object_id'] in OBJECTS and record['object_id'] not in records:
                records[record['object_id']] = record
    if set(records) != set(OBJECTS) or records[OBJECTS[0]]['split'] != 'train' or records[OBJECTS[1]]['split'] != 'validation':
        raise ValueError('pilot identities or object splits changed')
    (output / 'pilot_manifest.jsonl').write_text(''.join(json.dumps(records[name]) + '\n' for name in OBJECTS))
    geometry = output / 'geometry'
    geometry.mkdir()
    occupancy_root = output / 'occupancy'
    occupancy_root.mkdir()
    entries = []
    for name in OBJECTS:
        record = records[name]
        pack = load_pair(record, args.root, hash_assets=True)
        if pack['asset_sha256'] != record['asset_sha256']:
            raise ValueError('pair source asset hash changed: ' + name)
        candidate = inventory[name]
        if candidate.get('status') != 'UNVERIFIED_GEOMETRY_CANDIDATE' or candidate.get('error'):
            raise ValueError('geometry inventory candidate invalid: ' + name)
        mesh_path = confined_path(args.asset_root, name + '/meshes/model.obj')
        mesh_hash = sha256_file(mesh_path)
        if mesh_hash != candidate['asset']['sha256'] or mesh_hash != projected[name]['mesh_sha256']:
            raise ValueError('mesh identity changed: ' + name)
        if projected[name]['source_asset_sha256'] != pack['asset_sha256']:
            raise ValueError('projection/source hash changed: ' + name)
        view_scores = projected[name]['scores'][HYPOTHESIS]
        if any(not np.isfinite(side['bbox_mean_abs_error_px']) for side in view_scores.values()):
            raise ValueError('nonfinite pixel projection evidence: ' + name)
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        raw = np.asarray(mesh.vertices)
        if not len(raw) or not len(np.asarray(mesh.triangles)) or not np.isfinite(raw).all():
            raise ValueError('mesh vertices or faces invalid: ' + name)
        if not np.allclose(np.asarray([raw.min(0), raw.max(0)]), obj_bounds(mesh_path), atol=1e-6):
            raise ValueError('Open3D OBJ bounds differ from source vertices: ' + name)
        scale = float(record['normalization']['scale'])
        offset = np.asarray(record['normalization']['offset'], dtype=np.float64)
        render = (IMPORT @ raw.T).T * scale + offset
        canonical = (MIRROR[:3, :3] @ render.T).T
        if (canonical < -.5-1e-6).any() or (canonical > .5+1e-6).any():
            raise ValueError('canonical mesh outside official unit cube: ' + name)
        mesh.vertices = o3d.utility.Vector3dVector(canonical)
        subdir = geometry / name
        subdir.mkdir()
        canonical_mesh = subdir / 'mesh.ply'
        if not o3d.io.write_triangle_mesh(str(canonical_mesh), mesh, write_ascii=False):
            raise ValueError('failed to write canonical mesh: ' + name)
        canonical_hash = sha256_file(canonical_mesh)
        raw_to_canonical = np.eye(4)
        raw_to_canonical[:3, :3] = MIRROR[:3, :3] @ IMPORT * scale
        raw_to_canonical[:3, 3] = MIRROR[:3, :3] @ offset
        evidence = {'inventory_index_sha256': source_hashes['geometry_inventory'],
                    'stereo_warp_receipt_sha256': source_hashes['warp_receipt'],
                    'mesh_projection_receipt_sha256': source_hashes['projection_receipt'],
                    'mesh_projection_objects_sha256': source_hashes['projection_objects'],
                    'pair_view_scores': view_scores,
                    'holdout_objects': projection['objects'],
                    'empirical_not_historical_renderer_identity': True}
        mapping = {'schema': 'STEREO_GSO_EMPIRICAL_CANONICAL_MAPPING_V1',
                   'verification_scope': 'this source mesh and the selected frozen stereo pair',
                   'canonical_mapping_verified': True, 'canonical_mapping_evidence': evidence,
                   'canonical_frame': FRAME, 'asset_sha256': mesh_hash,
                   'canonical_mesh_sha256': canonical_hash,
                   'raw_obj_to_canonical': raw_to_canonical.tolist(),
                   'historical_renderer_exact_revision_verified': False,
                   'unit': 'scene_unit', 'metric_meters_verified': False}
        mapping_path = subdir / 'mapping_receipt.json'
        write_json(mapping_path, mapping)
        occupancy_output = occupancy_root / name
        subprocess.run([sys.executable, str(repo / 'scripts/stereo_data_occupancy.py'),
                        '--voxelizer', args.voxelizer, '--canonical-mesh', str(canonical_mesh),
                        '--provenance', str(mapping_path), '--output', str(occupancy_output)], check=True)
        occupancy_receipt = json.loads((occupancy_output / 'occupancy_receipt.json').read_text())
        if occupancy_receipt['status'] != 'COMPLETED':
            raise ValueError('official occupancy did not complete: ' + name)
        baseline = float(record['metadata']['baseline'])
        shift = np.eye(4)
        shift[0, 3] = -baseline / 2
        cameras = []
        Ks = []
        sizes = []
        crops = []
        for side in ('left', 'right'):
            view = pack['views'][side]
            w2c_cv = CAMERA_TO_CV @ shift @ view['w2c_saved'] @ MIRROR
            rotation = w2c_cv[:3, :3]
            if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5) or not np.isclose(np.linalg.det(rotation), 1, atol=1e-5):
                raise ValueError('empirical camera does not yield proper CV rotation: ' + name)
            height, width = view['rgba'].shape[:2]
            cameras.append(w2c_cv.tolist())
            Ks.append(view['K_fullpixel'].tolist())
            sizes.append([width, height])
            crops.append([0, 0, width, height])
        geom = {'schema': 'STEREO_GSO_GEOMETRY_V1', 'pair_id': record['pair_id'],
                'source_asset_sha256': pack['asset_sha256'],
                'validity': {'canonical_occupancy_verified': True, 'canonical_to_cv_verified': True},
                'provenance': {'canonical_frame': FRAME, 'asset_sha256': mesh_hash,
                               'renderer_provenance': {'current_renderer_sha256': candidate['renderer']['sha256'],
                                                       'historical_exact_revision_verified': False},
                               'geometry_evidence': evidence,
                               'empirical_mapping_receipt_sha256': sha256_file(mapping_path),
                               'official_occupancy_receipt_sha256': sha256_file(occupancy_output / 'occupancy_receipt.json'),
                               'raw_obj_to_canonical': raw_to_canonical.tolist(),
                               'saved_camera_x_shift_baseline_factor': -.5,
                               'camera_axis_to_cv': CAMERA_TO_CV.tolist(),
                               'canonical_world_mirror': MIRROR.tolist(),
                               'metric_meters_verified': False},
                'occupancy_npy': str((occupancy_output / 'occupancy.npy').relative_to(output)),
                'occupancy_sha256': occupancy_receipt['occupancy_sha256'],
                'w2c_cv': cameras, 'K_fullpixel': Ks, 'image_wh': sizes,
                'crop_xyxy': crops, 'const_ssuv': True}
        receipt_path = subdir / 'geometry_receipt.json'
        write_json(receipt_path, geom)
        entries.append({'pair_id': record['pair_id'], 'receipt': str(receipt_path.relative_to(output)),
                        'receipt_sha256': sha256_file(receipt_path)})
    index = output / 'geometry_index.jsonl'
    index.write_text(''.join(json.dumps(entry) + '\n' for entry in entries))
    subprocess.run([sys.executable, str(repo / 'scripts/stereo_data_targets.py'),
                    '--manifest', str(output / 'pilot_manifest.jsonl'), '--root', args.root,
                    '--geometry-index', str(index), '--geometry-root', str(output),
                    '--output', str(output / 'targets')], check=True)
    target_summary = json.loads((output / 'targets/summary.json').read_text())
    if target_summary['counts'] != {'prepared': 2, 'failed': 0} or target_summary['missing_geometry_pairs']:
        raise ValueError('pilot target generation incomplete')
    receipt = {'schema': 'STEREO_GSO_EMPIRICAL_TARGET_PILOT_V1', 'status': 'TWO_PAIR_TARGETS_PREPARED',
               'job_id': os.environ['SLURM_JOB_ID'], 'host': socket.gethostname(),
               'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
               'source_sha256': source_hashes, 'source_pairs': [records[name]['pair_id'] for name in OBJECTS],
               'pilot_manifest_sha256': sha256_file(output / 'pilot_manifest.jsonl'),
               'geometry_index_sha256': sha256_file(index),
               'target_index_sha256': sha256_file(output / 'targets/targets.jsonl'),
               'target_summary_sha256': sha256_file(output / 'targets/summary.json'),
               'canonical_frame': FRAME, 'historical_renderer_exact_revision_verified': False,
               'original_cupid_canonical_equivalence_verified': False,
               'scope': 'two-pair engineering smoke target; not 1K training readiness',
               'scientific_evidence': False}
    write_json(output / 'pilot_receipt.json', receipt)
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
