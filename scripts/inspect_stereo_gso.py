"""Bounded read-only GSO inspection; run only inside a Slurm allocation."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

import h5py
import numpy as np
from PIL import Image


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Inspection computation requires Slurm')
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    root = Path('/public/home/ricky/DATASET/gso_stereo_output_random')
    obj = root / 'Android_Figure_Panda'
    mesh = Path('/public/home/ricky/DATASET/Gazebo/Android_Figure_Panda/meshes/model.obj')
    renderer = Path('/public/home/ricky/CODE/GSO_dataset/render_stereo_gazebo.py')
    report = {'job': os.environ['SLURM_JOB_ID'], 'host': os.uname().nodename,
              'root': str(root), 'scope': 'five Panda manifests; first pair contents only',
              'renderer_sha256': digest(renderer), 'mesh_sha256': digest(mesh),
              'root_object_directory_count': sum(p.is_dir() for p in root.iterdir()),
              'manifests': []}
    for trajectory in sorted(obj.glob('random_linear_*')):
        meta = json.loads((trajectory / 'trajectory_info.json').read_text())
        counts = {f'{side}_{ext}': len(list((trajectory / side).glob('*.' + ext)))
                  for side in ['left', 'right'] for ext in ['png', 'npy']}
        counts['hdf5'] = len(list(trajectory.glob('*.hdf5')))
        report['manifests'].append({'path': str(trajectory), 'metadata': meta, 'counts': counts})
    registry = Path('/public/home/ricky/CODE/GSO_dataset/task_allocations/GSO_1K_200/object_registry.tsv')
    with registry.open() as handle:
        rows = list(csv.DictReader(handle, delimiter='\t'))
    report['large_registry'] = {'path': str(registry), 'rows': len(rows),
        'unique_objects': len({row['object_name'] for row in rows}),
        'statuses': sorted({row['status'] for row in rows}),
        'warning': 'assignment manifest, not completed/rendered trajectory count'}
    pair = obj / 'random_linear_0'
    meta = report['manifests'][0]['metadata']
    focal = 256 / np.tan(np.deg2rad(meta['fov']) / 2)
    K = np.array([[focal, 0, 256], [0, focal, 256], [0, 0, 1]])
    report['candidate_K_from_current_renderer'] = K.tolist()
    matrices = []
    report['images'] = {}
    for side in ['left', 'right']:
        path = pair / side / '000.png'
        image = np.array(Image.open(path))
        mask = image[..., 3] > 127 if image.shape[-1] == 4 else np.ones(image.shape[:2], bool)
        y, x = np.nonzero(mask)
        report['images'][side] = {'sha256': digest(path), 'shape': list(image.shape),
            'alpha_range': [int(image[..., -1].min()), int(image[..., -1].max())],
            'mask_pixels': int(mask.sum()), 'bbox_xyxy': [int(x.min()), int(y.min()), int(x.max()), int(y.max())]}
        matrix = np.eye(4)
        matrix[:3] = np.load(pair / side / '000.npy', allow_pickle=False)
        matrices.append(matrix)
    left, right = matrices
    relative = right @ np.linalg.inv(left)
    report['cameras'] = {'saved_w2c': [m.tolist() for m in matrices],
        'determinants': [float(np.linalg.det(m[:3, :3])) for m in matrices],
        'orthogonality_error': [float(np.max(np.abs(m[:3, :3].T @ m[:3, :3] - np.eye(3)))) for m in matrices],
        'right_from_left_saved_axes': relative.tolist(),
        'baseline_scene_units': float(np.linalg.norm(relative[:3, 3])),
        'metric_meters_verified': False}
    vertices = np.array([[float(v) for v in line.split()[1:4]] for line in mesh.read_text().splitlines() if line.startswith('v ')])
    report['mesh'] = {'path': str(mesh), 'vertices': len(vertices),
        'raw_bounds': [vertices.min(0).tolist(), vertices.max(0).tolist()]}
    report['hdf5'] = {}
    with h5py.File(pair / '0.hdf5', 'r') as handle:
        def inspect(name, item):
            if not isinstance(item, h5py.Dataset):
                return
            entry = {'shape': list(item.shape), 'dtype': str(item.dtype)}
            if item.size < 3000000 and np.issubdtype(item.dtype, np.number):
                array = item[()]
                finite = np.asarray(array)[np.isfinite(array)]
                entry.update(finite_count=int(finite.size), min=float(finite.min()) if finite.size else None,
                             max=float(finite.max()) if finite.size else None)
                if 'depth' in name and array.shape == (2, 512, 512):
                    # Diagnostic warp under explicit rectified pinhole hypothesis.
                    # Nearest right depth comparison; exclude invalid/outside/occluded pixels.
                    yy, xx = np.mgrid[0:512:8, 0:512:8]
                    z = array[0, yy, xx]
                    ok = np.isfinite(z) & (z > 0) & (z < 100)
                    xr = np.zeros_like(xx)
                    xr[ok] = np.rint(xx[ok] - focal * meta['baseline'] / z[ok]).astype(int)
                    ok &= (xr >= 0) & (xr < 512)
                    zr = array[1, yy[ok], xr[ok]]
                    delta = np.abs(zr - z[ok])
                    entry['rectified_depth_warp_diagnostic'] = {'tested': int(ok.sum()),
                        'median_absolute_depth_difference': float(np.median(delta)),
                        'within_0_01_scene_unit_fraction': float(np.mean(delta < .01)),
                        'not_proof_of_absolute_pose_or_physical_meters': True}
            report['hdf5'][name] = entry
        handle.visititems(inspect)
    (output / 'sample_inspection.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
