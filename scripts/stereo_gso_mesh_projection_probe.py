#!/usr/bin/env python3
"""Compare candidate OBJ-to-render coordinates against observed alpha silhouettes.

This is a bounded image-geometry diagnostic, not a historical provenance or GT receipt.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.datasets.stereo_gso import confined_path, load_pair, sha256_file


def obj_vertices(path):
    vertices = []
    with path.open() as handle:
        for line in handle:
            if line.startswith('v '):
                vertices.append([float(value) for value in line.split()[1:4]])
    array = np.asarray(vertices, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3 or not len(array) or not np.isfinite(array).all():
        raise ValueError('OBJ has no valid finite vertices: ' + str(path))
    return array


def project_score(points, view, axis):
    height, width = view['mask'].shape
    bounds_y, bounds_x = np.nonzero(view['mask'])
    observed = np.asarray([bounds_x.min(), bounds_y.min(), bounds_x.max() + 1,
                           bounds_y.max() + 1], dtype=np.float64)
    homogeneous = np.concatenate((points, np.ones((len(points), 1))), axis=1)
    camera = (view['w2c_saved'] @ homogeneous.T)[:3] * axis[:, None]
    front = camera[2] > 1e-6
    if not front.any():
        return {'front_fraction': 0., 'projected_in_image': 0, 'mask_hit_fraction': 0.,
                'bbox_mean_abs_error_px': None, 'predicted_bbox': None,
                'observed_bbox': observed.tolist()}
    camera = camera[:, front]
    K = view['K_fullpixel']
    u = K[0, 0] * camera[0] / camera[2] + K[0, 2]
    v = K[1, 1] * camera[1] / camera[2] + K[1, 2]
    finite = np.isfinite(u) & np.isfinite(v)
    u, v = u[finite], v[finite]
    if not len(u):
        raise ValueError('no finite projected vertices')
    predicted = np.asarray([u.min(), v.min(), u.max(), v.max()])
    inside = (u >= 0) & (u < width) & (v >= 0) & (v < height)
    pixel_u = np.clip(np.rint(u[inside]).astype(np.int64), 0, width - 1)
    pixel_v = np.clip(np.rint(v[inside]).astype(np.int64), 0, height - 1)
    mask_hit = float(view['mask'][pixel_v, pixel_u].mean()) if len(pixel_u) else 0.
    return {'front_fraction': float(front.mean()), 'projected_in_image': int(inside.sum()),
            'mask_hit_fraction': mask_hit, 'bbox_mean_abs_error_px': float(np.abs(predicted - observed).mean()),
            'predicted_bbox': predicted.tolist(), 'observed_bbox': observed.tolist()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--asset-root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--max-objects', type=int, default=12)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        parser.error('Slurm compute allocation required')
    if args.max_objects <= 0:
        parser.error('max-objects must be positive')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    results = []
    seen = set()
    totals = defaultdict(lambda: {'views': 0, 'bbox_error_sum': 0., 'mask_hit_sum': 0.,
                                  'front_fraction_sum': 0.})
    with Path(args.manifest).open() as rows:
        for line in rows:
            row = json.loads(line)
            if not row['validity']['content_verified'] or row['object_id'] in seen:
                continue
            if len(results) >= args.max_objects:
                break
            seen.add(row['object_id'])
            mesh = confined_path(args.asset_root, row['object_id'] + '/meshes/model.obj')
            raw = obj_vertices(mesh)
            normalization = row['normalization']
            scale = float(normalization['scale'])
            offset = np.asarray(normalization['offset'], dtype=np.float64)
            if scale <= 0 or offset.shape != (3,) or not np.isfinite(scale) or not np.isfinite(offset).all():
                raise ValueError('invalid normalization: ' + row['pair_id'])
            imported = raw[:, [0, 2, 1]] * np.asarray([1, -1, 1])
            variants = {'gazebo_obj_raw': raw * scale + offset,
                        'blender_obj_import_hypothesis': imported * scale + offset}
            pack = load_pair(row, args.root)
            scores = {}
            for mapping, points in variants.items():
                for sx in (-1, 1):
                    for sy in (-1, 1):
                        for sz in (-1, 1):
                            axis = np.asarray((sx, sy, sz), dtype=np.float64)
                            key = mapping + '/' + ''.join('+' if value > 0 else '-' for value in axis)
                            scores[key] = {side: project_score(points, pack['views'][side], axis)
                                           for side in ('left', 'right')}
                            for side_result in scores[key].values():
                                total = totals[key]
                                total['views'] += 1
                                total['bbox_error_sum'] += (side_result['bbox_mean_abs_error_px']
                                                            if side_result['bbox_mean_abs_error_px'] is not None else 1e6)
                                total['mask_hit_sum'] += side_result['mask_hit_fraction']
                                total['front_fraction_sum'] += side_result['front_fraction']
            results.append({'pair_id': row['pair_id'], 'object_id': row['object_id'],
                            'mesh_sha256': sha256_file(mesh), 'source_asset_sha256': row['asset_sha256'],
                            'scores': scores})
            print(f'OBJECT {len(results)} {row["object_id"]}', flush=True)
    if len(results) != args.max_objects:
        raise ValueError(f'Only {len(results)} distinct content-verified objects found')
    aggregate = [{'key': key, 'views': value['views'],
                  'mean_bbox_abs_error_px': value['bbox_error_sum'] / value['views'],
                  'mean_mask_hit_fraction': value['mask_hit_sum'] / value['views'],
                  'mean_front_fraction': value['front_fraction_sum'] / value['views']}
                 for key, value in totals.items()]
    aggregate.sort(key=lambda value: value['mean_bbox_abs_error_px'])
    receipt = {'schema': 'STEREO_GSO_MESH_PROJECTION_PROBE_V1', 'status': 'DIAGNOSTIC_ONLY',
               'job_id': os.environ['SLURM_JOB_ID'], 'host': socket.gethostname(),
               'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
               'manifest_sha256': sha256_file(args.manifest), 'objects': len(results),
               'ranked_candidates': aggregate, 'historical_renderer_verified': False,
               'canonical_to_cv_verified': False, 'target_ready': False, 'scientific_evidence': False}
    (output / 'objects.json').write_text(json.dumps(results, indent=2) + '\n')
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'job_id': receipt['job_id'], 'top_candidates': aggregate[:5]}, indent=2), flush=True)


if __name__ == '__main__':
    main()
