#!/usr/bin/env python3
"""Collect asset/normalization evidence; candidates are NOT accepted GT receipts."""
import argparse
import json
import os
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cupid.datasets.stereo_gso import confined_path, load_pair, sha256_file


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--asset-root', default='/public/home/ricky/DATASET/Gazebo')
    parser.add_argument('--renderer', default='/public/home/ricky/CODE/GSO_dataset/render_stereo_gazebo.py')
    parser.add_argument('--output', required=True)
    parser.add_argument('--max-objects', type=int)
    args = parser.parse_args()
    if not os.environ.get('SLURM_JOB_ID'):
        parser.error('Slurm compute allocation required')
    if args.max_objects is not None and args.max_objects <= 0:
        parser.error('--max-objects must be positive')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    renderer = Path(args.renderer)
    renderer_identity = {'path':str(renderer), 'sha256':sha256_file(renderer) if renderer.is_file() else None,
                         'is_historical_generation_revision':False}
    seen, counts = set(), {'objects':0,'errors':0}
    with open(args.manifest) as manifest, (output/'geometry_candidates.jsonl').open('x') as result:
        for line in manifest:
            row = json.loads(line)
            if row['object_id'] in seen or not row['validity']['content_verified']:
                continue
            if args.max_objects and len(seen) >= args.max_objects:
                break
            seen.add(row['object_id'])
            candidate = {'pair_id':row['pair_id'], 'object_id':row['object_id'],
                         'status':'UNVERIFIED_GEOMETRY_CANDIDATE', 'renderer':renderer_identity,
                         'normalization':row['normalization'], 'unit':row['unit']}
            try:
                mesh = confined_path(args.asset_root, row['object_id']+'/meshes/model.obj')
                vertices = []
                with mesh.open() as handle:
                    for obj_line in handle:
                        if obj_line.startswith('v '):
                            vertices.append([float(v) for v in obj_line.split()[1:4]])
                vertices = np.asarray(vertices)
                if vertices.ndim != 2 or vertices.shape[1] != 3 or not len(vertices) or not np.isfinite(vertices).all():
                    raise ValueError('OBJ has no valid finite xyz vertices')
                candidate['asset'] = {'path':str(mesh), 'sha256':sha256_file(mesh), 'vertices':len(vertices),
                                      'bounds':[vertices.min(0).tolist(),vertices.max(0).tolist()]}
                norm = row['normalization']
                if not norm:
                    raise ValueError('missing normalization')
                scale, offset = float(norm['scale']), np.asarray(norm['offset'],dtype=float)
                if not np.isfinite(scale) or scale <= 0 or offset.shape != (3,) or not np.isfinite(offset).all():
                    raise ValueError('invalid normalization')
                # Existing Panda audit hypothesis only; NEVER bless based on small residual.
                imported = vertices[:,[0,2,1]] * [1,-1,1]
                extent = np.ptp(imported,axis=0).max()
                if extent <= 0:
                    raise ValueError('degenerate asset extent')
                derived_scale = 1/extent
                derived_offset = -(imported.min(0)+imported.max(0))/2*derived_scale
                normalized = imported*scale+offset
                candidate['obj_import_hypothesis'] = {
                    'mapping':'(x,y,z)->(x,-z,y)', 'derived_scale':float(derived_scale),
                    'scale_delta':float(scale-derived_scale), 'offset_delta':(offset-derived_offset).tolist(),
                    'normalized_bounds':[normalized.min(0).tolist(),normalized.max(0).tolist()],
                    'historical_importer_verified':False}
                pack = load_pair(row,args.root,hash_assets=True)
                candidate['source_asset_sha256'] = pack['asset_sha256']
                candidate['views'] = {side:{'K_fullpixel_hypothesis':v['K_fullpixel'].tolist(),
                    'w2c_saved':v['w2c_saved'].tolist(), 'determinant':v['rotation_determinant'],
                    'proper_rotation':v['proper_rotation']} for side,v in pack['views'].items()}
                left,right = [pack['views'][side]['w2c_saved'] for side in ('left','right')]
                relative = right @ np.linalg.inv(left)
                candidate['right_from_left_saved_axes'] = relative.tolist()
                candidate['baseline_scene_units'] = float(np.linalg.norm(relative[:3,3]))
                candidate['remaining_inputs'] = ['verified historical asset-to-canonical mapping',
                    'official canonical voxel occupancy', 'canonical-to-CV camera convention',
                    'integer crop boxes paired with official image preprocessing']
            except (OSError, ValueError, KeyError, TypeError, np.linalg.LinAlgError) as exc:
                candidate['error'] = type(exc).__name__+': '+str(exc)
                counts['errors'] += 1
            result.write(json.dumps(candidate,allow_nan=False)+'\n')
            result.flush()
            counts['objects'] += 1
    summary = {'job_id':os.environ['SLURM_JOB_ID'], 'counts':counts, 'scope':'ONE_PAIR_PER_OBJECT',
               'max_objects':args.max_objects, 'renderer':renderer_identity,
               'manifest_sha256':sha256_file(args.manifest), 'target_ready':False, 'scientific_evidence':False}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    if counts['errors'] or not counts['objects']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
