#!/usr/bin/env python3
"""Prepare provenance-bound dense targets for the 184-pair GSO 1K increment."""
from __future__ import annotations

import argparse
import hashlib
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
from stereo_gso_empirical_target_pilot import (CAMERA_TO_CV, FRAME, IMPORT, MIRROR,
                                               obj_bounds, write_json)


def read_jsonl(path):
    with Path(path).open() as handle:
        return [json.loads(line) for line in handle]


def scores_pass(scores):
    return all(isinstance(side['bbox_mean_abs_error_px'], (int, float)) and
               np.isfinite(side['bbox_mean_abs_error_px']) and side['front_fraction'] >= .99 and
               side['projected_in_image'] >= 100 and side['mask_hit_fraction'] >= .90 and
               side['bbox_mean_abs_error_px'] <= 5. for side in scores.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('selection_root', 'geometry_inventory', 'root', 'asset_root', 'voxelizer', 'output'):
        parser.add_argument('--' + name.replace('_', '-'), required=True)
    parser.add_argument('--shard-index', type=int, required=True)
    parser.add_argument('--shard-count', type=int, required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        parser.error('Slurm allocation and valid shard position required')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    selection_root = Path(args.selection_root)
    selection_path = selection_root / 'receipt.json'
    manifest_path = selection_root / 'increment_manifest.jsonl'
    scores_path = selection_root / 'increment_scores.jsonl'
    selection = json.loads(selection_path.read_text())
    if selection['status'] != 'CANDIDATE_1K_PAIR_SET_FROZEN' or selection['job_id'] != '326956':
        raise ValueError('expected exact frozen 1K selection')
    if (sha256_file(manifest_path) != selection['output_sha256']['increment_manifest'] or
            sha256_file(scores_path) != selection['output_sha256']['increment_scores']):
        raise ValueError('increment manifest/scores hash mismatch')
    records = read_jsonl(manifest_path)
    score_rows = read_jsonl(scores_path)
    scores = {item['pair_id']: item['scores'] for item in score_rows}
    if len(records) != 184 or len(scores) != 184 or len(score_rows) != 184:
        raise ValueError('expected exactly 184 unique increment records/scores')
    source_sha = {'selection_receipt': sha256_file(selection_path),
                  'increment_manifest': sha256_file(manifest_path),
                  'increment_scores': sha256_file(scores_path),
                  'geometry_inventory': sha256_file(args.geometry_inventory)}
    if source_sha['geometry_inventory'] != 'abf8e3bce87845b9cb0651e98e15a3a8cfa106e4eb7ce637d4c6750b1236ca92':
        raise ValueError('geometry inventory changed')
    inventory = {item['object_id']: item for item in read_jsonl(args.geometry_inventory)}
    selected = records[args.shard_index::args.shard_count]
    if not selected:
        raise ValueError('empty increment shard')
    shard_manifest = output / 'shard_manifest.jsonl'
    shard_manifest.write_text(''.join(json.dumps(row) + '\n' for row in selected))
    geometry = output / 'geometry'
    geometry.mkdir()
    occupancy_root = output / 'occupancy'
    occupancy_root.mkdir()
    entries = []
    repo = Path(__file__).resolve().parents[1]
    for row in selected:
        pair_id, object_id = row['pair_id'], row['object_id']
        pack = load_pair(row, args.root, hash_assets=True)
        if pack['asset_sha256'] != row['asset_sha256']:
            raise ValueError('source pair asset changed: ' + pair_id)
        candidate = inventory[object_id]
        if candidate.get('status') != 'UNVERIFIED_GEOMETRY_CANDIDATE' or candidate.get('error'):
            raise ValueError('invalid geometry inventory item: ' + pair_id)
        mesh_path = confined_path(args.asset_root, object_id + '/meshes/model.obj')
        mesh_hash = sha256_file(mesh_path)
        if mesh_hash != candidate['asset']['sha256']:
            raise ValueError('source mesh changed: ' + pair_id)
        view_scores = scores[pair_id]
        if not scores_pass(view_scores):
            raise ValueError('pair no longer satisfies fixed projection gate: ' + pair_id)
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        raw = np.asarray(mesh.vertices)
        if not len(raw) or not len(np.asarray(mesh.triangles)) or not np.isfinite(raw).all():
            raise ValueError('invalid source OBJ mesh: ' + pair_id)
        if not np.allclose(np.asarray([raw.min(0), raw.max(0)]), obj_bounds(mesh_path), atol=1e-6):
            raise ValueError('Open3D OBJ bounds differ from source: ' + pair_id)
        scale = float(row['normalization']['scale'])
        offset = np.asarray(row['normalization']['offset'], dtype=np.float64)
        render = (IMPORT @ raw.T).T * scale + offset
        canonical = (MIRROR[:3, :3] @ render.T).T
        if (canonical < -.5-1e-6).any() or (canonical > .5+1e-6).any():
            raise ValueError('canonical mesh outside official unit cube: ' + pair_id)
        mesh.vertices = o3d.utility.Vector3dVector(canonical)
        slug = hashlib.sha256(pair_id.encode()).hexdigest()[:24]
        subdir = geometry / slug
        subdir.mkdir()
        canonical_mesh = subdir / 'mesh.ply'
        if not o3d.io.write_triangle_mesh(str(canonical_mesh), mesh, write_ascii=False):
            raise ValueError('cannot write canonical mesh: ' + pair_id)
        canonical_hash = sha256_file(canonical_mesh)
        raw_to_canonical = np.eye(4)
        raw_to_canonical[:3, :3] = MIRROR[:3, :3] @ IMPORT * scale
        raw_to_canonical[:3, 3] = MIRROR[:3, :3] @ offset
        evidence = {'selection_receipt_sha256': source_sha['selection_receipt'],
                    'increment_scores_sha256': source_sha['increment_scores'],
                    'geometry_inventory_sha256': source_sha['geometry_inventory'],
                    'allpair_projection_receipt_sha256': selection['source_sha256']['allpair_receipt'],
                    'replacement_mapping_sha256': selection['source_sha256']['replacement_map'],
                    'pair_view_scores': view_scores,
                    'empirical_not_historical_renderer_identity': True}
        mapping = {'schema': 'STEREO_GSO_EMPIRICAL_CANONICAL_MAPPING_V1',
                   'verification_scope': 'this source mesh and the selected pair',
                   'canonical_mapping_verified': True, 'canonical_mapping_evidence': evidence,
                   'canonical_frame': FRAME, 'asset_sha256': mesh_hash,
                   'canonical_mesh_sha256': canonical_hash,
                   'raw_obj_to_canonical': raw_to_canonical.tolist(),
                   'historical_renderer_exact_revision_verified': False,
                   'unit': 'scene_unit', 'metric_meters_verified': False}
        mapping_path = subdir / 'mapping_receipt.json'
        write_json(mapping_path, mapping)
        occupancy_output = occupancy_root / slug
        subprocess.run([sys.executable, str(repo / 'scripts/stereo_data_occupancy.py'),
                        '--voxelizer', args.voxelizer, '--canonical-mesh', str(canonical_mesh),
                        '--provenance', str(mapping_path), '--output', str(occupancy_output)], check=True)
        occupancy_receipt = json.loads((occupancy_output / 'occupancy_receipt.json').read_text())
        if occupancy_receipt['status'] != 'COMPLETED':
            raise ValueError('official occupancy did not complete: ' + pair_id)
        baseline = float(row['metadata']['baseline'])
        shift = np.eye(4)
        shift[0, 3] = -baseline / 2
        cameras, Ks, sizes, crops = [], [], [], []
        for side in ('left', 'right'):
            view = pack['views'][side]
            w2c_cv = CAMERA_TO_CV @ shift @ view['w2c_saved'] @ MIRROR
            rotation = w2c_cv[:3, :3]
            if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5) or not np.isclose(np.linalg.det(rotation), 1, atol=1e-5):
                raise ValueError('empirical camera not proper CV: ' + pair_id)
            height, width = view['rgba'].shape[:2]
            cameras.append(w2c_cv.tolist())
            Ks.append(view['K_fullpixel'].tolist())
            sizes.append([width, height])
            crops.append([0, 0, width, height])
        geom = {'schema': 'STEREO_GSO_GEOMETRY_V1', 'pair_id': pair_id,
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
        entries.append({'pair_id': pair_id, 'receipt': str(receipt_path.relative_to(output)),
                        'receipt_sha256': sha256_file(receipt_path)})
        print(json.dumps({'pair_id': pair_id, 'occupancy_sha256': occupancy_receipt['occupancy_sha256']}), flush=True)
    geometry_index = output / 'geometry_index.jsonl'
    geometry_index.write_text(''.join(json.dumps(entry) + '\n' for entry in entries))
    subprocess.run([sys.executable, str(repo / 'scripts/stereo_data_targets.py'),
                    '--manifest', str(shard_manifest), '--root', args.root,
                    '--geometry-index', str(geometry_index), '--geometry-root', str(output),
                    '--output', str(output / 'targets')], check=True)
    summary_path = output / 'targets/summary.json'
    summary = json.loads(summary_path.read_text())
    if summary['counts'] != {'prepared': len(selected), 'failed': 0} or summary['missing_geometry_pairs']:
        raise ValueError('increment shard target generation incomplete')
    receipt = {'schema': 'STEREO_GSO_1K_INCREMENT_TARGET_SHARD_V1', 'status': 'SHARD_TARGETS_PREPARED',
               'job_id': os.environ['SLURM_JOB_ID'], 'host': socket.gethostname(),
               'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
               'shard_index': args.shard_index, 'shard_count': args.shard_count, 'pairs': len(selected),
               'source_sha256': source_sha,
               'shard_manifest_sha256': sha256_file(shard_manifest),
               'geometry_index_sha256': sha256_file(geometry_index),
               'target_index_sha256': sha256_file(output / 'targets/targets.jsonl'),
               'target_summary_sha256': sha256_file(summary_path),
               'canonical_frame': FRAME, 'historical_renderer_exact_revision_verified': False,
               'original_cupid_canonical_equivalence_verified': False,
               'scientific_evidence': False}
    write_json(output / 'shard_receipt.json', receipt)
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
