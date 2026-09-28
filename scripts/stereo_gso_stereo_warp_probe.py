#!/usr/bin/env python3
"""Bounded stereo depth-warp diagnostic; never creates a CV or target receipt."""
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
from cupid.datasets.stereo_gso import load_pair, sha256_file


def homogeneous(w2c):
    if w2c.shape == (4, 4):
        return w2c
    if w2c.shape != (3, 4):
        raise ValueError('expected 3x4 or 4x4 camera matrix')
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3] = w2c
    return matrix


def score_pair(pack, axis, depth_mode, stride):
    left, right = pack['views']['left'], pack['views']['right']
    height, width = left['depth'].shape
    yy, xx = np.mgrid[0:height:stride, 0:width:stride]
    xx, yy = xx.ravel(), yy.ravel()
    valid = left['depth_valid'][yy, xx]
    xx, yy = xx[valid], yy[valid]
    if not len(xx):
        return {'sampled': 0, 'projected': 0, 'depth_compared': 0, 'depth_within_2pct': 0}

    K = left['K_fullpixel']
    ray = np.stack(((xx + .5 - K[0, 2]) / K[0, 0],
                    (yy + .5 - K[1, 2]) / K[1, 1], np.ones(len(xx))), axis=0)
    if depth_mode == 'radial':
        ray /= np.linalg.norm(ray, axis=0)
    xyz_saved = (axis[:, None] * ray) * left['depth'][yy, xx]
    right_from_left = homogeneous(right['w2c_saved']) @ np.linalg.inv(homogeneous(left['w2c_saved']))
    mapped_saved = right_from_left[:3, :3] @ xyz_saved + right_from_left[:3, 3, None]
    mapped = axis[:, None] * mapped_saved
    front = mapped[2] > 1e-6
    ur = np.full(len(xx), -1, dtype=np.int64)
    vr = np.full(len(xx), -1, dtype=np.int64)
    ur[front] = np.rint(K[0, 0] * mapped[0, front] / mapped[2, front] + K[0, 2] - .5).astype(np.int64)
    vr[front] = np.rint(K[1, 1] * mapped[1, front] / mapped[2, front] + K[1, 2] - .5).astype(np.int64)
    inside = front & (ur >= 0) & (ur < width) & (vr >= 0) & (vr < height)
    sampled = len(xx)
    if not inside.any():
        return {'sampled': sampled, 'projected': 0, 'depth_compared': 0, 'depth_within_2pct': 0}
    xx, yy, ur, vr = xx[inside], yy[inside], ur[inside], vr[inside]
    mapped = mapped[:, inside]
    target_valid = right['depth_valid'][vr, ur]
    compared = int(target_valid.sum())
    if not compared:
        return {'sampled': sampled, 'projected': len(ur), 'depth_compared': 0, 'depth_within_2pct': 0}
    xx, yy, ur, vr = xx[target_valid], yy[target_valid], ur[target_valid], vr[target_valid]
    mapped = mapped[:, target_valid]
    predicted = mapped[2] if depth_mode == 'z' else np.linalg.norm(mapped, axis=0)
    observed = right['depth'][vr, ur]
    relative = np.abs(predicted - observed) / np.maximum(observed, 1e-6)
    close = relative < .02
    left_rgb = left['rgba'][yy, xx, :3].astype(np.float32)
    right_rgb = right['rgba'][vr, ur, :3].astype(np.float32)
    photo_sum = float(np.abs(left_rgb[close] - right_rgb[close]).sum()) if close.any() else 0.
    return {'sampled': sampled, 'projected': len(ur), 'depth_compared': compared,
            'depth_within_2pct': int(close.sum()), 'depth_relative_error_sum': float(relative.sum()),
            'photo_absolute_error_sum': photo_sum, 'photo_channel_count': int(close.sum()) * 3}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--max-pairs', type=int, default=12)
    parser.add_argument('--stride', type=int, default=8)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        parser.error('Slurm compute allocation required')
    if args.max_pairs <= 0 or args.stride <= 0:
        parser.error('max-pairs and stride must be positive')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    candidates = [(np.asarray((sx, sy, sz), dtype=np.float64), mode)
                  for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)
                  for mode in ('z', 'radial')]
    totals = defaultdict(lambda: defaultdict(float))
    pair_results = []
    seen_objects = set()
    with Path(args.manifest).open() as rows:
        for line in rows:
            row = json.loads(line)
            if not row['validity']['content_verified'] or row['object_id'] in seen_objects:
                continue
            if len(pair_results) >= args.max_pairs:
                break
            seen_objects.add(row['object_id'])
            pack = load_pair(row, args.root)
            scores = {}
            for axis, mode in candidates:
                key = ''.join('+' if value > 0 else '-' for value in axis) + '/' + mode
                result = score_pair(pack, axis, mode, args.stride)
                scores[key] = result
                for field, value in result.items():
                    totals[key][field] += value
            pair_results.append({'pair_id': row['pair_id'], 'object_id': row['object_id'],
                                 'source_asset_sha256': row['asset_sha256'], 'scores': scores})
            print(f'PAIR {len(pair_results)} {row["pair_id"]}', flush=True)
    if len(pair_results) != args.max_pairs:
        raise ValueError(f'Only {len(pair_results)} distinct content-verified objects found')
    aggregate = {}
    for key, values in totals.items():
        values = dict(values)
        values['depth_match_fraction'] = (values['depth_within_2pct'] / values['depth_compared']
                                          if values['depth_compared'] else 0.)
        values['depth_mean_relative_error'] = (values.get('depth_relative_error_sum', 0.) / values['depth_compared']
                                               if values['depth_compared'] else None)
        values['photo_mean_absolute_error'] = (values.get('photo_absolute_error_sum', 0.) / values.get('photo_channel_count', 0)
                                               if values.get('photo_channel_count') else None)
        aggregate[key] = values
    ranked = sorted(aggregate, key=lambda key: aggregate[key]['depth_match_fraction'], reverse=True)
    receipt = {'schema': 'STEREO_GSO_STEREO_WARP_PROBE_V1', 'status': 'DIAGNOSTIC_ONLY',
               'job_id': os.environ['SLURM_JOB_ID'], 'host': socket.gethostname(),
               'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
               'manifest_sha256': sha256_file(args.manifest), 'max_pairs': args.max_pairs,
               'stride': args.stride, 'candidate_axis': 'saved_camera_xyz = diagonal_signs * image_cv_ray',
               'depth_modes': ['z', 'radial'], 'threshold_relative_depth': .02,
               'ranked_candidates': [{'key': key, **aggregate[key]} for key in ranked],
               'historical_renderer_verified': False, 'canonical_to_cv_verified': False,
               'target_ready': False, 'scientific_evidence': False}
    (output / 'pairs.json').write_text(json.dumps(pair_results, indent=2) + '\n')
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'job_id': receipt['job_id'], 'pairs': len(pair_results),
                      'top_candidates': receipt['ranked_candidates'][:5]}, indent=2), flush=True)


if __name__ == '__main__':
    main()
