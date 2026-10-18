#!/usr/bin/env python3
"""Re-read all bound GSO pairs on Slurm; distinguish empirical geometry from provenance.

Does not create training targets, select a new split, repair cameras or bless
historical renderer identity. Each failed pair remains in the denominator.
"""
import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.datasets.stereo_gso import load_pair, sha256_file, confined_path, object_split


def unique_rows(path):
    result = {}
    with open(path) as handle:
        for line in handle:
            row = json.loads(line)
            if row['pair_id'] in result:
                raise ValueError('duplicate pair ID: '+row['pair_id'])
            result[row['pair_id']] = row
    return result


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('SLURMD_NODENAME'):
        parser.error('Slurm compute node required')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(schema='SC_POSECROSS_DATA_AUDIT_V1', status='RUNNING', scientific_evidence=False,
                  job=os.environ['SLURM_JOB_ID'], node=os.environ['SLURMD_NODENAME'],
                  commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),
                  config_sha256=sha256_file(args.config))
    try:
        config = json.loads(Path(args.config).read_text())
        data = config['data']
        records, targets = unique_rows(data['manifest']), unique_rows(data['target_index'])
        report.update(manifest_sha256=sha256_file(data['manifest']), target_index_sha256=sha256_file(data['target_index']),
                      pairs=len(records), objects=len({r['object_id'] for r in records.values()}),
                      split_pairs=dict(Counter(r['split'] for r in records.values())),
                      target_coverage_exact=set(records)==set(targets))
        if not records or set(records) != set(targets):
            raise ValueError('empty corpus or target coverage mismatch')
        objects, images, assets = defaultdict(set), defaultdict(set), defaultdict(set)
        for pid, row in records.items():
            objects[row['object_id']].add(row['split'])
            for side in ('left','right'):
                images[row['asset_sha256'][side+'_rgba']].add(row['split'])
            assets[targets[pid]['provenance']['asset_sha256']].add(row['split'])
        report['cross_split_leaks'] = dict(objects=sum(len(v)>1 for v in objects.values()),
            identical_images=sum(len(v)>1 for v in images.values()), identical_source_assets=sum(len(v)>1 for v in assets.values()))
        counts = Counter()
        with (output/'pairs.jsonl').open('x') as handle:
            for pid, row in records.items():
                item = dict(pair_id=pid, object_id=row['object_id'], split=row['split'], status='ERROR')
                try:
                    target = targets[pid]
                    for key in ('object_id','trajectory_id','frame_id','split'):
                        if row[key] != target[key]:
                            raise ValueError('target identity differs: '+key)
                    policy = row['split_policy']
                    if object_split(row['object_id'], policy['seed'], policy['fractions']) != row['split']:
                        raise ValueError('split assignment differs from bound policy')
                    pack = load_pair(row, data['root'], hash_assets=True)
                    if pack['asset_sha256'] != row['asset_sha256'] or pack['asset_sha256'] != target['source_asset_sha256']:
                        raise ValueError('source hashes changed')
                    path = confined_path(data['target_root'], target['npz'])
                    if sha256_file(path) != target['sha256']:
                        raise ValueError('target NPZ hash changed')
                    with np.load(path, allow_pickle=False) as z:
                        crop = z['crop_xyxy'].copy()
                    p = target['provenance']
                    shift = np.eye(4)
                    shift[0,3] = p['saved_camera_x_shift_baseline_factor'] * row['metadata']['baseline']
                    cameras = np.stack([np.asarray(p['camera_axis_to_cv']) @ shift @ pack['views'][s]['w2c_saved'] @ np.asarray(p['canonical_world_mirror']) for s in ('left','right')])
                    proper = all(np.allclose(t[3],[0,0,0,1],atol=1e-7) and np.allclose(t[:3,:3].T@t[:3,:3],np.eye(3),atol=1e-5) and np.isclose(np.linalg.det(t[:3,:3]),1,atol=1e-5) for t in cameras)
                    relative = cameras[1] @ np.linalg.inv(cameras[0])
                    rotation_error = float(np.linalg.norm(relative[:3,:3]-np.eye(3)))
                    baseline = float(np.linalg.norm(relative[:3,3]))
                    transverse = float(np.linalg.norm(relative[1:3,3]))
                    Ks = [pack['views'][s]['K_fullpixel'] for s in ('left','right')]
                    Kcrop = []
                    for i in range(2):
                        x0,y0,x1,y1 = crop[i]
                        if x1 <= x0 or y1 <= y0 or not np.equal(crop[i], np.round(crop[i])).all():
                            raise ValueError('invalid integer crop')
                        M = np.array([[x1-x0,0,x0],[0,y1-y0,y0],[0,0,1]])
                        Kcrop.append(np.linalg.solve(M,Ks[i]))
                    item.update(status='READ_VERIFIED', proper_cameras=proper,
                        empirical_relative=relative.tolist(), baseline_scene_unit=baseline,
                        relative_rotation_identity_frobenius=rotation_error, off_horizontal_translation=transverse,
                        full_K_equal=bool(np.allclose(Ks[0],Ks[1],atol=1e-7)),
                        effective_crop_K_equal=bool(np.allclose(Kcrop[0],Kcrop[1],atol=1e-7)),
                        K_crop_uv=[k.tolist() for k in Kcrop],
                        numerically_rectified=bool(proper and rotation_error<1e-5 and transverse<1e-6 and baseline>1e-6 and np.allclose(Ks[0],Ks[1],atol=1e-7)),
                        canonical_frame=p['canonical_frame'], length_unit=p['length_unit'],
                        historical_renderer_verified=p['renderer_provenance']['historical_exact_revision_verified'],
                        metric_meters_verified=p.get('metric_meters_verified',False),
                        canonical_asset_transform=p['raw_obj_to_canonical'])
                    counts['read_verified'] += 1
                    counts['numerically_rectified'] += int(item['numerically_rectified'])
                    counts['historical_renderer_verified'] += int(item['historical_renderer_verified'])
                    counts['metric_meters_verified'] += int(item['metric_meters_verified'])
                except Exception as exc:
                    item['error'] = type(exc).__name__+': '+str(exc)
                    counts['errors'] += 1
                handle.write(json.dumps(item,allow_nan=False)+'\n')
                handle.flush()
        report.update(status='AUDIT_COMPLETED', counts=dict(counts),
            calibration_provenance='REQUIRES_INDEPENDENT_RENDERER_AND_CANONICAL_ACCEPTANCE',
            full_training_eligible=False)
        if counts['errors'] or any(report['cross_split_leaks'].values()):
            report['status'] = 'DATA_INTEGRITY_FAIL'
            raise RuntimeError('Data integrity/overlap failure; inspect all retained pair records')
    except Exception as exc:
        report.update(status='ERROR' if report['status']=='RUNNING' else report['status'], error=type(exc).__name__+': '+str(exc))
        raise
    finally:
        (output/'receipt.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        print(json.dumps(report,indent=2,allow_nan=False),flush=True)


if __name__ == '__main__':
    main()
