#!/usr/bin/env python3
"""Prepare official dense SS/SUV targets from explicit verified geometry receipts.

CPU Slurm only. This does not infer canonical asset transforms from saved camera
matrices, generate occupancy from visible depth, or encode latents on a GPU.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.datasets.stereo_gso import confined_path, load_pair, official_dense_targets, sha256_file


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--geometry-index', required=True)
    parser.add_argument('--geometry-root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        parser.error('Slurm compute allocation required')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    records = {}
    with open(args.manifest) as handle:
        for line in handle:
            row = json.loads(line)
            if row['pair_id'] in records:
                raise ValueError('duplicate pair_id')
            records[row['pair_id']] = row
    counts = {'prepared': 0, 'failed': 0}
    seen = set()
    with open(args.geometry_index) as geometry, (output/'targets.jsonl').open('x') as index, (output/'failures.jsonl').open('x') as failures:
        for line in geometry:
            entry = json.loads(line)
            pair_id = entry['pair_id']
            if pair_id in seen:
                raise ValueError('duplicate geometry pair_id: ' + pair_id)
            seen.add(pair_id)
            try:
                record = records[pair_id]
                receipt_path = confined_path(args.geometry_root, entry['receipt'])
                if sha256_file(receipt_path) != entry['receipt_sha256']:
                    raise ValueError('geometry receipt hash mismatch')
                receipt = json.loads(receipt_path.read_text())
                if receipt['pair_id'] != pair_id or receipt['schema'] != 'STEREO_GSO_GEOMETRY_V1':
                    raise ValueError('geometry identity/schema mismatch')
                for field in ('canonical_occupancy_verified', 'canonical_to_cv_verified'):
                    if receipt['validity'].get(field) is not True:
                        raise ValueError(field + ' is not verified')
                # Evidence is required alongside booleans: a flag alone is not provenance.
                for field in ('canonical_frame', 'asset_sha256', 'renderer_provenance', 'geometry_evidence'):
                    if not receipt['provenance'].get(field):
                        raise ValueError('missing geometry provenance: ' + field)
                pack = load_pair(record, args.root, hash_assets=True)
                if pack['asset_sha256'] != receipt['source_asset_sha256'] or pack['asset_sha256'] != record.get('asset_sha256'):
                    raise ValueError('geometry receipt/source hash mismatch')
                occ_path = confined_path(args.geometry_root, receipt['occupancy_npy'])
                if sha256_file(occ_path) != receipt['occupancy_sha256']:
                    raise ValueError('canonical occupancy hash mismatch')
                occupancy = np.load(occ_path, allow_pickle=False)
                for i, side in enumerate(('left','right')):
                    h,w = pack['views'][side]['rgba'].shape[:2]
                    if receipt['image_wh'][i] != [w,h]:
                        raise ValueError('geometry image dimensions mismatch')
                if receipt['const_ssuv'] is not True:
                    raise ValueError('V1 official config requires const_ssuv=true')
                dense = official_dense_targets(occupancy, receipt['w2c_cv'], receipt['K_fullpixel'], receipt['image_wh'], receipt['crop_xyxy'], const_ssuv=True)
                name = hashlib.sha256(pair_id.encode()).hexdigest() + '.npz'
                with (output/name).open('xb') as handle:
                    np.savez_compressed(handle, **{k:v.numpy() for k,v in dense.items()}, crop_xyxy=np.asarray(receipt['crop_xyxy']))
                target = {k:record[k] for k in ('pair_id','object_id','trajectory_id','frame_id','split')}
                target.update(schema='STEREO_GSO_DENSE_V1', npz=name, sha256=sha256_file(output/name),
                              source_asset_sha256=pack['asset_sha256'],
                              provenance={**receipt['provenance'], 'geometry_receipt_sha256':entry['receipt_sha256'],
                                          'const_ssuv':True, 'length_unit':'scene_unit', 'metric_meters_verified':False})
                index.write(json.dumps(target)+'\n')
                index.flush()
                counts['prepared'] += 1
            except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
                failures.write(json.dumps({'pair_id':pair_id,'error':type(exc).__name__+': '+str(exc)})+'\n')
                failures.flush()
                counts['failed'] += 1
    summary = {'counts':counts, 'job_id':os.environ['SLURM_JOB_ID'], 'source_manifest_sha256':sha256_file(args.manifest),
               'geometry_index_sha256':sha256_file(args.geometry_index), 'target_index_sha256':sha256_file(output/'targets.jsonl'),
               'source_pairs':len(records), 'geometry_pairs':len(seen), 'missing_geometry_pairs':len(set(records)-seen),
               'scientific_evidence':False}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    if counts['failed'] or not counts['prepared'] or set(records)-seen:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
