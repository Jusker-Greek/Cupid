#!/usr/bin/env python3
"""Build immutable pair inventory on a Slurm compute node (CPU only)."""
from __future__ import annotations
import argparse
import collections
import csv
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.datasets.stereo_gso import discover_pairs, load_pair, sha256_file


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--verify-content', action='store_true')
    parser.add_argument('--hash-assets', action='store_true')
    parser.add_argument('--max-pairs', type=int)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        parser.error('Run inside a Slurm compute allocation')
    if args.hash_assets and not args.verify_content:
        parser.error('--hash-assets requires --verify-content')
    if args.max_pairs is not None and args.max_pairs <= 0:
        parser.error('--max-pairs must be positive')
    config = json.loads(Path(args.config).read_text())
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    counts = collections.Counter()
    objects, splits = set(), collections.defaultdict(set)
    # On-disk index bounds memory during full-dataset image duplicate checks.
    db = sqlite3.connect(output / 'content_index.sqlite')
    db.execute('CREATE TABLE assets (sha TEXT PRIMARY KEY, pair_id TEXT, object_id TEXT, split TEXT, side TEXT)')
    summary = {'schema': 'STEREO_GSO_AUDIT_V1', 'status': 'RUNNING',
               'started_at': datetime.now(timezone.utc).isoformat(),
               'job_id': os.environ['SLURM_JOB_ID'], 'host': socket.gethostname(),
               'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
               'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
               'config': config, 'config_sha256': sha256_file(args.config),
               'scope': 'BOUNDED' if args.max_pairs else 'FULL_DISCOVERY',
               'content_verification_requested': args.verify_content,
               'content_duplicates_checked': args.hash_assets,
               'scientific_evidence': False}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    try:
        with (output / 'pairs.jsonl').open('x') as manifest, (output / 'duplicates.jsonl').open('x') as duplicates:
            for index, row in enumerate(discover_pairs(config['root'], config['dataset_id'], config['split_seed'], config['split_fractions'])):
                if args.max_pairs and index >= args.max_pairs:
                    break
                counts['candidate_records'] += 1
                counts['observed_frame_candidates' if row['frame_id'] is not None else 'empty_trajectories'] += 1
                objects.add(row['object_id'])
                splits[row['split']].add(row['object_id'])
                if row['validity']['files_complete']:
                    counts['files_complete'] += 1
                    if args.verify_content:
                        try:
                            pack = load_pair(row, config['root'], depth_background=config['depth_background_exclusive'], hash_assets=args.hash_assets)
                            row['validity'] = pack['validity']
                            row['provenance'] = pack['provenance']
                            row['view_diagnostics'] = {
                                side: {'proper_rotation': v['proper_rotation'],
                                       'rotation_determinant': v['rotation_determinant'],
                                       'K_status': v['K_status'], 'K_fullpixel': v['K_fullpixel'].tolist(),
                                       'w2c_saved': v['w2c_saved'].tolist(),
                                       'foreground_pixels': int(v['mask'].sum()),
                                       'valid_depth_pixels': int(v['depth_valid'].sum())}
                                for side, v in pack['views'].items()}
                            counts['content_verified'] += 1
                            counts['proper_rotation_pairs'] += int(pack['validity']['proper_rotations'])
                            if args.hash_assets:
                                row['asset_sha256'] = pack['asset_sha256']
                                for side in ('left', 'right'):
                                    digest = pack['asset_sha256'][side + '_rgba']
                                    prior = db.execute('SELECT pair_id,object_id,split,side FROM assets WHERE sha=?', (digest,)).fetchone()
                                    if prior:
                                        cross = prior[2] != row['split']
                                        counts['duplicate_images'] += 1
                                        counts['cross_split_duplicate_images'] += int(cross)
                                        duplicates.write(json.dumps({'sha256': digest, 'pair_id': row['pair_id'], 'side': side,
                                            'prior': dict(zip(('pair_id', 'object_id', 'split', 'side'), prior)),
                                            'cross_split': cross}) + '\n')
                                    else:
                                        db.execute('INSERT INTO assets VALUES (?,?,?,?,?)', (digest, row['pair_id'], row['object_id'], row['split'], side))
                        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
                            row['validity']['errors'].append(type(exc).__name__ + ': ' + str(exc))
                            row['validity']['content_verified'] = False
                            counts['content_failed'] += 1
                else:
                    counts['incomplete_records'] += 1
                manifest.write(json.dumps(row, allow_nan=False) + '\n')
                if (index + 1) % 100 == 0:
                    db.commit()
                    manifest.flush()
                    print(json.dumps(dict(counts)), flush=True)
        db.commit()
        summary['status'] = 'COMPLETED'
        summary['manifest_sha256'] = sha256_file(output / 'pairs.jsonl')
        summary['object_split_disjoint'] = not any(splits[a] & splits[b] for a,b in [('train','validation'),('train','test'),('validation','test')])
        summary['content_leakage_status'] = ('FAIL' if counts['cross_split_duplicate_images'] else 'PASS_WITHIN_SCANNED_SCOPE') if args.hash_assets else 'UNVERIFIED'
        registry = config.get('registry')
        if registry:
            try:
                with open(registry) as handle:
                    rows = list(csv.DictReader(handle, delimiter='\t'))
                summary['registry'] = {'path': registry, 'sha256': sha256_file(registry), 'rows': len(rows),
                                       'columns': list(rows[0]) if rows else [], 'not_a_pair_count': True}
            except OSError as exc:
                summary['registry'] = {'path': registry, 'error': str(exc)}
    except Exception as exc:
        summary['status'] = 'FAILED'
        summary['error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        db.close()
        summary['counts'] = dict(counts)
        summary['observed_objects'] = len(objects)
        summary['split_objects'] = {key: sorted(values) for key, values in splits.items()}
        summary['ended_at'] = datetime.now(timezone.utc).isoformat()
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
